from asyncio.log import logger
from zipfile import Path

from config import BINARY_EXTENSIONS, CICD_FILES, CONFIG_FILES,  EXCLUDED_DIRECTORIES, LANGUAGE_EXTENSIONS, Configuration
from models import RepoStats, BaseRepoInfo, CodeStats, QualityIndicators, ActivityMetrics, CommunityMetrics, AnalysisScores
from utilities import ensure_utc
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Any, Optional
import concurrent.futures

from github.Repository import Repository
from github.GithubException import GithubException, RateLimitExceededException
from tqdm.auto import tqdm



class GithubAnalyzer:
    """Class responsible for analyzing GitHub repositories"""
    
    def __init__(self, github, username: str, config: Optional[Configuration] = None):
        """Initialize the analyzer with GitHub client, username and configuration"""
        self.github = github
        self.username = username
        self.config = config
        self.rate_display = None
        self.session = None
        self.user = None
        self.checkpoint = None
        self.max_workers = self.config.get("MAX_WORKERS", 1) if self.config else 1

    def check_rate_limit(self) -> None:
        """Check GitHub API rate limit and wait if necessary"""
        try:
            # Get rate data from API
            rate_limit = self.github.get_rate_limit()
            remaining = rate_limit.core.remaining
            reset_time = rate_limit.core.reset
            
            if remaining < 100:  # Low on remaining requests
                # Check if we need to wait
                wait_time = (reset_time - datetime.now().replace(tzinfo=timezone.utc)).total_seconds()
                if wait_time > 0:
                    logger.warning(f"GitHub API rate limit low ({remaining} left). Waiting {wait_time:.1f}s until reset.")
                    self._visualize_wait(wait_time, "Rate limit cooldown")
        except Exception as e:
            logger.warning(f"Could not check rate limit: {e}")
            
    def _visualize_wait(self, wait_time: float, desc: str):
        """Display a progress bar for wait periods"""
        # Cap very long waits to show reasonable progress
        if wait_time > 3600:  # If more than an hour
            logger.warning(f"Long wait time detected ({wait_time:.1f}s). Showing progress for first hour.")
            print(f"⚠️ GitHub API requires a long cooldown period ({wait_time/60:.1f} minutes)")
            print(f"The script will automatically continue after the wait period.")
            wait_time = 3600  # Cap to 1 hour for the progress bar
        
        # Show progress bar for the wait
        wait_seconds = int(wait_time)
        for _ in tqdm(range(wait_seconds), desc=desc, colour="yellow", leave=True):
            time.sleep(1)

    def analyze_all_repositories(self) -> List[RepoStats]:
        """Analyze all repositories for the user"""
        logger.info(f"Starting analysis of all repositories for {self.username}")
        
        all_stats = []
        analyzed_repo_names = []
        repos_to_analyze = []
        last_rate_display = 0  # Track when we last displayed the rate usage
        
        try:
            # Check for existing checkpoint
            checkpoint_data = self.load_checkpoint()
            
            # If checkpoint exists and resume is enabled, load the checkpoint data
            if checkpoint_data:
                all_stats = checkpoint_data.get('all_stats', [])
                analyzed_repo_names = checkpoint_data.get('analyzed_repos', [])
                logger.info(f"Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
                print(f"📋 Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
            
            # Initialize GitHub user with rate limit check
            self.check_rate_limit()
            self.user = self.github.get_user(self.username)
            
            # Get all repositories
            all_repos = list(self.user.get_repos())
            
            # Apply filters based on configuration
            for repo in all_repos:
                # Skip already analyzed repos from checkpoint
                if repo.name in analyzed_repo_names:
                    logger.debug(f"Skipping previously analyzed repo from checkpoint: {repo.name}")
                    continue
                    
                # Apply filters
                if self.config["SKIP_FORKS"] and repo.fork:
                    logger.info(f"Skipping fork: {repo.name}")
                    continue
                    
                if self.config["SKIP_ARCHIVED"] and repo.archived:
                    logger.info(f"Skipping archived repo: {repo.name}")
                    continue
                    
                if not self.config["INCLUDE_PRIVATE"] and repo.private:
                    logger.info(f"Skipping private repo: {repo.name}")
                    continue
                    
                repos_to_analyze.append(repo)
            
            # Report on repos    
            logger.info(f"Found {len(repos_to_analyze)} repositories to analyze after filtering")
            if analyzed_repo_names:
                logger.info(f"Skipping {len(analyzed_repo_names)} already analyzed repositories from checkpoint")
            
            if not repos_to_analyze and not all_stats:
                logger.warning("No repositories found matching the criteria")
                return []
                
            if not repos_to_analyze and all_stats:
                logger.info("All repositories have already been analyzed according to checkpoint")
                return all_stats
                
            # Track newly analyzed repositories in this session
            newly_analyzed_repos = []
            
            # For progress bar display, accurate counts including checkpoint
            total_repos = len(repos_to_analyze) + len(all_stats)
            
            # Display initial rate limit usage before starting
            print("\n--- Initial API Rate Status ---")
            self.rate_display.display_once()  # Use our interactive display
            print("-------------------------------")
            
            # Use parallel processing if configured with multiple workers
            if self.max_workers > 1 and len(repos_to_analyze) > 1:
                logger.info(f"Using parallel processing with {self.max_workers} workers")
                
                with tqdm(total=total_repos, initial=len(all_stats),
                        desc="Analyzing repositories", leave=True, colour='green') as pbar:
                    
                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")
                        
                    # Process repos in smaller batches to allow for checkpointing
                    remaining_repos = repos_to_analyze.copy()
                    batch_size = min(20, len(remaining_repos))  # Process in batches of 20 or fewer
                    repo_counter = 0  # Counter to track repository processing
                    
                    while remaining_repos:
                        repo_counter += 1
                        # Take the next batch
                        batch = remaining_repos[:batch_size]
                        remaining_repos = remaining_repos[batch_size:]
                        
                        # Periodically show rate limit status (every 5 repos or after a batch)
                        if repo_counter % 5 == 0 or repo_counter == 1 or len(batch) == batch_size:
                            print("\n--- Current API Rate Status ---")
                            self.rate_display.display_once()  # Use our interactive display
                            print("-------------------------------")
                        
                        # Check if we need to checkpoint before processing this batch
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in newly_analyzed_repos], 
                                                            remaining_repos + batch):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            # Submit all tasks for this batch
                            future_to_repo = {
                                executor.submit(self.analyze_single_repository, repo): repo 
                                for repo in batch
                            }
                            
                            # Process results
                            for future in concurrent.futures.as_completed(future_to_repo):
                                repo = future_to_repo[future]
                                try:
                                    stats = future.result()
                                    all_stats.append(stats)
                                    newly_analyzed_repos.append(repo)
                                    analyzed_repo_names.append(repo.name)
                                    pbar.update(1)
                                except Exception as e:
                                    logger.error(f"Failed to analyze {repo.name}: {e}")
            else:
                # Sequential processing with progress bar
                with tqdm(total=total_repos, initial=len(all_stats),
                        desc="Analyzing repositories", leave=True, colour='green') as pbar:
                    
                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")
                    
                    # Process remaining repositories
                    remaining_repos = repos_to_analyze.copy()
                    repo_counter = 0  # Counter to track repository processing
                    
                    while remaining_repos:
                        repo_counter += 1
                        repo = remaining_repos.pop(0)
                        
                        # Periodically show rate limit status (every 5 repos)
                        if repo_counter % 5 == 0 or repo_counter == 1:
                            print("\n--- Current API Rate Status ---")
                            self.rate_display.display_once()  # Use our interactive display
                            print("-------------------------------")
                        
                        # Check if we need to checkpoint
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in newly_analyzed_repos], 
                                                            remaining_repos + [repo]):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats
                        
                        try:
                            stats = self.analyze_single_repository(repo)
                            all_stats.append(stats)
                            newly_analyzed_repos.append(repo)
                            analyzed_repo_names.append(repo.name)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to analyze {repo.name}: {e}")
                            continue
            
            # Analysis completed successfully - display final rate usage
            print("\n--- Final API Rate Status ---")
            self.rate_display.display_once()  # Use our interactive display
            print("----------------------------")
            
            # Save final checkpoint with empty remaining repos
            if self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, [])
                # Option to remove checkpoint file upon successful completion
                # if self.checkpoint_path.exists():
                #     self.checkpoint_path.unlink()
                #     logger.info("Removed checkpoint file after successful completion")
            
            logger.info(f"Successfully analyzed {len(all_stats)} repositories")
            return all_stats
            
        except RateLimitExceededException:
            logger.error("GitHub API rate limit exceeded during repository listing")
            # Create checkpoint before exiting due to rate limit
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            # Create checkpoint before exiting due to error
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            # Create checkpoint before exiting due to error
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise

    def check_rate_limit_and_checkpoint(self, all_stats, analyzed_repo_names, remaining_repos):
        """
        Check if the rate limit is approaching threshold and create a checkpoint if needed.
        
        Args:
            all_stats: List of RepoStats objects analyzed so far
            analyzed_repo_names: List of repository names already analyzed
            remaining_repos: List of Repository objects still to analyze
            
        Returns:
            Boolean: True if should stop processing, False if can continue
        """
        try:
            # Update rate data from API
            self.rate_display.update_from_api(self.github)
            remaining = self.rate_display.rate_data["remaining"]
            limit = self.rate_display.rate_data["limit"]
            
            # Check if below checkpoint threshold
            if remaining <= self.config["CHECKPOINT_THRESHOLD"]:
                logger.warning(f"Rate limit low: {remaining} of {limit} remaining")
                
                # Display rate usage
                self.rate_display.display_once()
                
                # Create checkpoint
                if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                    self.save_checkpoint(all_stats, analyzed_repo_names, remaining_repos)
                    
                # Return True to indicate should stop processing
                return True
                
            # Still have enough requests
            return False
                
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    def save_checkpoint(self, all_stats: List[RepoStats], analyzed_repo_names: List[str], remaining_repos: List[Repository]) -> None:
        """Save checkpoint data during analysis"""
        self.checkpoint.save(all_stats, analyzed_repo_names, remaining_repos)
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint data from previous analysis"""
        return self.checkpoint.load()

    def get_file_language(self, file_path: str) -> str:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_EXTENSIONS.get(ext, 'Other')

    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary"""
        ext = Path(file_path).suffix.lower()
        return ext in BINARY_EXTENSIONS

    def is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file"""
        filename = Path(file_path).name.lower()
        return filename in CONFIG_FILES
        
    def is_cicd_file(self, file_path: str) -> bool:
        """Check if file is related to CI/CD configuration"""
        for pattern in CICD_FILES:
            if pattern in file_path.lower():
                return True
        return False
        
    def is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file"""
        file_path_lower = file_path.lower()
        filename = Path(file_path).name.lower()
        
        # Check various test file patterns
        test_patterns = [
            '/test/', '/tests/', '/spec/', '/specs/',
            'test_', '_test.', '.test.', '.spec.',
            'test.', 'spec.', 'tests.', 'specs.'
        ]
        
        return any(pattern in file_path_lower or filename.startswith(pattern) or filename.endswith(pattern) 
                 for pattern in test_patterns)

    def count_lines_of_code(self, content: str, file_path: str) -> int:
        """Count lines of code, excluding empty lines and comments"""
        if not content:
            return 0
        
        # Get file extension to determine comment syntax
        ext = Path(file_path).suffix.lower()
        
        lines = content.split('\n')
        loc = 0
        in_block_comment = False
        
        # Define comment patterns based on language
        if ext in ['.py', '.rb']:
            line_comment = '#'
            block_start = '"""'
            block_end = '"""'
        elif ext in ['.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cs', '.go', '.swift', '.kt']:
            line_comment = '//'
            block_start = '/*'
            block_end = '*/'
        elif ext in ['.html', '.xml']:
            line_comment = None  # HTML doesn't have line comments
            block_start = '<!--'
            block_end = '-->'
        elif ext in ['.sql']:
            line_comment = '--'
            block_start = '/*'
            block_end = '*/'
        else:
            # Default comment syntax
            line_comment = '#'
            block_start = '/*'
            block_end = '*/'
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Handle block comments
            if block_start and block_end:
                if in_block_comment:
                    if block_end in line:
                        in_block_comment = False
                    continue
                elif block_start in line:
                    if block_end not in line[line.find(block_start) + len(block_start):]:
                        in_block_comment = True
                    continue
            
            # Handle line comments
            if line_comment and line.startswith(line_comment):
                continue
                
            # Count non-comment lines
            loc += 1
        
        return loc

    def analyze_repository_files(self, repo: Repository) -> Dict[str, Any]:
        """Analyze files in a repository with improved detection capabilities"""
        stats = {
            'total_files': 0,
            'total_loc': 0,
            'languages': defaultdict(int),
            'file_types': defaultdict(int),
            'has_docs': False,
            'has_readme': False,
            'has_tests': False,
            'test_files_count': 0,
            'has_cicd': False,
            'cicd_files': [],
            'dependency_files': [],
            'project_structure': defaultdict(int),
            'is_empty': False,  # New flag to track empty repositories
            'skipped_directories': set(),  # Track which directories were skipped
            'excluded_file_count': 0  # Count of excluded files
        }
        
        try:
            # Check for rate limits before making API calls
            self.check_rate_limit()
            
            # Get repository contents recursively
            contents = repo.get_contents("")
            files_to_process = []
            
            # Collect all files
            directories_seen = set()
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    try:
                        # Check if directory should be excluded
                        if self.is_excluded_path(file_content.path):
                            stats['skipped_directories'].add(file_content.path)
                            logger.debug(f"Skipping excluded directory: {file_content.path}")
                            continue
                        
                        if file_content.path not in directories_seen:
                            directories_seen.add(file_content.path)
                            contents.extend(repo.get_contents(file_content.path))
                            
                            # Update project structure statistics
                            path_parts = file_content.path.split('/')
                            if len(path_parts) == 1:  # Top-level directory
                                stats['project_structure'][path_parts[0]] += 1
                    except Exception as e:
                        logger.warning(f"Could not access directory {file_content.path}: {e}")
                        continue
                else:
                    # Skip files in excluded directories
                    if self.is_excluded_path(file_content.path):
                        stats['excluded_file_count'] += 1
                        logger.debug(f"Skipping file in excluded path: {file_content.path}")
                        continue
                        
                    files_to_process.append(file_content)
            
            # Process files with progress bar
            for file_content in tqdm(files_to_process, 
                                   desc=f"Analyzing {repo.name} files", 
                                   leave=False, 
                                   colour='cyan'):
                try:
                    file_path = file_content.path
                    stats['total_files'] += 1
                    
                    # Check for documentation
                    if ('readme' in file_path.lower() or 
                        file_path.lower().startswith('docs/') or
                        '/docs/' in file_path.lower() or
                        file_path.lower().endswith('.md')):
                        stats['has_docs'] = True
                        
                    # Specific check for README
                    if 'readme' in file_path.lower():
                        stats['has_readme'] = True
                    
                    # Check for tests
                    if self.is_test_file(file_path):
                        stats['has_tests'] = True
                        stats['test_files_count'] += 1
                    
                    # Check for CI/CD configuration
                    if self.is_cicd_file(file_path):
                        stats['has_cicd'] = True
                        stats['cicd_files'].append(file_path)
                    
                    # Check for dependency files
                    if self.is_config_file(file_path):
                        stats['dependency_files'].append(file_path)
                    
                    # Skip binary files for LOC counting
                    if self.is_binary_file(file_path):
                        stats['file_types']['Binary'] += 1
                        continue
                    
                    # Determine language and file type
                    language = self.get_file_language(file_path)
                    ext = Path(file_path).suffix.lower() or 'no_extension'
                    stats['file_types'][ext] += 1
                    
                    # Get file content for LOC counting
                    if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
                        try:
                            content = file_content.decoded_content.decode('utf-8', errors='ignore')
                            loc = self.count_lines_of_code(content, file_path)
                            stats['total_loc'] += loc
                            stats['languages'][language] += loc
                        except Exception as e:
                            logger.debug(f"Could not decode {file_path}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Error processing file {file_content.path}: {e}")
                    continue
        
        except GithubException as e:
            # Handle empty repository specifically
            if e.status == 404 and "This repository is empty" in str(e):
                logger.info(f"Repository {repo.name} is empty")
                stats['is_empty'] = True
            else:
                logger.error(f"GitHub API error analyzing repository {repo.name}: {e}")
        except RateLimitExceededException:
            logger.error(f"GitHub API rate limit exceeded while analyzing repository {repo.name}")
            # Wait and continue with partial results
            self.check_rate_limit()
        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")
        
        # Log summary of excluded directories
        if stats['skipped_directories']:
            logger.info(f"Skipped {len(stats['skipped_directories'])} directories and {stats['excluded_file_count']} files in {repo.name}")
            logger.debug(f"Skipped directories in {repo.name}: {', '.join(list(stats['skipped_directories'])[:5])}" + 
                       (f" and {len(stats['skipped_directories']) - 5} more..." if len(stats['skipped_directories']) > 5 else ""))
        
        # Remove the tracking set from final stats
        stats.pop('skipped_directories', None)
        
        return dict(stats)

    def calculate_scores(self, repo_stats: Dict[str, Any], repo: Repository) -> Dict[str, float]:
        """Calculate various quality scores for a repository"""
        scores = {
            'maintenance_score': 0.0,
            'popularity_score': 0.0,
            'code_quality_score': 0.0,
            'documentation_score': 0.0
        }
        
        # Maintenance score (0-100)
        maintenance_score = 0.0
        
        # Documentation (20 points)
        if repo_stats.get('has_docs', False):
            maintenance_score += 15
        if repo_stats.get('has_readme', False):
            maintenance_score += 5
        
        # Tests (20 points)
        if repo_stats.get('has_tests', False):
            test_count = repo_stats.get('test_files_count', 0)
            if test_count > 10:
                maintenance_score += 20
            elif test_count > 5:
                maintenance_score += 15
            elif test_count > 0:
                maintenance_score += 10
        
        # CI/CD (10 points)
        if repo_stats.get('has_cicd', False):
            maintenance_score += 10
        
        # Recent activity (20 points)
        if repo_stats.get('is_active', False):
            maintenance_score += 10
            
            # More points for higher activity
            commits_last_month = repo_stats.get('commits_last_month', 0)
            if commits_last_month > 10:
                maintenance_score += 10
            elif commits_last_month > 0:
                maintenance_score += commits_last_month
        
        # License (10 points)
        if repo.license:
            maintenance_score += 10
        
        # Issues management (10 points)
        try:
            if repo.open_issues_count < 10:
                maintenance_score += 10
            elif repo.open_issues_count < 50:
                maintenance_score += 5
        except:
            pass
        
        # Repository size and structure (10 points)
        if repo_stats.get('total_files', 0) > 5:
            maintenance_score += 5
        if len(repo_stats.get('dependency_files', [])) > 0:
            maintenance_score += 5
        
        scores['maintenance_score'] = min(maintenance_score, 100.0)
        
        # Popularity score (0-100)
        popularity_score = 0.0
        
        # Stars (up to 50 points)
        if repo.stargazers_count > 1000:
            popularity_score += 50
        elif repo.stargazers_count > 100:
            popularity_score += 30
        elif repo.stargazers_count > 10:
            popularity_score += 15
        elif repo.stargazers_count > 0:
            popularity_score += 5
        
        # Forks (up to 30 points)
        if repo.forks_count > 100:
            popularity_score += 30
        elif repo.forks_count > 10:
            popularity_score += 20
        elif repo.forks_count > 0:
            popularity_score += 10
        
        # Watchers and contributors (up to 20 points)
        contributors_count = repo_stats.get('contributors_count', 0)
        if contributors_count > 10:
            popularity_score += 10
        elif contributors_count > 1:
            popularity_score += 5
        
        if repo.watchers_count > 10:
            popularity_score += 10
        elif repo.watchers_count > 0:
            popularity_score += 5
        
        scores['popularity_score'] = min(popularity_score, 100.0)
        
        # Code quality score (0-100)
        code_quality_score = 0.0
        
        # Test coverage
        if repo_stats.get('has_tests', False):
            code_quality_score += 30
        
        # CI/CD
        if repo_stats.get('has_cicd', False):
            code_quality_score += 30
        
        # Code size and complexity
        if repo_stats.get('total_loc', 0) > 0:
            avg_loc = repo_stats.get('avg_loc_per_file', 0)
            if avg_loc > 0 and avg_loc < 300:  # Reasonable file size
                code_quality_score += 20
            elif avg_loc > 0:
                code_quality_score += 10
        
        # Documentation
        if repo_stats.get('has_docs', False):
            code_quality_score += 20
        
        scores['code_quality_score'] = min(code_quality_score, 100.0)
        
        # Documentation score (0-100)
        documentation_score = 0.0
        
        # README
        if repo_stats.get('has_readme', False):
            documentation_score += 40
        
        # Additional documentation
        if repo_stats.get('has_docs', False):
            documentation_score += 40
        
        # Wiki presence
        try:
            if repo.has_wiki:
                documentation_score += 20
        except:
            pass
        
        scores['documentation_score'] = min(documentation_score, 100.0)
        
        return scores

    def analyze_single_repository(self, repo: Repository) -> RepoStats:
        """Analyze a single repository and return detailed statistics"""
        logger.info(f"Analyzing repository: {repo.name}")
        
        try:
            # Get file analysis
            file_stats = self.analyze_repository_files(repo)
            
            # Check if repository is empty and handle accordingly
            is_empty = file_stats.get('is_empty', False)
            
            # Calculate derived statistics
            avg_loc = (file_stats['total_loc'] / file_stats['total_files'] 
                      if file_stats['total_files'] > 0 else 0)
            
            # Check if repository is active (commits in last N months)
            is_active = False
            last_commit_date = None
            commits_last_month = 0
            commits_last_year = 0
            commit_frequency = 0.0
            
            try:
                # Get commit history with rate limit awareness
                self.check_rate_limit()
                commits = list(repo.get_commits().get_page(0))
                
                if commits:
                    latest_commit = commits[0]
                    last_commit_date = latest_commit.commit.author.date
                    
                    # Ensure timezone-aware datetime comparison
                    # Create timezone-aware threshold date
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=self.config["INACTIVE_THRESHOLD_DAYS"])
                    
                    # Check activity within threshold using consistent timezone info
                    if last_commit_date is not None:
                        is_active = last_commit_date > inactive_threshold
                    
                    # Count recent commits
                    one_month_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=30)
                    one_year_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=365)
                    
                    # Get a sample of commits for frequency estimation
                    try:
                        recent_commits = list(repo.get_commits(since=one_year_ago))
                        
                        # Count commits in different periods
                        commits_last_month = sum(1 for c in recent_commits 
                                             if c.commit.author.date > one_month_ago)
                        commits_last_year = len(recent_commits)
                        
                        # Calculate average monthly commit frequency
                        if commits_last_year > 0:
                            # Make sure created_at is timezone-aware for consistent comparison
                            created_at = repo.created_at
                            created_at = ensure_utc(created_at)
                                
                            months_active = min(12, (datetime.now().replace(tzinfo=timezone.utc) - created_at).days / 30)
                            if months_active > 0:
                                commit_frequency = commits_last_year / months_active
                    except GithubException as e:
                        logger.warning(f"Could not get recent commits for {repo.name}: {e}")
            except GithubException as e:
                # Handle empty repository specifically
                if e.status == 409 and "Git Repository is empty" in str(e):
                    logger.info(f"Repository {repo.name} has no commits")
                    # Repository has no commits but we can still use pushed_at as a reference
                    last_commit_date = repo.pushed_at
                else:
                    logger.warning(f"Could not get commit info for {repo.name}: {e}")
                    last_commit_date = repo.pushed_at
                
                if last_commit_date:
                    # Ensure timezone awareness consistency
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=self.config["INACTIVE_THRESHOLD_DAYS"])
                    last_commit_date = ensure_utc(last_commit_date)
                    is_active = last_commit_date > inactive_threshold
            
            # Get contributors count
            contributors_count = 0
            try:
                contributors_count = repo.get_contributors().totalCount
            except GithubException as e:
                # Skip logging for empty repos as this is expected
                if not (e.status == 409 and "Git Repository is empty" in str(e)):
                    logger.warning(f"Could not get contributors for {repo.name}: {e}")
            
            # Get open PRs count
            open_prs = 0
            try:
                open_prs = repo.get_pulls(state='open').totalCount
            except Exception as e:
                logger.warning(f"Could not get PRs for {repo.name}: {e}")
            
            # Get closed issues count
            closed_issues = 0
            try:
                closed_issues = repo.get_issues(state='closed').totalCount
            except Exception as e:
                logger.warning(f"Could not get closed issues for {repo.name}: {e}")
            
            # Get languages from GitHub API
            github_languages = {}
            try:
                github_languages = repo.get_languages()
            except Exception as e:
                logger.warning(f"Could not get languages from API for {repo.name}: {e}")
            
            # Merge file analysis languages with GitHub API languages
            combined_languages = dict(file_stats['languages'])
            for lang, bytes_count in github_languages.items():
                if lang in combined_languages:
                    combined_languages[lang] = max(combined_languages[lang], bytes_count)
                else:
                    combined_languages[lang] = bytes_count
            
            # Calculate estimated test coverage percentage based on test files to total files ratio
            test_coverage_percentage = None
            if file_stats['has_tests'] and file_stats['total_files'] > 0:
                # Simple estimation based on test files count relative to codebase size
                # More sophisticated estimation would require actual test coverage data
                test_ratio = min(file_stats['test_files_count'] / max(1, file_stats['total_files'] - file_stats['test_files_count']), 1.0)
                # Scale to percentage with diminishing returns model
                # 0 tests = 0%, 10% test files = ~30% coverage, 20% test files = ~50% coverage, 50% test files = ~90% coverage
                test_coverage_percentage = min(100, 100 * (1 - (1 / (1 + 2 * test_ratio))))
            
            # Calculate all scores
            scores = self.calculate_scores(file_stats, repo)
            
            # Use ensure_utc consistently in this section
            # Ensure created_at and last_pushed are timezone-aware
            created_at = ensure_utc(repo.created_at)
                
            last_pushed = ensure_utc(repo.pushed_at)
            
            # Create base repository info
            base_info = BaseRepoInfo(
                name=repo.name,
                is_private=repo.private,
                default_branch=repo.default_branch,
                is_fork=repo.fork,
                is_archived=repo.archived,
                is_template=repo.is_template,
                created_at=created_at,
                last_pushed=last_pushed,
                description=repo.description,
                homepage=repo.homepage
            )
            
            # Create code stats
            code_stats = CodeStats(
                languages=combined_languages,
                total_files=file_stats['total_files'],
                total_loc=file_stats['total_loc'],
                avg_loc_per_file=avg_loc,
                file_types=dict(file_stats['file_types']),
                size_kb=repo.size,
                excluded_file_count=file_stats.get('excluded_file_count', 0),
                project_structure=file_stats.get('project_structure', {})
            )
            
            # Create quality indicators
            quality = QualityIndicators(
                has_docs=file_stats['has_docs'],
                has_readme=file_stats['has_readme'],
                has_tests=file_stats['has_tests'],
                test_files_count=file_stats['test_files_count'],
                test_coverage_percentage=test_coverage_percentage,
                has_cicd=file_stats.get('has_cicd', False),
                cicd_files=file_stats.get('cicd_files', []),
                dependency_files=file_stats['dependency_files']
            )
            
            # Create activity metrics
            activity = ActivityMetrics(
                last_commit_date=last_commit_date or repo.pushed_at,
                is_active=is_active,
                commit_frequency=commit_frequency,
                commits_last_month=commits_last_month,
                commits_last_year=commits_last_year
            )
            
            # Create community metrics
            community = CommunityMetrics(
                license_name=repo.license.name if repo.license else None,
                license_spdx_id=repo.license.spdx_id if repo.license else None,
                contributors_count=contributors_count,
                open_issues=repo.open_issues_count,
                open_prs=open_prs,
                closed_issues=closed_issues,
                topics=repo.topics,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                watchers=repo.watchers_count
            )
            
            # Create analysis scores
            scores_obj = AnalysisScores(
                maintenance_score=scores['maintenance_score'],
                popularity_score=scores['popularity_score'],
                code_quality_score=scores['code_quality_score'],
                documentation_score=scores['documentation_score']
            )
            
            # Create RepoStats object
            repo_stats = RepoStats(
                base_info=base_info,
                code_stats=code_stats,
                quality=quality,
                activity=activity,
                community=community,
                scores=scores_obj
            )
            
            # Add anomaly for empty repository
            if is_empty:
                repo_stats.add_anomaly("Empty repository with no files")
            
            # Calculate additional derived metrics
            repo_stats.calculate_primary_language()
            repo_stats.detect_monorepo()
            
            # Identify anomalies
            self.detect_anomalies(repo_stats)
            
            return repo_stats
            
        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")
            # Return minimal stats on error with proper object structure
            base_info = BaseRepoInfo(
                name=repo.name,
                is_private=getattr(repo, 'private', False),
                default_branch=getattr(repo, 'default_branch', 'unknown'),
                is_fork=getattr(repo, 'fork', False),
                is_archived=getattr(repo, 'archived', False),
                is_template=getattr(repo, 'is_template', False),
                created_at=getattr(repo, 'created_at', datetime.now().replace(tzinfo=timezone.utc)),
                last_pushed=getattr(repo, 'pushed_at', datetime.now().replace(tzinfo=timezone.utc)),
                description=getattr(repo, 'description', None),
                homepage=getattr(repo, 'homepage', None)
            )
            return RepoStats(base_info=base_info)

    def detect_anomalies(self, repo_stats: RepoStats) -> None:
        """Detect anomalies in repository data"""
        # Large repo without documentation
        if repo_stats.code_stats.total_loc > self.config["LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.quality.has_docs:
            repo_stats.add_anomaly("Large repository without documentation")
            
        # Large repo without tests
        if repo_stats.code_stats.total_loc > self.config["LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.quality.has_tests:
            repo_stats.add_anomaly("Large repository without tests")
            
        # Popular repo without docs
        if repo_stats.community.stars > 10 and not repo_stats.quality.has_docs:
            repo_stats.add_anomaly("Popular repository without documentation")
            
        # Many open issues
        if repo_stats.community.open_issues > 20 and not repo_stats.activity.is_active:
            repo_stats.add_anomaly("Many open issues but repository is inactive")
            
        # Stale repository with stars
        if not repo_stats.activity.is_active and repo_stats.community.stars > 10:
            repo_stats.add_anomaly("Popular repository appears to be abandoned")
            
        # Project with code but no license
        if repo_stats.code_stats.total_loc > 1000 and not repo_stats.community.license_name:
            repo_stats.add_anomaly("Substantial code without license")
            
        # Imbalanced test coverage
        if repo_stats.quality.has_tests and repo_stats.quality.test_files_count < repo_stats.code_stats.total_files * 0.05:
            repo_stats.add_anomaly("Low test coverage ratio")
            
        # Missing CI/CD in active project
        if repo_stats.activity.is_active and repo_stats.code_stats.total_loc > 1000 and not repo_stats.quality.has_cicd:
            repo_stats.add_anomaly("Active project without CI/CD configuration")
            
        # Old repository without recent activity
        if repo_stats.base_info.created_at and repo_stats.activity.last_commit_date:
            now = datetime.now().replace(tzinfo=timezone.utc)
            created_at = ensure_utc(repo_stats.base_info.created_at)
            last_commit = ensure_utc(repo_stats.activity.last_commit_date)
            
            years_since_created = (now - created_at).days / 365.25
            months_since_last_commit = (now - last_commit).days / 30
            
            if years_since_created > 3 and months_since_last_commit > 12:
                repo_stats.add_anomaly("Old repository without updates in over a year")

    def is_excluded_path(self, file_path: str) -> bool:
        """Check if a file path should be excluded from analysis"""
        path_parts = file_path.split('/')
        
        # Check if any part of the path matches excluded directories
        for part in path_parts:
            if part in EXCLUDED_DIRECTORIES:
                return True
                
        # Also check for specific file patterns to exclude
        file_name = path_parts[-1] if path_parts else ""
        if any(file_name.endswith(ext) for ext in BINARY_EXTENSIONS):
            return True
        
        return False
