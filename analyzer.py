"""
GitHub Repository Analyzer Module

This module provides detailed analysis of GitHub repositories.
It handles fetching repository data, analyzing code quality, activity metrics,
and community engagement.
"""

import concurrent.futures
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from github.GithubException import GithubException, RateLimitExceededException
from github.Repository import Repository
from tqdm.auto import tqdm

from config import BINARY_EXTENSIONS, CICD_FILES, CONFIG_FILES, EXCLUDED_DIRECTORIES, LANGUAGE_EXTENSIONS, \
    SPECIAL_FILENAMES, PACKAGE_FILES, DEPLOYMENT_FILES, RELEASE_FILES, Configuration
from console import rprint, logger, RateLimitDisplay
from models import RepoStats, BaseRepoInfo, CodeStats, QualityIndicators, ActivityMetrics, CommunityMetrics, \
    AnalysisScores
from utilities import ensure_utc

# Initialize the rate limit display
rate_display = RateLimitDisplay()


def is_binary_file(file_path: str) -> bool:
    """Check if file is binary"""
    ext = Path(file_path).suffix.lower()
    return ext in BINARY_EXTENSIONS


def is_deployment_file(file_path: str) -> bool:
    """Check if file is related to deployment"""
    filename = Path(file_path).name.lower()

    # Check against DEPLOYMENT_FILES set
    if filename in DEPLOYMENT_FILES or any(pattern in file_path.lower() for pattern in DEPLOYMENT_FILES):
        return True

    # Check if it's in the special filenames dictionary and is a deployment file
    base_filename = Path(file_path).name
    if base_filename in SPECIAL_FILENAMES:
        file_type = SPECIAL_FILENAMES[base_filename]
        if any(deploy_type in file_type for deploy_type in
               ['Docker', 'Kubernetes', 'Deploy', 'Terraform']):
            return True

    return False


def is_release_file(file_path: str) -> bool:
    """Check if file is related to releases"""
    filename = Path(file_path).name.lower()

    # Check against RELEASE_FILES set
    if filename in RELEASE_FILES or any(pattern in file_path.lower() for pattern in RELEASE_FILES):
        return True

    # Check for specific release patterns
    release_patterns = [
        'changelog', 'changes', 'releases', 'version', 'semver',
        'semantic-release', '.github/releases'
    ]
    if any(pattern in file_path.lower() for pattern in release_patterns):
        return True

    return False


def is_test_file(file_path: str) -> bool:
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


def is_package_file(file_path: str) -> bool:
    """Check if file is related to package management"""
    filename = Path(file_path).name.lower()

    # Check against PACKAGE_FILES set
    if filename in PACKAGE_FILES or any(pattern in file_path.lower() for pattern in PACKAGE_FILES):
        return True

    # Check if it's in the special filenames dictionary and is a package file
    base_filename = Path(file_path).name
    if base_filename in SPECIAL_FILENAMES:
        file_type = SPECIAL_FILENAMES[base_filename]
        if any(pkg_type in file_type for pkg_type in
               ['TOML', 'JSON', 'Package', 'Requirements', 'Gemfile', 'Cargo']):
            return True

    return False


def is_cicd_file(file_path: str) -> bool:
    """Check if a file is likely related to CI/CD pipelines."""
    file_path_lower = file_path.lower()

    # Check for common CI/CD directory patterns
    ci_cd_patterns = ['.github/workflows', '.circleci', '.travis', 'jenkins', 'gitlab-ci']
    for pattern in ci_cd_patterns:
        if pattern in file_path_lower:
            return True

    # Check special filenames for CI/CD related files
    base_filename = Path(file_path).name
    if base_filename in SPECIAL_FILENAMES:
        file_type = SPECIAL_FILENAMES[base_filename]
        if any(ci_type in file_type for ci_type in
               ['Docker', 'Jenkinsfile', 'YAML', 'CI', 'CD']):
            return True

    # Check for common CI/CD file names without extensions
    ci_cd_filenames = {'dockerfile', 'jenkinsfile', 'vagrantfile', 'procfile'}
    if base_filename.lower() in ci_cd_filenames:
        return True

    return False


class CodeAnalyzer:
    """
    A comprehensive class for analyzing code across multiple languages.
    
    This class provides methods to count lines of code while handling
    language-specific comment styles, blank lines, and special file types.
    """
    
    def __init__(self):
        """Initialize the CodeAnalyzer with language-specific comment patterns."""
        # Language comment pattern definitions
        self.language_patterns = {
            # Python-style
            'python': {'line_comment': '#', 'block_start': '"""', 'block_end': '"""', 'alt_block_start': "'''", 'alt_block_end': "'''"},
            'ruby': {'line_comment': '#', 'block_start': '=begin', 'block_end': '=end'},
            'perl': {'line_comment': '#', 'block_start': '=pod', 'block_end': '=cut'},
            'r': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'yaml': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'toml': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'shell': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'bash': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'fish': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'zsh': {'line_comment': '#', 'block_start': None, 'block_end': None},
            'powershell': {'line_comment': '#', 'block_start': '<#', 'block_end': '#>'},
            'makefile': {'line_comment': '#', 'block_start': None, 'block_end': None},
            
            # C-style
            'c': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'cpp': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'java': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'javascript': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'typescript': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'c#': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'go': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'swift': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'kotlin': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'scala': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'rust': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'dart': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'php': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'css': {'line_comment': None, 'block_start': '/*', 'block_end': '*/'},
            'scss': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'less': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            'objc': {'line_comment': '//', 'block_start': '/*', 'block_end': '*/'},
            
            # HTML/XML style
            'html': {'line_comment': None, 'block_start': '<!--', 'block_end': '-->'},
            'xml': {'line_comment': None, 'block_start': '<!--', 'block_end': '-->'},
            'svg': {'line_comment': None, 'block_start': '<!--', 'block_end': '-->'},
            
            # SQL style
            'sql': {'line_comment': '--', 'block_start': '/*', 'block_end': '*/'},
            
            # Lisp style
            'lisp': {'line_comment': ';', 'block_start': None, 'block_end': None},
            'clojure': {'line_comment': ';', 'block_start': None, 'block_end': None},
            
            # Haskell style
            'haskell': {'line_comment': '--', 'block_start': '{-', 'block_end': '-}'},
            
            # Lua style
            'lua': {'line_comment': '--', 'block_start': '--[[', 'block_end': ']]'},
            
            # Fortran style
            'fortran': {'line_comment': '!', 'block_start': None, 'block_end': None},
            
            # Ada style
            'ada': {'line_comment': '--', 'block_start': None, 'block_end': None},
            
            # LaTeX style
            'latex': {'line_comment': '%', 'block_start': None, 'block_end': None},
            
            # Julia style
            'julia': {'line_comment': '#', 'block_start': '#=', 'block_end': '=#'},
            
            # Other languages
            'markdown': {'line_comment': None, 'block_start': None, 'block_end': None},
            'text': {'line_comment': None, 'block_start': None, 'block_end': None},
        }
        
        # Map file extensions to language types
        self.extension_to_language = {
            # Python
            '.py': 'python', '.pyx': 'python', '.pyd': 'python', '.pyi': 'python',
            '.ipynb': 'jupyter',  # Special handling for Jupyter notebooks
            
            # JavaScript/TypeScript
            '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
            '.ts': 'typescript', '.tsx': 'typescript', '.jsx': 'javascript',
            
            # Web
            '.html': 'html', '.htm': 'html', '.xhtml': 'html',
            '.css': 'css', '.scss': 'scss', '.sass': 'scss', '.less': 'less',
            '.svg': 'svg', '.xml': 'xml',
            
            # JVM languages
            '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin',
            '.scala': 'scala', '.sc': 'scala',
            '.groovy': 'java', '.clj': 'clojure', '.cljs': 'clojure',
            
            # C-family
            '.c': 'c', '.h': 'c',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
            '.hpp': 'cpp', '.hxx': 'cpp', '.hh': 'cpp',
            '.cs': 'c#',
            
            # Other programming languages
            '.rb': 'ruby', '.erb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php', '.phtml': 'php',
            '.swift': 'swift',
            '.m': 'objc', '.mm': 'objc',  # Objective-C
            '.lua': 'lua',
            '.hs': 'haskell', '.lhs': 'haskell',
            '.pl': 'perl', '.pm': 'perl',
            '.jl': 'julia',
            '.r': 'r', '.rmd': 'r',
            '.dart': 'dart',
            
            # Shell and scripting
            '.sh': 'shell', '.bash': 'bash', '.zsh': 'zsh', '.fish': 'fish',
            '.ps1': 'powershell', '.psm1': 'powershell', '.psd1': 'powershell',
            
            # Configuration and data
            '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
            '.toml': 'toml', '.ini': 'text',
            '.sql': 'sql',
            
            # Documentation
            '.md': 'markdown', '.markdown': 'markdown',
            '.tex': 'latex', '.ltx': 'latex', '.latex': 'latex',
            '.txt': 'text',
        }
    
    def get_language_from_file(self, file_path: str) -> str:
        """
        Determine the language type based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            The language identifier or 'text' if unknown
        """
        ext = Path(file_path).suffix.lower()
        return self.extension_to_language.get(ext, 'text')
    
    def count_lines_of_code(self, content: str, file_path: str) -> int:
        """
        Count lines of code, excluding empty lines and comments.
        
        Args:
            content: The content of the file as a string
            file_path: Path to the file (for language detection)
            
        Returns:
            Number of non-blank, non-comment lines of code
        """
        if not content:
            return 0
            
        # Handle binary files
        if is_binary_file(file_path):
            return 0
            
        # Get language type from file extension
        language = self.get_language_from_file(file_path)
        
        # Special handling for Jupyter notebooks
        if language.lower() == 'jupyter':
            return self._count_jupyter_notebook_loc(content, file_path)
            
        # Regular file handling
        return self._count_standard_file_loc(content, language)
    
    def _count_standard_file_loc(self, content: str, language: str) -> int:
        """
        Count lines of code in a standard text-based file.
        
        Args:
            content: File content as string
            language: The programming language identifier
            
        Returns:
            Number of non-blank, non-comment lines
        """
        # Get comment patterns for this language
        patterns = self.language_patterns.get(language, {'line_comment': None, 'block_start': None, 'block_end': None})
        
        lines = content.split('\n')
        loc = 0
        in_block_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
                
            # Check if we're in a block comment
            if in_block_comment:
                if patterns['block_end'] and patterns['block_end'] in stripped:
                    # Look for the end of the block comment
                    end_pos = stripped.find(patterns['block_end'])
                    # If there's code after the block comment on the same line
                    rest = stripped[end_pos + len(patterns['block_end']):].strip()
                    in_block_comment = False
                    
                    # Count line if there's code after the block comment
                    if rest and not (patterns['line_comment'] and rest.startswith(patterns['line_comment'])):
                        loc += 1
                continue
                
            # Check for the start of a block comment
            if patterns['block_start'] and patterns['block_start'] in stripped:
                start_pos = stripped.find(patterns['block_start'])
                
                # Check if there's code before the comment
                before = stripped[:start_pos].strip()
                if before:
                    loc += 1
                
                # Check if the block comment ends on the same line
                if patterns['block_end'] and patterns['block_end'] in stripped[start_pos + len(patterns['block_start']):]:
                    end_pos = stripped.find(patterns['block_end'], start_pos + len(patterns['block_start']))
                    # If there's code after the block comment on the same line
                    after = stripped[end_pos + len(patterns['block_end']):].strip()
                    if after and not (patterns['line_comment'] and after.startswith(patterns['line_comment'])):
                        loc += 1
                else:
                    in_block_comment = True
                continue
                
            # Check for alternative block comment style (like Python's triple quotes)
            if 'alt_block_start' in patterns and patterns['alt_block_start'] and patterns['alt_block_start'] in stripped:
                start_pos = stripped.find(patterns['alt_block_start'])
                
                # Check if there's code before the comment
                before = stripped[:start_pos].strip()
                if before:
                    loc += 1
                
                # Check if the block comment ends on the same line
                if patterns['alt_block_end'] and patterns['alt_block_end'] in stripped[start_pos + len(patterns['alt_block_start']):]:
                    end_pos = stripped.find(patterns['alt_block_end'], start_pos + len(patterns['alt_block_start']))
                    # If there's code after the block comment on the same line
                    after = stripped[end_pos + len(patterns['alt_block_end']):].strip()
                    if after and not (patterns['line_comment'] and after.startswith(patterns['line_comment'])):
                        loc += 1
                else:
                    in_block_comment = True
                continue
            
            # Check for line comments
            if patterns['line_comment'] and stripped.startswith(patterns['line_comment']):
                continue
                
            # If we reach here, the line contains code
            loc += 1
            
        return loc
    
    def _count_jupyter_notebook_loc(self, content: str, file_path: str) -> int:
        """
        Count lines of code in a Jupyter notebook.
        
        Args:
            content: File content as string (should be JSON)
            file_path: Path to the notebook file
            
        Returns:
            Number of actual executable lines of code
        """
        try:
            import json
            notebook_data = json.loads(content)
            
            actual_loc = 0
            
            # Process notebook cells
            cells = notebook_data.get('cells', [])
            
            for cell in cells:
                cell_type = cell.get('cell_type')
                source = cell.get('source', [])
                
                # Only count code cells
                if cell_type != 'code':
                    continue
                
                # The 'source' can be a list of strings or a single string
                if isinstance(source, str):
                    lines = source.splitlines()
                else:
                    # Flatten and remove trailing newlines
                    lines = [line.rstrip('\n') for line in source]
                
                # Count non-blank, non-comment lines
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith('#'):
                        actual_loc += 1
            
            return actual_loc
            
        except json.JSONDecodeError:
            # If we can't parse as JSON, fall back to counting Python-style code
            return self._count_standard_file_loc(content, 'python')
        except Exception as e:
            # If any other error occurs, return 0
            logger.warning(f"Error parsing Jupyter notebook {file_path}: {e}")
            return 0


# Create a singleton instance of the analyzer
code_analyzer = CodeAnalyzer()


def count_lines_of_code(content: str, file_path: str) -> int:
    """
    Count non-blank lines of code in a file.
    
    Args:
        content: File content as string
        file_path: Path to the file (for language detection)
        
    Returns:
        Number of non-blank lines of code
    """
    # Use the code analyzer instance to count lines
    return code_analyzer.count_lines_of_code(content, file_path)


def is_config_file(file_path: str) -> bool:
    """
    Check if a file is likely a configuration file based on its name or extension.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is likely a config file, False otherwise
    """
    filename = Path(file_path).name.lower()

    # First check against the CONFIG_FILES set
    if filename in CONFIG_FILES:
        return True

    # Then check if it's in the special filenames dictionary and is a config file
    base_filename = Path(file_path).name
    if base_filename in SPECIAL_FILENAMES:
        # Check if the file type indicates it's a configuration file
        file_type = SPECIAL_FILENAMES[base_filename]
        if any(config_type in file_type for config_type in
               ['JSON', 'YAML', 'TOML', 'INI', 'XML', 'Config']):
            return True

    return False


class GithubAnalyzer:
    """Class responsible for analyzing GitHub repositories"""

    def __init__(self, github, username: str, config: Optional[Configuration] = None):
        """Initialize the analyzer with GitHub client, username and configuration"""
        self.github = github
        self.username = username
        self.config = config
        self.rate_display = rate_display
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
                    logger.warning(
                        f"GitHub API rate limit low ({remaining} left). Waiting {wait_time:.1f}s until reset.")
                    self._visualize_wait(wait_time, "Rate limit cooldown")
        except Exception as e:
            logger.warning(f"Could not check rate limit: {e}")

    @staticmethod
    def _visualize_wait(wait_time: float, desc: str):
        """Display a progress bar for wait periods"""
        # Cap very long waits to show reasonable progress
        if wait_time > 3600:  # If more than an hour
            logger.warning(f"Long wait time detected ({wait_time:.1f}s). Showing progress for first hour.")
            rprint(
                f"[bold yellow]⚠️ GitHub API requires a long cooldown period ({wait_time / 60:.1f} minutes)[/bold yellow]")
            rprint(f"[dim]The script will automatically continue after the wait period.[/dim]")
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
                rprint(
                    f"[blue]📋 Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories[/blue]")

            # Initialize GitHub user with rate limit check
            self.check_rate_limit()

            # Check if we're analyzing the authenticated user (to access private repos)
            auth_user = self.github.get_user()
            if self.username == auth_user.login:
                # If analyzing ourselves, use the authenticated user to get all repos including private
                logger.info(f"Analyzing authenticated user {self.username}, will include private repositories")
                self.user = auth_user
            else:
                # Otherwise get the specified user (which will only return public repos)
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
            rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
            self.rate_display.display_once()  # Use our interactive display
            rprint("[bold]-------------------------------[/bold]")

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

                        # Periodically show rate limit status
                        if repo_counter % 5 == 0 or repo_counter == 1 or len(batch) == batch_size:
                            rprint("\n[bold]--- Current API Rate Status ---[/bold]")
                            self.rate_display.display_once()
                            rprint("[bold]-------------------------------[/bold]")

                        # Check if we need to checkpoint before processing this batch
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in
                                                                                                  newly_analyzed_repos],
                                                                remaining_repos + batch):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats

                        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            # Submit all tasks for this batch
                            future_to_repo = {executor.submit(self.analyze_single_repository, repo): repo for repo in
                                              batch}

                            # Process results as they complete
                            for future in concurrent.futures.as_completed(future_to_repo):
                                repo = future_to_repo[future]
                                try:
                                    repo_stats = future.result()
                                    all_stats.append(repo_stats)
                                    newly_analyzed_repos.append(repo)
                                    analyzed_repo_names.append(repo.name)
                                    pbar.update(1)
                                except Exception as e:
                                    logger.error(f"Failed to analyze {repo.name}: {e}")

                # Final checkpoint after all batches complete
                if self.config["ENABLE_CHECKPOINTING"] and newly_analyzed_repos:
                    self.save_checkpoint(all_stats, analyzed_repo_names, remaining_repos)
            else:
                # Sequential processing for single worker or single repo case
                with tqdm(total=total_repos, initial=len(all_stats),
                          desc="Analyzing repositories", leave=True, colour='green') as pbar:

                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")

                    for repo in repos_to_analyze:
                        # Periodically check and display rate limit status
                        if len(newly_analyzed_repos) % 5 == 0 or len(newly_analyzed_repos) == 0:
                            rprint("\n[bold]--- Current API Rate Status ---[/bold]")
                            self.rate_display.display_once()
                            rprint("[bold]-------------------------------[/bold]")

                        # Check if we need to checkpoint
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names,
                                                                repos_to_analyze[repos_to_analyze.index(repo):]):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats

                        try:
                            repo_stats = self.analyze_single_repository(repo)
                            all_stats.append(repo_stats)
                            newly_analyzed_repos.append(repo)
                            analyzed_repo_names.append(repo.name)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to analyze {repo.name}: {e}")

                # Final checkpoint after all repos complete
                if self.config["ENABLE_CHECKPOINTING"] and newly_analyzed_repos:
                    self.save_checkpoint(all_stats, analyzed_repo_names, [])

            # Final rate limit status display
            rprint("\n[bold]--- Final API Rate Status ---[/bold]")
            self.rate_display.display_once()
            rprint("[bold]----------------------------[/bold]")

            # If all repositories were successfully analyzed, clean up the checkpoint file
            if self.config["ENABLE_CHECKPOINTING"] and not repos_to_analyze:
                try:
                    Path(self.config["CHECKPOINT_FILE"]).unlink(missing_ok=True)
                except:
                    pass  # Silently ignore any issues with checkpoint deletion

            logger.info(f"Successfully analyzed {len(all_stats)} repositories")
            return all_stats

        except RateLimitExceededException:
            logger.error("GitHub API rate limit exceeded during repository listing")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats

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

    def save_checkpoint(self, all_stats: List[RepoStats], analyzed_repo_names: List[str],
                        remaining_repos: List[Repository]) -> None:
        """Save checkpoint data during analysis"""
        self.checkpoint.save(all_stats, analyzed_repo_names, remaining_repos)

    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint data from previous analysis"""
        return self.checkpoint.load()

    @staticmethod
    def get_file_language(file_path: str) -> str:
        """Determine language from file extension or special filename"""
        path_obj = Path(file_path)
        ext = path_obj.suffix.lower()

        # If file has an extension, check language mappings
        if ext:
            return LANGUAGE_EXTENSIONS.get(ext, 'Other')

        # No extension, check if it's a known special filename
        filename = path_obj.name
        if filename in SPECIAL_FILENAMES:
            return SPECIAL_FILENAMES[filename]

        # Check if it's a special dot file (like .gitignore)
        if filename.startswith('.') and filename in SPECIAL_FILENAMES:
            return SPECIAL_FILENAMES[filename]

        # For truly unknown files
        return 'Other'

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
            'excluded_file_count': 0,  # Count of excluded files

            # Additional tracking for new metrics
            'has_packages': False,
            'package_files': [],
            'has_deployments': False,
            'deployment_files': [],
            'has_releases': False,
            'release_files': [],
            'docs_files': [],
            'readme_file': None,
            'readme_content': None,
            'readme_line_count': 0
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
                    is_doc = False
                    if ('readme' in file_path.lower() or
                            file_path.lower().startswith('docs/') or
                            '/docs/' in file_path.lower() or
                            file_path.lower().endswith('.md')):
                        stats['has_docs'] = True
                        is_doc = True
                        stats['docs_files'].append(file_path)

                    # Specific check for README
                    if 'readme' in file_path.lower():
                        stats['has_readme'] = True
                        stats['readme_file'] = file_path

                        # Get README content for comprehensiveness analysis
                        try:
                            if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
                                readme_content = file_content.decoded_content.decode('utf-8', errors='ignore')
                                stats['readme_content'] = readme_content
                                stats['readme_line_count'] = len(readme_content.splitlines())
                        except Exception as e:
                            logger.debug(f"Could not decode README {file_path}: {e}")

                    # Check for tests
                    if is_test_file(file_path):
                        stats['has_tests'] = True
                        stats['test_files_count'] += 1

                    # Check for CI/CD configuration
                    if is_cicd_file(file_path):
                        stats['has_cicd'] = True
                        stats['cicd_files'].append(file_path)

                    # Check for dependency files
                    if is_config_file(file_path):
                        stats['dependency_files'].append(file_path)

                    # Check for package files
                    if is_package_file(file_path):
                        stats['has_packages'] = True
                        stats['package_files'].append(file_path)

                    # Check for deployment files
                    if is_deployment_file(file_path):
                        stats['has_deployments'] = True
                        stats['deployment_files'].append(file_path)

                    # Check for release files
                    if is_release_file(file_path):
                        stats['has_releases'] = True
                        stats['release_files'].append(file_path)

                    # Skip binary files for LOC counting
                    if is_binary_file(file_path):
                        stats['file_types']['Binary'] += 1
                        continue

                    # Determine language and file type
                    language = self.get_file_language(file_path)

                    # Get file extension or special category for file type
                    path_obj = Path(file_path)
                    filename = path_obj.name
                    ext = path_obj.suffix.lower()

                    # Record file type - either by extension or special filename
                    if ext:
                        stats['file_types'][ext] += 1
                    elif filename in SPECIAL_FILENAMES:
                        # Use filename as file type for files without extensions
                        stats['file_types'][f"no_ext_{filename}"] += 1
                    elif filename.startswith('.') and filename in SPECIAL_FILENAMES:
                        # Handle dot files like .gitignore
                        stats['file_types'][filename] += 1
                    else:
                        # Truly unknown files
                        stats['file_types']['no_extension'] += 1

                    # Get file content for LOC counting
                    if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
                        try:
                            content = file_content.decoded_content.decode('utf-8', errors='ignore')
                            loc = count_lines_of_code(content, file_path)
                            stats['total_loc'] += loc
                            stats['languages'][language] += loc
                        except Exception as e:
                            logger.debug(f"Could not decode {file_path}: {e}")

                except Exception as e:
                    logger.warning(f"Error processing file {file_content.path}: {e}")
                    continue

            # Process additional metadata

            # Check for GitHub releases
            try:
                releases = list(repo.get_releases())
                if releases:
                    stats['has_releases'] = True
                    stats['release_count'] = len(releases)
            except Exception as e:
                logger.debug(f"Could not get releases for {repo.name}: {e}")

            # Categorize documentation size
            docs_files_count = len(stats['docs_files'])
            stats['docs_files_count'] = docs_files_count

            if docs_files_count == 0:
                stats['docs_size_category'] = "None"
            elif docs_files_count <= 2:
                stats['docs_size_category'] = "Small"
            elif docs_files_count <= 10:
                stats['docs_size_category'] = "Intermediate"
            else:
                stats['docs_size_category'] = "Big"

            # Categorize README comprehensiveness
            readme_lines = stats['readme_line_count']
            if readme_lines == 0:
                stats['readme_comprehensiveness'] = "None"
            elif readme_lines < 20:
                stats['readme_comprehensiveness'] = "Small"
            elif readme_lines < 100:
                stats['readme_comprehensiveness'] = "Good"
            else:
                stats['readme_comprehensiveness'] = "Comprehensive"

            # Clean up large content we don't need to keep
            stats.pop('readme_content', None)

        except RateLimitExceededException:
            logger.error(f"GitHub API rate limit exceeded while analyzing repository {repo.name}")
            # Wait and continue with partial results
            self.check_rate_limit()
        except GithubException as e:
            # Handle empty repository specifically
            if e.status == 404 and "This repository is empty" in str(e):
                logger.info(f"Repository {repo.name} is empty")
                stats['is_empty'] = True
            else:
                logger.error(f"GitHub API error analyzing repository {repo.name}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")

        # Log summary of excluded directories
        if stats['skipped_directories']:
            logger.info(
                f"Skipped {len(stats['skipped_directories'])} directories and {stats['excluded_file_count']} files in {repo.name}")
            logger.debug(f"Skipped directories in {repo.name}: {', '.join(list(stats['skipped_directories'])[:5])}" +
                         (f" and {len(stats['skipped_directories']) - 5} more..." if len(
                             stats['skipped_directories']) > 5 else ""))

        # Remove the tracking set from final stats
        stats.pop('skipped_directories', None)

        return dict(stats)

    @staticmethod
    def calculate_scores(repo_stats: Dict[str, Any], repo: Repository) -> Dict[str, float]:
        """Calculate various quality scores for a repository"""
        scores = {
            'maintenance_score': 0.0,
            'popularity_score': 0.0,
            'code_quality_score': 0.0,
            'documentation_score': 0.0
        }

        # Maintenance score (0-100)
        maintenance_score = 0.0

        # Documentation (15 points)
        if repo_stats.get('has_docs', False):
            # Add points based on documentation size
            docs_size = repo_stats.get('docs_size_category', "None")
            if docs_size == "Big":
                maintenance_score += 15
            elif docs_size == "Intermediate":
                maintenance_score += 10
            elif docs_size == "Small":
                maintenance_score += 5

        # README quality (10 points)
        if repo_stats.get('has_readme', False):
            # Add points based on README comprehensiveness
            readme_quality = repo_stats.get('readme_comprehensiveness', "None")
            if readme_quality == "Comprehensive":
                maintenance_score += 10
            elif readme_quality == "Good":
                maintenance_score += 7
            elif readme_quality == "Small":
                maintenance_score += 3

        # Tests (15 points)
        if repo_stats.get('has_tests', False):
            test_count = repo_stats.get('test_files_count', 0)
            if test_count > 10:
                maintenance_score += 15
            elif test_count > 5:
                maintenance_score += 10
            elif test_count > 0:
                maintenance_score += 5

        # CI/CD (10 points)
        if repo_stats.get('has_cicd', False):
            maintenance_score += 10

        # Package management (5 points)
        if repo_stats.get('has_packages', False):
            maintenance_score += 5

        # Deployment configuration (5 points)
        if repo_stats.get('has_deployments', False):
            maintenance_score += 5

        # Releases (5 points)
        if repo_stats.get('has_releases', False):
            release_count = repo_stats.get('release_count', 0)
            if release_count > 5:
                maintenance_score += 5
            else:
                maintenance_score += min(release_count, 5)

        # Recent activity (15 points)
        if repo_stats.get('is_active', False):
            maintenance_score += 10

            # More points for higher activity
            commits_last_month = repo_stats.get('commits_last_month', 0)
            if commits_last_month > 10:
                maintenance_score += 5
            elif commits_last_month > 0:
                maintenance_score += commits_last_month / 2  # Up to 5 points

        # License (5 points)
        if repo.license:
            maintenance_score += 5

        # Issues management (5 points)
        try:
            if repo.open_issues_count < 10:
                maintenance_score += 5
            elif repo.open_issues_count < 50:
                maintenance_score += 3
        except:
            pass

        # Repository size and structure (5 points)
        if repo_stats.get('total_files', 0) > 5:
            maintenance_score += 3
        if len(repo_stats.get('dependency_files', [])) > 0:
            maintenance_score += 2

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

        # Test coverage (up to 30 points)
        if repo_stats.get('has_tests', False):
            test_count = repo_stats.get('test_files_count', 0)
            total_files = repo_stats.get('total_files', 0)
            if total_files > 0:
                test_ratio = min(test_count / max(1, total_files - test_count), 1.0)
                # Up to 30 points based on test ratio
                code_quality_score += min(30, int(30 * test_ratio))
            else:
                code_quality_score += 10  # Some tests are better than none

        # CI/CD (up to 20 points)
        if repo_stats.get('has_cicd', False):
            code_quality_score += 20

        # Package management (up to 10 points)
        if repo_stats.get('has_packages', False):
            package_files_count = len(repo_stats.get('package_files', []))
            if package_files_count > 3:
                code_quality_score += 10
            else:
                code_quality_score += package_files_count * 3

        # Code size and complexity (up to 20 points)
        if repo_stats.get('total_loc', 0) > 0:
            avg_loc = repo_stats.get('avg_loc_per_file', 0)
            if 0 < avg_loc < 300:  # Reasonable file size
                code_quality_score += 20
            elif avg_loc > 0:
                code_quality_score += 10

        # Documentation (up to 20 points)
        if repo_stats.get('has_docs', False):
            docs_category = repo_stats.get('docs_size_category', "None")
            if docs_category == "Big":
                code_quality_score += 20
            elif docs_category == "Intermediate":
                code_quality_score += 15
            elif docs_category == "Small":
                code_quality_score += 10

        scores['code_quality_score'] = min(code_quality_score, 100.0)

        # Documentation score (0-100)
        documentation_score = 0.0

        # README quality (up to 40 points)
        if repo_stats.get('has_readme', False):
            readme_quality = repo_stats.get('readme_comprehensiveness', "None")
            if readme_quality == "Comprehensive":
                documentation_score += 40
            elif readme_quality == "Good":
                documentation_score += 30
            elif readme_quality == "Small":
                documentation_score += 15

        # Additional documentation (up to 40 points)
        if repo_stats.get('has_docs', False):
            docs_category = repo_stats.get('docs_size_category', "None")
            if docs_category == "Big":
                documentation_score += 40
            elif docs_category == "Intermediate":
                documentation_score += 30
            elif docs_category == "Small":
                documentation_score += 15

        # Wiki presence (up to 20 points)
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
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(
                        days=self.config["INACTIVE_THRESHOLD_DAYS"])

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

                            months_active = min(12,
                                                int((datetime.now().replace(
                                                    tzinfo=timezone.utc) - created_at).days / 30))
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
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(
                        days=self.config["INACTIVE_THRESHOLD_DAYS"])
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

            # Use our file analysis languages instead of merging with GitHub API data
            # GitHub API returns sizes in bytes, not lines of code, so using these values
            # as LOC would result in inflated numbers
            combined_languages = dict(file_stats['languages'])
            
            # Log the difference between our analysis and GitHub's for debugging
            logger.debug(f"File analysis languages: {combined_languages}")
            logger.debug(f"GitHub API languages (bytes): {github_languages}")
            
            # We'll continue using our manually counted LOC

            # Calculate estimated test coverage percentage based on test files to total files ratio
            test_coverage_percentage = None
            if file_stats['has_tests'] and file_stats['total_files'] > 0:
                # Simple estimation based on test files count relative to codebase size
                # More sophisticated estimation would require actual test coverage data
                test_ratio = min(
                    file_stats['test_files_count'] / max(1, file_stats['total_files'] - file_stats['test_files_count']),
                    1.0)
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
                # Let CodeStats calculate total_loc based on languages when calculate_primary_language is called
                avg_loc_per_file=avg_loc,
                file_types=dict(file_stats['file_types']),
                size_kb=repo.size,
                excluded_file_count=file_stats.get('excluded_file_count', 0),
                project_structure=file_stats.get('project_structure', {})
            )
            
            # Calculate primary language which will also set the correct total_loc
            code_stats.calculate_primary_language()

            # Create quality indicators
            quality = QualityIndicators(
                has_docs=file_stats['has_docs'],
                has_readme=file_stats['has_readme'],
                has_tests=file_stats['has_tests'],
                test_files_count=file_stats['test_files_count'],
                test_coverage_percentage=test_coverage_percentage,
                has_cicd=file_stats.get('has_cicd', False),
                cicd_files=file_stats.get('cicd_files', []),
                dependency_files=file_stats['dependency_files'],
                # New metrics
                has_packages=file_stats.get('has_packages', False),
                package_files=file_stats.get('package_files', []),
                has_deployments=file_stats.get('has_deployments', False),
                deployment_files=file_stats.get('deployment_files', []),
                has_releases=file_stats.get('has_releases', False),
                release_count=file_stats.get('release_count', 0),
                docs_size_category=file_stats.get('docs_size_category', "None"),
                docs_files_count=file_stats.get('docs_files_count', 0),
                readme_comprehensiveness=file_stats.get('readme_comprehensiveness', "None"),
                readme_line_count=file_stats.get('readme_line_count', 0)
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
        if repo_stats.code_stats.total_loc > self.config[
            "LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.quality.has_docs:
            repo_stats.add_anomaly("Large repository without documentation")

        # Large repo without tests
        if repo_stats.code_stats.total_loc > self.config[
            "LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.quality.has_tests:
            repo_stats.add_anomaly("Large repository without tests")

        # Popular repo without docs
        if repo_stats.community.stars > 10 and not repo_stats.quality.has_docs:
            repo_stats.add_anomaly("Popular repository without documentation")

        # Small/inadequate README for larger codebases
        if repo_stats.code_stats.total_loc > 1000 and repo_stats.quality.readme_comprehensiveness in ["None", "Small"]:
            repo_stats.add_anomaly("Large codebase with inadequate README")

        # Many open issues
        if repo_stats.community.open_issues > 20 and not repo_stats.activity.is_active:
            repo_stats.add_anomaly("Many open issues but repository is inactive")

        # Stale repository with stars
        if not repo_stats.activity.is_active and repo_stats.community.stars > 10:
            repo_stats.add_anomaly("Popular repository appears to be abandoned")

        # Active project without package management
        if repo_stats.activity.is_active and repo_stats.code_stats.total_loc > 1000 and not repo_stats.quality.has_packages:
            repo_stats.add_anomaly("Active project without package management")

        # Missing releases in mature project
        if repo_stats.activity.is_active and repo_stats.code_stats.total_loc > 1000 and not repo_stats.quality.has_releases:
            repo_stats.add_anomaly("Mature project without releases")

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

    @staticmethod
    def is_excluded_path(file_path: str) -> bool:
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

    def analyze_repositories(self, repositories: List[Repository]) -> List[RepoStats]:
        """
        Analyze a specific list of repositories.
        
        This method is similar to analyze_all_repositories but works with a
        provided list of repositories instead of fetching them from the user.
        
        Args:
            repositories: List of Repository objects to analyze
            
        Returns:
            List of RepoStats objects, one for each analyzed repository
        """
        logger.info(f"Starting analysis of {len(repositories)} specified repositories")

        all_stats = []
        analyzed_repo_names = []
        repos_to_analyze = repositories
        last_rate_display = 0  # Track when we last displayed the rate usage

        try:
            # Check for existing checkpoint
            checkpoint_data = self.load_checkpoint()

            # If checkpoint exists and resume is enabled, load the checkpoint data
            if checkpoint_data:
                all_stats = checkpoint_data.get('all_stats', [])
                analyzed_repo_names = checkpoint_data.get('analyzed_repos', [])

                # Filter out repositories that have already been analyzed
                repos_to_analyze = [repo for repo in repositories if repo.name not in analyzed_repo_names]

                logger.info(f"Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
                rprint(
                    f"[blue]📋 Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories[/blue]")

            # Initialize GitHub with rate limit check
            self.check_rate_limit()

            logger.info(f"Analyzing {len(repos_to_analyze)} repositories after checkpoint filtering")

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
            rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
            self.rate_display.display_once()  # Use our interactive display
            rprint("[bold]-------------------------------[/bold]")

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

                        # Periodically show rate limit status
                        if repo_counter % 5 == 0 or repo_counter == 1 or len(batch) == batch_size:
                            rprint("\n[bold]--- Current API Rate Status ---[/bold]")
                            self.rate_display.display_once()
                            rprint("[bold]-------------------------------[/bold]")

                        # Check if we need to checkpoint before processing this batch
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in
                                                                                                  newly_analyzed_repos],
                                                                remaining_repos + batch):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats

                        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            # Submit all tasks for this batch
                            future_to_repo = {executor.submit(self.analyze_single_repository, repo): repo for repo in
                                              batch}

                            # Process results as they complete
                            for future in concurrent.futures.as_completed(future_to_repo):
                                repo = future_to_repo[future]
                                try:
                                    repo_stats = future.result()
                                    all_stats.append(repo_stats)
                                    newly_analyzed_repos.append(repo)
                                    analyzed_repo_names.append(repo.name)
                                    pbar.update(1)
                                except Exception as e:
                                    logger.error(f"Failed to analyze {repo.name}: {e}")

                # Final checkpoint after all batches complete
                if self.config["ENABLE_CHECKPOINTING"] and newly_analyzed_repos:
                    self.save_checkpoint(all_stats, analyzed_repo_names, remaining_repos)
            else:
                # Sequential processing for single worker or single repo case
                with tqdm(total=total_repos, initial=len(all_stats),
                          desc="Analyzing repositories", leave=True, colour='green') as pbar:

                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")

                    for repo in repos_to_analyze:
                        # Periodically check and display rate limit status
                        if len(newly_analyzed_repos) % 5 == 0 or len(newly_analyzed_repos) == 0:
                            rprint("\n[bold]--- Current API Rate Status ---[/bold]")
                            self.rate_display.display_once()
                            rprint("[bold]-------------------------------[/bold]")

                        # Check if we need to checkpoint
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names,
                                                                repos_to_analyze[repos_to_analyze.index(repo):]):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats

                        try:
                            repo_stats = self.analyze_single_repository(repo)
                            all_stats.append(repo_stats)
                            newly_analyzed_repos.append(repo)
                            analyzed_repo_names.append(repo.name)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to analyze {repo.name}: {e}")

                # Final checkpoint after all repos complete
                if self.config["ENABLE_CHECKPOINTING"] and newly_analyzed_repos:
                    self.save_checkpoint(all_stats, analyzed_repo_names, [])

            # Final rate limit status display
            rprint("\n[bold]--- Final API Rate Status ---[/bold]")
            self.rate_display.display_once()
            rprint("[bold]----------------------------[/bold]")

            # If all repositories were successfully analyzed, clean up the checkpoint file
            if self.config["ENABLE_CHECKPOINTING"] and not repos_to_analyze:
                try:
                    Path(self.config["CHECKPOINT_FILE"]).unlink(missing_ok=True)
                except:
                    pass  # Silently ignore any issues with checkpoint deletion

            logger.info(f"Successfully analyzed {len(all_stats)} repositories")
            return all_stats

        except RateLimitExceededException:
            logger.error("GitHub API rate limit exceeded during repository analysis")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            if all_stats and self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            return all_stats
