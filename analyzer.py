"""
GitHub Repository RunnerAnalyzer Module

This module provides detailed analysis of GitHub repositories.
It handles fetching repository data, analyzing code quality, activity metrics,
and community engagement.
"""

import concurrent.futures
import contextlib
import dataclasses
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from github.GithubException import GithubException, RateLimitExceededException
from github.Repository import Repository
from tqdm.auto import tqdm

from config import BINARY_EXTENSIONS, CONFIG_FILES, EXCLUDED_DIRECTORIES, LANGUAGE_EXTENSIONS, \
    SPECIAL_FILENAMES, PACKAGE_FILES, DEPLOYMENT_FILES, RELEASE_FILES, Configuration, is_game_repo, \
    MEDIA_FILE_EXTENSIONS, get_media_type, AUDIO_FILE_EXTENSIONS
from console import rprint, logger, RateLimitDisplay
from models import RepoStats, BaseRepoInfo, CodeStats, QualityIndicators, ActivityMetrics, CommunityMetrics, \
    AnalysisScores, MediaMetrics
from utilities import ensure_utc

# Initialize the rate limit display
rate_display = RateLimitDisplay()


def is_binary_file(file_path: str) -> bool:
    """Check if file is binary"""
    ext = Path(file_path).suffix.lower()
    return ext in BINARY_EXTENSIONS or ext in MEDIA_FILE_EXTENSIONS


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


def is_excluded_file(file_path: str) -> bool:
    """Check if file should be excluded from analysis"""

    # Skip .gitkeep files
    filename = Path(file_path).name.lower()
    if filename == '.gitkeep' or filename == '.gitignore':
        return True

    # Check if it's a binary file
    if is_binary_file(file_path):
        return True

    return False


@dataclasses.dataclass
class LineProcessResult:
    """Result of processing a single line for LOC counting"""
    loc_count: int
    in_block_comment: bool


@dataclasses.dataclass
class AnalysisState:
    """Encapsulates the state of an ongoing analysis"""
    all_stats: List
    analyzed_repo_names: List[str]
    repos_to_analyze: List[Repository]
    newly_analyzed_repos: List
    total_repos: int


class CodeAnalyzer:
    """
    A comprehensive class for analyzing code across multiple languages.
    
    This class provides methods to count lines of code while handling
    language-specific comment styles, blank lines, and special file types.
    """

    def __init__(self):
        """Initialize the CodeAnalyzer with language-specific comment patterns."""
        # Language comment pattern definitions
        self.language_patterns = self._get_language_patterns()
        # Map file extensions to language types
        self.extension_to_language = self._get_extension_to_language()

    @staticmethod
    def _get_extension_to_language() -> Dict[str, str]:
        """Get mapping of file extensions to language types"""
        return {
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

    @staticmethod
    def _get_language_patterns() -> Dict[str, Dict[str, str]]:
        """Get language patterns for comment styles"""
        return {
            # Python-style
            'python': {'line_comment': '#', 'block_start': '"""', 'block_end': '"""', 'alt_block_start': "'''",
                       'alt_block_end': "'''"},
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
        # Skip empty content
        if not content:
            return 0

        # Handle binary files
        if is_binary_file(file_path):
            return 0

        # Skip meta files, .gitkeep files and other excluded files
        filename = Path(file_path).name.lower()
        if filename == '.gitkeep' or filename == '.gitignore' or filename.endswith('.meta'):
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
        patterns = self.language_patterns.get(language, {
            'line_comment': None,
            'block_start': None,
            'block_end': None
        })

        lines = content.split('\n')
        loc = 0
        in_block_comment = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Process line based on current comment state
            line_result = self._process_line_for_loc(stripped, patterns, in_block_comment)
            loc += line_result.loc_count
            in_block_comment = line_result.in_block_comment

        return loc

    def _process_line_for_loc(self, line: str, patterns: dict, in_block_comment: bool) -> 'LineProcessResult':
        """
        Process a single line to determine if it contains code and update block comment state.

        Args:
            line: Stripped line content
            patterns: Language comment patterns
            in_block_comment: Current block comment state

        Returns:
            LineProcessResult with loc_count and updated block comment state
        """
        if in_block_comment:
            return self._process_line_in_block_comment(line, patterns)

        return self._process_line_outside_comment(line, patterns)

    def _process_line_in_block_comment(self, line: str, patterns: dict) -> 'LineProcessResult':
        """Process a line that's inside a block comment"""
        block_end = patterns.get('block_end')

        if not block_end or block_end not in line:
            return LineProcessResult(loc_count=0, in_block_comment=True)

        # Found end of block comment
        end_pos = line.find(block_end)
        code_after_comment = line[end_pos + len(block_end):].strip()

        # Check if there's code after the block comment ends
        if self._is_code_line(code_after_comment, patterns):
            return LineProcessResult(loc_count=1, in_block_comment=False)

        return LineProcessResult(loc_count=0, in_block_comment=False)

    def _process_line_outside_comment(self, line: str, patterns: dict) -> 'LineProcessResult':
        """Process a line that's outside any block comment"""
        # Check for line comments first
        if self._is_line_comment(line, patterns):
            return LineProcessResult(loc_count=0, in_block_comment=False)

        # Check for block comments
        block_result = self._check_for_block_comments(line, patterns)
        if block_result is not None:
            return block_result

        # Check for alternative block comments (like Python triple quotes)
        alt_block_result = self._check_for_alt_block_comments(line, patterns)
        if alt_block_result is not None:
            return alt_block_result

        # If we reach here, the line contains code
        return LineProcessResult(loc_count=1, in_block_comment=False)

    @staticmethod
    def _is_line_comment(line: str, patterns: dict) -> bool:
        """Check if a line is a line comment"""
        line_comment = patterns.get('line_comment')
        return line_comment and line.startswith(line_comment)

    def _check_for_block_comments(self, line: str, patterns: dict) -> Optional['LineProcessResult']:
        """Check for standard block comments and process accordingly"""
        block_start = patterns.get('block_start')
        block_end = patterns.get('block_end')

        if not block_start or block_start not in line:
            return None

        start_pos = line.find(block_start)

        # Count code before the block comment
        code_before = line[:start_pos].strip()
        loc_count = 1 if code_before else 0

        # Check if block comment ends on the same line
        if block_end and block_end in line[start_pos + len(block_start):]:
            code_after = self._get_code_after_block_end(line, start_pos, block_start, block_end)
            if self._is_code_line(code_after, patterns):
                loc_count = 1
            return LineProcessResult(loc_count=loc_count, in_block_comment=False)

        # Block comment continues to next line
        return LineProcessResult(loc_count=loc_count, in_block_comment=True)

    def _check_for_alt_block_comments(self, line: str, patterns: dict) -> Optional['LineProcessResult']:
        """Check for alternative block comments (like Python triple quotes)"""
        alt_block_start = patterns.get('alt_block_start')
        alt_block_end = patterns.get('alt_block_end')

        if not alt_block_start or alt_block_start not in line:
            return None

        start_pos = line.find(alt_block_start)

        # Count code before the block comment
        code_before = line[:start_pos].strip()
        loc_count = 1 if code_before else 0

        # Check if block comment ends on the same line
        if alt_block_end and alt_block_end in line[start_pos + len(alt_block_start):]:
            code_after = self._get_code_after_block_end(line, start_pos, alt_block_start, alt_block_end)
            if self._is_code_line(code_after, patterns):
                loc_count = 1
            return LineProcessResult(loc_count=loc_count, in_block_comment=False)

        # Block comment continues to next line
        return LineProcessResult(loc_count=loc_count, in_block_comment=True)

    @staticmethod
    def _get_code_after_block_end(line: str, start_pos: int, block_start: str, block_end: str) -> str:
        """Extract code that appears after a block comment ends"""
        end_pos = line.find(block_end, start_pos + len(block_start))
        if end_pos == -1:
            return ""

        return line[end_pos + len(block_end):].strip()

    @staticmethod
    def _is_code_line(code: str, patterns: dict) -> bool:
        """Check if a code snippet represents actual code (not a comment)"""
        if not code:
            return False

        line_comment = patterns.get('line_comment')
        return not (line_comment and code.startswith(line_comment))

    # Helper class to encapsulate line processing results

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


class SingleRepoAnalyzer:
    """Class responsible for analyzing a single GitHub repository"""

    def __init__(self, github_analyzer):
        """Initialize with reference to parent GithubAnalyzer"""
        self.github_analyzer = github_analyzer
        self.github = github_analyzer.github
        self.config = github_analyzer.config

    def analyze(self, repo: Repository) -> RepoStats:
        """Analyze a single repository and return detailed statistics"""
        logger.info(f"Analyzing repository: {repo.name}")

        try:
            # Get file analysis
            file_stats = self.github_analyzer.analyze_repository_files(repo)

            # Build analysis components
            activity_data = self._analyze_repository_activity(repo)
            community_data = self._analyze_community_metrics(repo)
            language_data = self._analyze_languages(repo, file_stats)

            # Create repository statistics object
            repo_stats = self._build_repo_stats(repo, file_stats, activity_data, community_data, language_data)

            # Finalize analysis
            self._finalize_analysis(repo_stats, file_stats.get('is_empty', False))

            return repo_stats

        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")
            return self._create_minimal_repo_stats(repo)

    def _analyze_repository_activity(self, repo: Repository) -> Dict:
        """Analyze repository activity metrics including commits and dates"""
        activity_data = {
            'is_active': False,
            'last_commit_date': None,
            'commits_last_month': 0,
            'commits_last_year': 0,
            'commit_frequency': 0.0
        }

        try:
            # Get commit history with rate limit awareness
            self.github_analyzer.check_rate_limit()
            commits = list(repo.get_commits().get_page(0))

            if commits:
                activity_data = self._process_commit_history(repo, commits)

        except GithubException as e:
            activity_data = self._handle_commit_analysis_error(repo, e)

        return activity_data

    def _process_commit_history(self, repo: Repository, commits: List) -> Dict:
        """Process commit history to extract activity metrics"""
        latest_commit = commits[0]
        last_commit_date = latest_commit.commit.author.date

        # Calculate activity status
        inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(
            days=self.config["INACTIVE_THRESHOLD_DAYS"])
        is_active = last_commit_date > inactive_threshold if last_commit_date else False

        # Get recent commit counts
        commits_last_month, commits_last_year = self._count_recent_commits(repo)

        # Calculate commit frequency
        commit_frequency = self._calculate_commit_frequency(repo, commits_last_year)

        return {
            'is_active': is_active,
            'last_commit_date': last_commit_date,
            'commits_last_month': commits_last_month,
            'commits_last_year': commits_last_year,
            'commit_frequency': commit_frequency
        }

    @staticmethod
    def _count_recent_commits(repo: Repository) -> tuple[int, int]:
        """Count commits in the last month and year"""
        one_month_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=30)
        one_year_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=365)

        commits_last_month = 0
        commits_last_year = 0

        try:
            recent_commits = list(repo.get_commits(since=one_year_ago))
            commits_last_month = sum(1 for c in recent_commits
                                     if c.commit.author.date > one_month_ago)
            commits_last_year = len(recent_commits)
        except GithubException as e:
            logger.warning(f"Could not get recent commits for {repo.name}: {e}")

        return commits_last_month, commits_last_year

    @staticmethod
    def _calculate_commit_frequency(repo: Repository, commits_last_year: int) -> float:
        """Calculate average monthly commit frequency"""
        if commits_last_year == 0:
            return 0.0

        try:
            created_at = ensure_utc(repo.created_at)
            months_active = min(12, int((datetime.now().replace(
                tzinfo=timezone.utc) - created_at).days / 30))

            return commits_last_year / months_active if months_active > 0 else 0.0
        except Exception:
            return 0.0

    def _handle_commit_analysis_error(self, repo: Repository, error: GithubException) -> Dict:
        """Handle errors during commit analysis"""
        activity_data = {
            'is_active': False,
            'last_commit_date': None,
            'commits_last_month': 0,
            'commits_last_year': 0,
            'commit_frequency': 0.0
        }

        # Handle empty repository specifically
        if error.status == 409 and "Git Repository is empty" in str(error):
            logger.info(f"Repository {repo.name} has no commits")
            last_commit_date = repo.pushed_at
        else:
            logger.warning(f"Could not get commit info for {repo.name}: {error}")
            last_commit_date = repo.pushed_at

        if last_commit_date:
            inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(
                days=self.config["INACTIVE_THRESHOLD_DAYS"])
            last_commit_date = ensure_utc(last_commit_date)
            activity_data['is_active'] = last_commit_date > inactive_threshold
            activity_data['last_commit_date'] = last_commit_date

        return activity_data

    def _analyze_community_metrics(self, repo: Repository) -> Dict:
        """Analyze community-related metrics"""
        community_data = {
            'contributors_count': self._get_contributors_count(repo),
            'open_prs': self._get_open_prs_count(repo),
            'closed_issues': self._get_closed_issues_count(repo)
        }

        return community_data

    @staticmethod
    def _get_contributors_count(repo: Repository) -> int:
        """Get the number of contributors for the repository"""
        try:
            return repo.get_contributors().totalCount
        except GithubException as e:
            if not (e.status == 409 and "Git Repository is empty" in str(e)):
                logger.warning(f"Could not get contributors for {repo.name}: {e}")
            return 0

    @staticmethod
    def _get_open_prs_count(repo: Repository) -> int:
        """Get the number of open pull requests"""
        try:
            return repo.get_pulls(state='open').totalCount
        except Exception as e:
            logger.warning(f"Could not get PRs for {repo.name}: {e}")
            return 0

    @staticmethod
    def _get_closed_issues_count(repo: Repository) -> int:
        """Get the number of closed issues"""
        try:
            return repo.get_issues(state='closed').totalCount
        except Exception as e:
            logger.warning(f"Could not get closed issues for {repo.name}: {e}")
            return 0

    def _analyze_languages(self, repo: Repository, file_stats: Dict) -> Dict:
        """Analyze repository languages and calculate test coverage"""
        # Get languages from GitHub API (for reference/debugging)
        github_languages = self._get_github_languages(repo)

        # Use our file analysis languages instead of GitHub API data
        combined_languages = dict(file_stats['languages'])

        # Log the difference for debugging
        logger.debug(f"File analysis languages: {combined_languages}")
        logger.debug(f"GitHub API languages (bytes): {github_languages}")

        # Calculate test coverage
        test_coverage_percentage = self._calculate_test_coverage(file_stats)

        return {
            'languages': combined_languages,
            'test_coverage_percentage': test_coverage_percentage
        }

    @staticmethod
    def _get_github_languages(repo: Repository) -> Dict:
        """Get languages from GitHub API"""
        try:
            return repo.get_languages()
        except Exception as e:
            logger.warning(f"Could not get languages from API for {repo.name}: {e}")
            return {}

    @staticmethod
    def _calculate_test_coverage(file_stats: Dict) -> Optional[float]:
        """Calculate estimated test coverage percentage"""
        if not file_stats['has_tests'] or file_stats['total_files'] == 0:
            return None

        test_ratio = min(
            file_stats['test_files_count'] / max(1, file_stats['total_files'] - file_stats['test_files_count']),
            1.0
        )

        # Scale to percentage with diminishing returns model
        return min(100, 100 * (1 - (1 / (1 + 2 * test_ratio))))

    def _build_repo_stats(self, repo: Repository, file_stats: Dict, activity_data: Dict,
                          community_data: Dict, language_data: Dict) -> RepoStats:
        """Build the complete RepoStats object"""
        # Calculate derived statistics
        avg_loc = (file_stats['total_loc'] / file_stats['total_files']
                   if file_stats['total_files'] > 0 else 0)

        # Create component objects
        base_info = self._create_base_info(repo)
        code_stats = self._create_code_stats(file_stats, language_data, avg_loc, repo.size)
        quality = self._create_quality_indicators(file_stats, language_data['test_coverage_percentage'])
        activity = self._create_activity_metrics(activity_data)
        community = self._create_community_metrics(repo, community_data)
        media = self._create_media_metrics(file_stats)

        # Calculate scores
        scores_dict = self.github_analyzer.calculate_scores(file_stats, repo)
        scores = self._create_analysis_scores(scores_dict)

        return RepoStats(
            base_info=base_info,
            code_stats=code_stats,
            quality=quality,
            activity=activity,
            community=community,
            scores=scores,
            media=media
        )

    @staticmethod
    def _create_base_info(repo: Repository) -> BaseRepoInfo:
        """Create base repository information"""
        return BaseRepoInfo(
            name=repo.name,
            is_private=repo.private,
            default_branch=repo.default_branch,
            is_fork=repo.fork,
            is_archived=repo.archived,
            is_template=repo.is_template,
            created_at=ensure_utc(repo.created_at),
            last_pushed=ensure_utc(repo.pushed_at),
            description=repo.description,
            homepage=repo.homepage
        )

    @staticmethod
    def _create_code_stats(file_stats: Dict, language_data: Dict, avg_loc: float, size_kb: int) -> CodeStats:
        """Create code statistics object"""
        code_stats = CodeStats(
            languages=language_data['languages'],
            total_files=file_stats['total_files'],
            avg_loc_per_file=avg_loc,
            file_types=dict(file_stats['file_types']),
            size_kb=size_kb,
            excluded_file_count=file_stats.get('excluded_file_count', 0),
            project_structure=file_stats.get('project_structure', {}),
            is_game_repo=file_stats.get('is_game_repo', False),
            game_engine=file_stats.get('game_engine', 'None'),
            game_confidence=file_stats.get('game_confidence', 0.0)
        )

        # Calculate primary language which will also set the correct total_loc
        code_stats.calculate_primary_language()
        return code_stats

    @staticmethod
    def _create_quality_indicators(file_stats: Dict, test_coverage: Optional[float]) -> QualityIndicators:
        """Create quality indicators object"""
        return QualityIndicators(
            has_docs=file_stats['has_docs'],
            has_readme=file_stats['has_readme'],
            has_tests=file_stats['has_tests'],
            test_files_count=file_stats['test_files_count'],
            test_coverage_percentage=test_coverage,
            has_cicd=file_stats.get('has_cicd', False),
            cicd_files=file_stats.get('cicd_files', []),
            dependency_files=file_stats['dependency_files'],
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

    @staticmethod
    def _create_activity_metrics(activity_data: Dict) -> ActivityMetrics:
        """Create activity metrics object"""
        return ActivityMetrics(
            last_commit_date=activity_data['last_commit_date'],
            is_active=activity_data['is_active'],
            commit_frequency=activity_data['commit_frequency'],
            commits_last_month=activity_data['commits_last_month'],
            commits_last_year=activity_data['commits_last_year']
        )

    @staticmethod
    def _create_community_metrics(repo: Repository, community_data: Dict) -> CommunityMetrics:
        """Create community metrics object"""
        return CommunityMetrics(
            license_name=repo.license.name if repo.license else None,
            license_spdx_id=repo.license.spdx_id if repo.license else None,
            contributors_count=community_data['contributors_count'],
            open_issues=repo.open_issues_count,
            open_prs=community_data['open_prs'],
            closed_issues=community_data['closed_issues'],
            topics=repo.topics,
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            watchers=repo.watchers_count
        )

    @staticmethod
    def _create_analysis_scores(scores_dict: Dict[str, float]) -> AnalysisScores:
        """Create analysis scores object"""
        return AnalysisScores(
            maintenance_score=scores_dict['maintenance_score'],
            popularity_score=scores_dict['popularity_score'],
            code_quality_score=scores_dict['code_quality_score'],
            documentation_score=scores_dict['documentation_score']
        )

    @staticmethod
    def _create_media_metrics(file_stats: Dict) -> MediaMetrics:
        """Create media metrics object"""
        media_data = file_stats.get('media_metrics', {})

        return MediaMetrics(
            image_count=media_data.get('image_count', 0),
            audio_count=media_data.get('audio_count', 0),
            video_count=media_data.get('video_count', 0),
            model_3d_count=media_data.get('model_3d_count', 0),
            image_files=media_data.get('image_files', []),
            audio_files=media_data.get('audio_files', []),
            video_files=media_data.get('video_files', []),
            model_3d_files=media_data.get('model_3d_files', []),
            image_size_kb=media_data.get('image_size_kb', 0),
            audio_size_kb=media_data.get('audio_size_kb', 0),
            video_size_kb=media_data.get('video_size_kb', 0),
            model_3d_size_kb=media_data.get('model_3d_size_kb', 0)
        )

    def _finalize_analysis(self, repo_stats: RepoStats, is_empty: bool) -> None:
        """Finalize the analysis with additional processing"""
        # Add anomaly for empty repository
        if is_empty:
            repo_stats.add_anomaly("Empty repository with no files")

        # Calculate additional derived metrics
        repo_stats.detect_monorepo()

        # Identify anomalies
        self.github_analyzer.detect_anomalies(repo_stats)

    @staticmethod
    def _create_minimal_repo_stats(repo: Repository) -> RepoStats:
        """Create minimal repository stats when analysis fails"""
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


class AnalyzerRepoFiles:
    """Class responsible for analyzing files within a single repository"""

    def __init__(self, github_analyzer):
        """Initialize with reference to parent GithubAnalyzer"""
        self.github_analyzer = github_analyzer
        self.github = github_analyzer.github
        self.config = github_analyzer.config

    def analyze(self, repo: Repository) -> Dict[str, Any]:
        """Analyze files in a repository with improved detection capabilities"""
        stats = self._initialize_stats()

        try:
            # Early checks
            self.github_analyzer.check_rate_limit()

            # Main analysis pipeline
            files_to_process = self._collect_repository_files(repo, stats)
            self._process_files(repo, files_to_process, stats)
            self._process_additional_metadata(repo, stats)
            self._finalize_stats(repo, stats)

            return dict(stats)

        except (RateLimitExceededException, GithubException, Exception) as e:
            return self._handle_analysis_error(repo, stats, e)

    @staticmethod
    def _initialize_stats() -> Dict[str, Any]:
        """Initialize the statistics dictionary with default values"""
        return {
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
            'is_empty': False,
            'skipped_directories': set(),
            'excluded_file_count': 0,

            # Package and deployment tracking
            'has_packages': False,
            'package_files': [],
            'has_deployments': False,
            'deployment_files': [],
            'has_releases': False,
            'release_files': [],

            # Documentation tracking
            'docs_files': [],
            'readme_file': None,
            'readme_content': None,
            'readme_line_count': 0,

            # Game repository detection
            'is_game_repo': False,
            'game_engine': 'None',
            'game_confidence': 0.0,

            # Media files tracking
            'media_metrics': {
                'image_count': 0,
                'audio_count': 0,
                'video_count': 0,
                'model_3d_count': 0,
                'image_files': [],
                'audio_files': [],
                'video_files': [],
                'model_3d_files': [],
                'image_size_kb': 0,
                'audio_size_kb': 0,
                'video_size_kb': 0,
                'model_3d_size_kb': 0
            },
            'has_media': False
        }

    def _collect_repository_files(self, repo: Repository, stats: Dict[str, Any]) -> List:
        """Collect all files from repository, handling directories and exclusions"""
        try:
            contents = repo.get_contents("")
            files_to_process = []
            directories_seen = set()

            while contents:
                file_content = contents.pop(0)

                if file_content.type == "dir":
                    self._process_directory(repo, file_content, contents, directories_seen, stats)
                else:
                    if self._should_process_file(file_content, stats):
                        files_to_process.append(file_content)

            return files_to_process

        except Exception as e:
            logger.error(f"Error collecting files from {repo.name}: {e}")
            return []

    def _process_directory(self, repo: Repository, file_content, contents: List,
                           directories_seen: set, stats: Dict[str, Any]) -> None:
        """Process a directory, adding its contents to the processing queue"""
        try:
            if self.github_analyzer.is_excluded_path(file_content.path):
                stats['skipped_directories'].add(file_content.path)
                logger.debug(f"Skipping excluded directory: {file_content.path}")
                return

            if file_content.path not in directories_seen:
                directories_seen.add(file_content.path)
                contents.extend(repo.get_contents(file_content.path))

                # Update project structure statistics
                path_parts = file_content.path.split('/')
                if len(path_parts) == 1:  # Top-level directory
                    stats['project_structure'][path_parts[0]] += 1

        except Exception as e:
            logger.warning(f"Could not access directory {file_content.path}: {e}")

    def _should_process_file(self, file_content, stats: Dict[str, Any]) -> bool:
        """Determine if a file should be processed for analysis"""
        if self.github_analyzer.is_excluded_path(file_content.path):
            stats['excluded_file_count'] += 1
            logger.debug(f"Skipping file in excluded path: {file_content.path}")
            self._track_media_if_applicable(file_content, stats)
            return False

        if is_excluded_file(file_content.path):
            stats['excluded_file_count'] += 1
            logger.debug(f"Skipping excluded file: {file_content.path}")
            self._track_media_if_applicable(file_content, stats)
            return False

        return True

    @staticmethod
    def _track_media_if_applicable(file_content, stats: Dict[str, Any]) -> None:
        """Track media files even if they're excluded from code analysis"""
        media_type = get_media_type(file_content.path)
        if media_type:
            size_kb = file_content.size // 1024 if file_content.size else 0
            stats['media_metrics'][f'{media_type}_count'] += 1
            stats['media_metrics'][f'{media_type}_files'].append(file_content.path)
            stats['media_metrics'][f'{media_type}_size_kb'] += size_kb
            logger.debug(f"Detected {media_type} file: {file_content.path} ({size_kb} KB)")

    def _process_files(self, repo: Repository, files_to_process: List, stats: Dict[str, Any]) -> None:
        """Process all files for analysis"""
        all_file_extensions = set()

        for file_content in tqdm(files_to_process,
                                 desc=f"Analyzing {repo.name} files",
                                 leave=False,
                                 colour='cyan'):
            try:
                self._process_single_file(repo, file_content, stats, all_file_extensions)
            except Exception as e:
                logger.warning(f"Error processing file {file_content.path}: {e}")
                continue

        # Log debugging information
        self._log_file_analysis_debug(repo, stats, all_file_extensions)

    def _process_single_file(self, repo: Repository, file_content, stats: Dict[str, Any],
                             all_file_extensions: set) -> None:
        """Process a single file for all types of analysis"""
        file_path = file_content.path
        stats['total_files'] += 1

        # Track file extensions
        ext = Path(file_path).suffix.lower()
        if ext:
            all_file_extensions.add(ext)

        # Debug logging for specific repositories
        if repo.name == "DrumVerse" and ext in AUDIO_FILE_EXTENSIONS:
            logger.info(f"Found audio file in DrumVerse: {file_path}")

        # Process different aspects of the file
        self._track_media_file(file_content, stats)
        self._analyze_file_type_and_purpose(file_content, stats)
        self._count_lines_of_code(file_content, stats)

    @staticmethod
    def _track_media_file(file_content, stats: Dict[str, Any]) -> None:
        """Track media files and their sizes"""
        media_type = get_media_type(file_content.path)
        if media_type:
            size_kb = file_content.size // 1024 if file_content.size else 0
            stats['media_metrics'][f'{media_type}_count'] += 1
            stats['media_metrics'][f'{media_type}_files'].append(file_content.path)
            stats['media_metrics'][f'{media_type}_size_kb'] += size_kb
            logger.debug(f"Detected {media_type} file: {file_content.path} ({size_kb} KB)")

    def _analyze_file_type_and_purpose(self, file_content, stats: Dict[str, Any]) -> None:
        """Analyze file type and determine its purpose (docs, tests, CI/CD, etc.)"""
        file_path = file_content.path

        # Documentation analysis
        if self._is_documentation_file(file_path):
            stats['has_docs'] = True
            stats['docs_files'].append(file_path)

            if 'readme' in file_path.lower():
                self._process_readme_file(file_content, stats)

        # Other file type checks
        if is_test_file(file_path):
            stats['has_tests'] = True
            stats['test_files_count'] += 1

        if is_cicd_file(file_path):
            stats['has_cicd'] = True
            stats['cicd_files'].append(file_path)

        if is_config_file(file_path):
            stats['dependency_files'].append(file_path)

        if is_package_file(file_path):
            stats['has_packages'] = True
            stats['package_files'].append(file_path)

        if is_deployment_file(file_path):
            stats['has_deployments'] = True
            stats['deployment_files'].append(file_path)

        if is_release_file(file_path):
            stats['has_releases'] = True
            stats['release_files'].append(file_path)

    @staticmethod
    def _is_documentation_file(file_path: str) -> bool:
        """Check if a file is a documentation file"""
        return ('readme' in file_path.lower() or
                file_path.lower().startswith('docs/') or
                '/docs/' in file_path.lower() or
                file_path.lower().endswith('.md'))

    @staticmethod
    def _process_readme_file(file_content, stats: Dict[str, Any]) -> None:
        """Process README file for content analysis"""
        stats['has_readme'] = True
        stats['readme_file'] = file_content.path

        try:
            if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
                readme_content = file_content.decoded_content.decode('utf-8', errors='ignore')
                stats['readme_content'] = readme_content
                stats['readme_line_count'] = len(readme_content.splitlines())
        except Exception as e:
            logger.debug(f"Could not decode README {file_content.path}: {e}")

    def _count_lines_of_code(self, file_content, stats: Dict[str, Any]) -> None:
        """Count lines of code for non-binary files"""
        file_path = file_content.path

        # Handle binary files
        if is_binary_file(file_path):
            stats['file_types']['Binary'] += 1
            self._track_media_file(file_content, stats)  # Track media even if binary
            return

        # Determine language and file type
        language = self.github_analyzer.get_file_language(file_path)
        self._categorize_file_type(file_path, stats)

        # Skip meta files for LOC counting
        path_obj = Path(file_path)
        if path_obj.suffix.lower() == '.meta' or path_obj.name == '.gitkeep':
            return

        # Count lines of code
        if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
            try:
                content = file_content.decoded_content.decode('utf-8', errors='ignore')
                loc = count_lines_of_code(content, file_path)
                stats['total_loc'] += loc
                stats['languages'][language] += loc
            except Exception as e:
                logger.debug(f"Could not decode {file_path}: {e}")

    @staticmethod
    def _categorize_file_type(file_path: str, stats: Dict[str, Any]) -> None:
        """Categorize file type based on extension or filename"""
        path_obj = Path(file_path)
        filename = path_obj.name
        ext = path_obj.suffix.lower()

        if ext:
            stats['file_types'][ext] += 1
        elif filename in SPECIAL_FILENAMES:
            stats['file_types'][f"no_ext_{filename}"] += 1
        elif filename.startswith('.') and filename in SPECIAL_FILENAMES:
            stats['file_types'][filename] += 1
        else:
            stats['file_types']['no_extension'] += 1

    def _process_additional_metadata(self, repo: Repository, stats: Dict[str, Any]) -> None:
        """Process additional repository metadata"""
        self._check_github_releases(repo, stats)
        self._categorize_documentation(stats)
        self._detect_game_repository(stats)

    @staticmethod
    def _check_github_releases(repo: Repository, stats: Dict[str, Any]) -> None:
        """Check for GitHub releases"""
        try:
            releases = list(repo.get_releases())
            if releases:
                stats['has_releases'] = True
                stats['release_count'] = len(releases)
        except Exception as e:
            logger.debug(f"Could not get releases for {repo.name}: {e}")

    @staticmethod
    def _categorize_documentation(stats: Dict[str, Any]) -> None:
        """Categorize documentation size and README comprehensiveness"""
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

    @staticmethod
    def _detect_game_repository(stats: Dict[str, Any]) -> None:
        """Detect if repository is a game repository"""
        try:
            game_repo_info = is_game_repo(stats['file_types'], stats['project_structure'])
            stats['is_game_repo'] = game_repo_info['is_game_repo']
            stats['game_engine'] = game_repo_info['engine_type']
            stats['game_confidence'] = game_repo_info['confidence']

            if stats['is_game_repo'] and stats['game_confidence'] > 0.7:
                logger.info(f"Detected game repository using {stats['game_engine']} engine "
                            f"(confidence: {stats['game_confidence']:.2f})")
        except Exception as e:
            logger.error(f"Error during game repository detection: {e}")
            stats['is_game_repo'] = False
            stats['game_engine'] = 'None'
            stats['game_confidence'] = 0.0

    def _finalize_stats(self, repo: Repository, stats: Dict[str, Any]) -> None:
        """Finalize statistics and perform cleanup"""
        self._set_media_flags(stats)
        self._log_media_summary(repo, stats)
        self._log_exclusion_summary(repo, stats)
        self._cleanup_stats(stats)

    @staticmethod
    def _set_media_flags(stats: Dict[str, Any]) -> None:
        """Set media-related flags based on counts"""
        media_metrics = stats['media_metrics']
        stats['has_media'] = (
                media_metrics['image_count'] > 0 or
                media_metrics['audio_count'] > 0 or
                media_metrics['video_count'] > 0 or
                media_metrics['model_3d_count'] > 0
        )

    @staticmethod
    def _log_media_summary(repo: Repository, stats: Dict[str, Any]) -> None:
        """Log summary of media files found"""
        if not stats['has_media']:
            return

        media_metrics = stats['media_metrics']
        logger.info(f"Repository {repo.name} contains media files:")

        media_types = [
            ('image', 'Images'),
            ('audio', 'Audio'),
            ('video', 'Video'),
            ('model_3d', '3D Models')
        ]

        for media_type, display_name in media_types:
            count = media_metrics[f'{media_type}_count']
            if count > 0:
                size_mb = media_metrics[f'{media_type}_size_kb'] / 1024
                logger.info(f"  {display_name}: {count} files, {size_mb:.2f} MB")

                if media_type == 'audio':
                    # Log audio file examples for debugging
                    audio_examples = media_metrics['audio_files'][:5]
                    logger.debug(f"  Audio file examples: {audio_examples}")

    @staticmethod
    def _log_file_analysis_debug(repo: Repository, stats: Dict[str, Any],
                                 all_file_extensions: set) -> None:
        """Log debugging information about file analysis"""
        logger.debug(f"All file extensions found in {repo.name}: {sorted(all_file_extensions)}")

        # Special logging for DrumVerse
        if repo.name == "DrumVerse":
            logger.info("DrumVerse analysis summary:")
            logger.info(f"  Total files: {stats['total_files']}")
            logger.info(f"  Extensions found: {sorted(all_file_extensions)}")
            logger.info(f"  Has media: {stats['has_media']}")
            logger.info(f"  Media metrics: {stats['media_metrics']}")
            logger.info(f"  Looking for audio extensions: {sorted(AUDIO_FILE_EXTENSIONS)}")

    @staticmethod
    def _log_exclusion_summary(repo: Repository, stats: Dict[str, Any]) -> None:
        """Log summary of excluded directories and files"""
        if stats['skipped_directories']:
            skipped_dirs = list(stats['skipped_directories'])
            logger.info(f"Skipped {len(skipped_dirs)} directories and "
                        f"{stats['excluded_file_count']} files in {repo.name}")

            # Show first 5 directories
            dirs_to_show = skipped_dirs[:5]
            dirs_summary = ', '.join(dirs_to_show)
            if len(skipped_dirs) > 5:
                dirs_summary += f" and {len(skipped_dirs) - 5} more..."
            logger.debug(f"Skipped directories in {repo.name}: {dirs_summary}")

    @staticmethod
    def _cleanup_stats(stats: Dict[str, Any]) -> None:
        """Clean up temporary data from stats"""
        stats.pop('readme_content', None)
        stats.pop('skipped_directories', None)

    def _handle_analysis_error(self, repo: Repository, stats: Dict[str, Any],
                               error: Exception) -> Dict[str, Any]:
        """Handle analysis errors appropriately"""
        if isinstance(error, RateLimitExceededException):
            logger.error(f"GitHub API rate limit exceeded while analyzing repository {repo.name}")
            self.github_analyzer.check_rate_limit()
        elif isinstance(error, GithubException):
            if error.status == 404 and "This repository is empty" in str(error):
                logger.info(f"Repository {repo.name} is empty")
                stats['is_empty'] = True
            else:
                logger.error(f"GitHub API error analyzing repository {repo.name}: {error}")
        else:
            logger.error(f"Error analyzing repository {repo.name}: {error}")

        # Clean up and return partial results
        self._cleanup_stats(stats)
        return dict(stats)


class ScoreCalculator:
    """Class responsible for calculating various quality scores for repositories"""

    @staticmethod
    def calculate_scores(repo_stats: Dict[str, Any], repo: Repository) -> Dict[str, float]:
        """Calculate various quality scores for a repository"""
        return {
            'maintenance_score': ScoreCalculator._calculate_maintenance_score(repo_stats, repo),
            'popularity_score': ScoreCalculator._calculate_popularity_score(repo_stats, repo),
            'code_quality_score': ScoreCalculator._calculate_code_quality_score(repo_stats),
            'documentation_score': ScoreCalculator._calculate_documentation_score(repo_stats, repo)
        }

    @staticmethod
    def _calculate_maintenance_score(repo_stats: Dict[str, Any], repo: Repository) -> float:
        """Calculate maintenance score (0-100) based on project maintenance indicators"""
        score = 0.0

        # Documentation (15 points)
        score += ScoreCalculator._score_documentation_size(repo_stats, max_points=15)

        # README quality (10 points)
        score += ScoreCalculator._score_readme_quality(repo_stats, max_points=10)

        # Tests (15 points)
        score += ScoreCalculator._score_testing(repo_stats, max_points=15)

        # CI/CD (10 points)
        if repo_stats.get('has_cicd', False):
            score += 10

        # Package management (5 points)
        if repo_stats.get('has_packages', False):
            score += 5

        # Deployment configuration (5 points)
        if repo_stats.get('has_deployments', False):
            score += 5

        # Releases (5 points)
        score += ScoreCalculator._score_releases(repo_stats, max_points=5)

        # Recent activity (15 points)
        score += ScoreCalculator._score_activity(repo_stats, max_points=15)

        # License (5 points)
        if getattr(repo, 'license', None):
            score += 5

        # Issues management (5 points)
        score += ScoreCalculator._score_issue_management(repo, max_points=5)

        # Repository structure (5 points)
        score += ScoreCalculator._score_repository_structure(repo_stats, max_points=5)

        return min(score, 100.0)

    @staticmethod
    def _calculate_popularity_score(repo_stats: Dict[str, Any], repo: Repository) -> float:
        """Calculate popularity score (0-100) based on community engagement"""
        score = 0.0

        # Stars (up to 50 points)
        stars = getattr(repo, 'stargazers_count', 0)
        if stars > 1000:
            score += 50
        elif stars > 100:
            score += 30
        elif stars > 10:
            score += 15
        elif stars > 0:
            score += 5

        # Forks (up to 30 points)
        forks = getattr(repo, 'forks_count', 0)
        if forks > 100:
            score += 30
        elif forks > 10:
            score += 20
        elif forks > 0:
            score += 10

        # Contributors (up to 10 points)
        contributors_count = repo_stats.get('contributors_count', 0)
        if contributors_count > 10:
            score += 10
        elif contributors_count > 1:
            score += 5

        # Watchers (up to 10 points)
        watchers = getattr(repo, 'watchers_count', 0)
        if watchers > 10:
            score += 10
        elif watchers > 0:
            score += 5

        return min(score, 100.0)

    @staticmethod
    def _calculate_code_quality_score(repo_stats: Dict[str, Any]) -> float:
        """Calculate code quality score (0-100) based on development practices"""
        score = 0.0

        # Test coverage (up to 30 points)
        score += ScoreCalculator._score_test_coverage(repo_stats, max_points=30)

        # CI/CD (up to 20 points)
        if repo_stats.get('has_cicd', False):
            score += 20

        # Package management (up to 10 points)
        score += ScoreCalculator._score_package_management(repo_stats, max_points=10)

        # Code size and complexity (up to 20 points)
        score += ScoreCalculator._score_code_complexity(repo_stats, max_points=20)

        # Documentation (up to 20 points)
        score += ScoreCalculator._score_documentation_size(repo_stats, max_points=20)

        return min(score, 100.0)

    @staticmethod
    def _calculate_documentation_score(repo_stats: Dict[str, Any], repo: Repository) -> float:
        """Calculate documentation score (0-100) based on documentation quality and coverage"""
        score = 0.0

        # README quality (up to 40 points)
        score += ScoreCalculator._score_readme_quality(repo_stats, max_points=40)

        # Additional documentation (up to 40 points)
        score += ScoreCalculator._score_documentation_size(repo_stats, max_points=40)

        # Wiki presence (up to 20 points)
        try:
            if getattr(repo, 'has_wiki', False):
                score += 20
        except (AttributeError, Exception):
            pass

        return min(score, 100.0)

    # Helper methods for scoring specific aspects

    @staticmethod
    def _score_documentation_size(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on documentation size category"""
        if not repo_stats.get('has_docs', False):
            return 0.0

        docs_size = repo_stats.get('docs_size_category', "None")
        if docs_size == "Big":
            return max_points
        elif docs_size == "Intermediate":
            return max_points * 0.67  # ~2/3 of max points
        elif docs_size == "Small":
            return max_points * 0.33  # ~1/3 of max points

        return 0.0

    @staticmethod
    def _score_readme_quality(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on README comprehensiveness"""
        if not repo_stats.get('has_readme', False):
            return 0.0

        readme_quality = repo_stats.get('readme_comprehensiveness', "None")
        if readme_quality == "Comprehensive":
            return max_points
        elif readme_quality == "Good":
            return max_points * 0.7
        elif readme_quality == "Small":
            return max_points * 0.3

        return 0.0

    @staticmethod
    def _score_testing(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on test presence and quantity"""
        if not repo_stats.get('has_tests', False):
            return 0.0

        test_count = repo_stats.get('test_files_count', 0)
        if test_count > 10:
            return max_points
        elif test_count > 5:
            return max_points * 0.67
        elif test_count > 0:
            return max_points * 0.33

        return 0.0

    @staticmethod
    def _score_releases(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on release management"""
        if not repo_stats.get('has_releases', False):
            return 0.0

        release_count = repo_stats.get('release_count', 0)
        if release_count > 5:
            return max_points
        else:
            return min(release_count, max_points)

    @staticmethod
    def _score_activity(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on recent repository activity"""
        base_score = 10 if repo_stats.get('is_active', False) else 0

        if base_score > 0:
            commits_last_month = repo_stats.get('commits_last_month', 0)
            additional_points = max_points - 10  # Remaining points after base

            if commits_last_month > 10:
                return base_score + additional_points
            elif commits_last_month > 0:
                return base_score + min(commits_last_month / 2, additional_points)

        return base_score

    @staticmethod
    def _score_issue_management(repo: Repository, max_points: int) -> float:
        """Score based on open issues management"""
        try:
            open_issues = getattr(repo, 'open_issues_count', 0)
            if open_issues < 10:
                return max_points
            elif open_issues < 50:
                return max_points * 0.6
        except (AttributeError, Exception):
            pass

        return 0.0

    @staticmethod
    def _score_repository_structure(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on repository structure and organization"""
        score = 0.0

        # File count indicates project size/complexity
        if repo_stats.get('total_files', 0) > 5:
            score += max_points * 0.6

        # Dependency files indicate proper project setup
        if len(repo_stats.get('dependency_files', [])) > 0:
            score += max_points * 0.4

        return score

    @staticmethod
    def _score_test_coverage(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on test coverage ratio"""
        if not repo_stats.get('has_tests', False):
            return 0.0

        test_count = repo_stats.get('test_files_count', 0)
        total_files = repo_stats.get('total_files', 0)

        if total_files > 0:
            test_ratio = min(test_count / max(1, total_files - test_count), 1.0)
            return min(max_points, int(max_points * test_ratio))
        else:
            return max_points * 0.33  # Some tests are better than none

    @staticmethod
    def _score_package_management(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on package management setup"""
        if not repo_stats.get('has_packages', False):
            return 0.0

        package_files_count = len(repo_stats.get('package_files', []))
        if package_files_count > 3:
            return max_points
        else:
            return min(package_files_count * (max_points / 3), max_points)

    @staticmethod
    def _score_code_complexity(repo_stats: Dict[str, Any], max_points: int) -> float:
        """Score based on code complexity metrics"""
        if repo_stats.get('total_loc', 0) <= 0:
            return 0.0

        avg_loc = repo_stats.get('avg_loc_per_file', 0)
        if 0 < avg_loc < 300:  # Reasonable file size
            return max_points
        elif avg_loc > 0:
            return max_points * 0.5

        return 0.0


class AnomalyDetctor:
    """Class responsible for detecting anomalies in repository data"""

    def __init__(self, config: Configuration):
        """Initialize with configuration"""
        self.config = config

    def detect(self, repo_stats: RepoStats) -> None:
        """Detect anomalies in repository data"""
        self._detect_documentation_issues(repo_stats)
        self._detect_testing_issues(repo_stats)
        self._detect_maintenance_issues(repo_stats)
        self._detect_project_maturity_issues(repo_stats)
        self._detect_media_anomalies(repo_stats)
        self._detect_special_repository_types(repo_stats)
        self._detect_age_related_issues(repo_stats)

    def _detect_documentation_issues(self, repo_stats: RepoStats) -> None:
        """Detect documentation-related anomalies"""
        large_repo_threshold = self.config.get("LARGE_REPO_LOC_THRESHOLD", 10000)
        total_loc = repo_stats.code_stats.total_loc
        has_docs = repo_stats.quality.has_docs
        stars = repo_stats.community.stars
        readme_quality = repo_stats.quality.readme_comprehensiveness

        # Large repo without documentation
        if total_loc > large_repo_threshold and not has_docs:
            repo_stats.add_anomaly("Large repository without documentation")

        # Popular repo without docs
        if stars > 10 and not has_docs:
            repo_stats.add_anomaly("Popular repository without documentation")

        # Small/inadequate README for larger codebases
        if total_loc > 1000 and readme_quality in ["None", "Small"]:
            repo_stats.add_anomaly("Large codebase with inadequate README")

    def _detect_testing_issues(self, repo_stats: RepoStats) -> None:
        """Detect testing-related anomalies"""
        large_repo_threshold = self.config.get("LARGE_REPO_LOC_THRESHOLD", 10000)
        total_loc = repo_stats.code_stats.total_loc
        has_tests = repo_stats.quality.has_tests
        test_files_count = getattr(repo_stats.quality, 'test_files_count', 0)
        total_files = repo_stats.code_stats.total_files

        # Large repo without tests
        if total_loc > large_repo_threshold and not has_tests:
            repo_stats.add_anomaly("Large repository without tests")

        # Imbalanced test coverage
        if has_tests and total_files > 0 and test_files_count < total_files * 0.05:
            repo_stats.add_anomaly("Low test coverage ratio")

    @staticmethod
    def _detect_maintenance_issues(repo_stats: RepoStats) -> None:
        """Detect maintenance and activity-related anomalies"""
        open_issues = repo_stats.community.open_issues
        is_active = repo_stats.activity.is_active
        stars = repo_stats.community.stars
        has_cicd = repo_stats.quality.has_cicd
        total_loc = repo_stats.code_stats.total_loc

        # Many open issues in inactive repo
        if open_issues > 20 and not is_active:
            repo_stats.add_anomaly("Many open issues but repository is inactive")

        # Stale repository with stars
        if not is_active and stars > 10:
            repo_stats.add_anomaly("Popular repository appears to be abandoned")

        # Missing CI/CD in active project
        if is_active and total_loc > 1000 and not has_cicd:
            repo_stats.add_anomaly("Active project without CI/CD configuration")

    @staticmethod
    def _detect_project_maturity_issues(repo_stats: RepoStats) -> None:
        """Detect issues related to project maturity and best practices"""
        is_active = repo_stats.activity.is_active
        total_loc = repo_stats.code_stats.total_loc
        has_packages = repo_stats.quality.has_packages
        has_releases = repo_stats.quality.has_releases
        license_name = getattr(repo_stats.community, 'license_name', None)

        # Active project without package management
        if is_active and total_loc > 1000 and not has_packages:
            repo_stats.add_anomaly("Active project without package management")

        # Missing releases in mature project
        if is_active and total_loc > 1000 and not has_releases:
            repo_stats.add_anomaly("Mature project without releases")

        # Project with code but no license
        if total_loc > 1000 and not license_name:
            repo_stats.add_anomaly("Substantial code without license")

    def _detect_media_anomalies(self, repo_stats: RepoStats) -> None:
        """Detect anomalies related to media files"""
        total_media_count = getattr(repo_stats, 'total_media_count', 0)

        if total_media_count == 0:
            return

        total_media_size_kb = getattr(repo_stats, 'total_media_size_kb', 0)
        total_files = repo_stats.code_stats.total_files

        # Very large media files
        if total_media_size_kb > 100000:  # More than 100MB
            size_mb = total_media_size_kb // 1024
            repo_stats.add_anomaly(f"Very large media files ({size_mb} MB)")

        # Repository dominated by media files
        if total_files > 10 and total_media_count > total_files * 0.5:
            repo_stats.add_anomaly("Repository contains more media files than code files")

        # Check for specific media type thresholds
        self._check_media_type_thresholds(repo_stats)

    @staticmethod
    def _check_media_type_thresholds(repo_stats: RepoStats) -> None:
        """Check individual media type counts against thresholds"""
        media_thresholds = [
            ('image_count', 100, 'images'),
            ('video_count', 10, 'video files'),
            ('audio_count', 20, 'audio files'),
            ('model_3d_count', 10, '3D model files')
        ]

        for attr_name, threshold, description in media_thresholds:
            count = getattr(repo_stats, attr_name, 0)
            if count > threshold:
                repo_stats.add_anomaly(f"Repository contains {count} {description}")

    @staticmethod
    def _detect_special_repository_types(repo_stats: RepoStats) -> None:
        """Detect special repository types (games, etc.)"""
        is_game_repo = getattr(repo_stats.code_stats, 'is_game_repo', False)

        if is_game_repo:
            game_engine = getattr(repo_stats.code_stats, 'game_engine', 'Unknown')
            repo_stats.add_anomaly(f"Game repository detected ({game_engine})")

    @staticmethod
    def _detect_age_related_issues(repo_stats: RepoStats) -> None:
        """Detect issues related to repository age and activity"""
        created_at = getattr(repo_stats.base_info, 'created_at', None)
        last_commit_date = getattr(repo_stats.activity, 'last_commit_date', None)

        if not created_at or not last_commit_date:
            return

        with contextlib.suppress(Exception):
            from datetime import datetime, timezone

            now = datetime.now().replace(tzinfo=timezone.utc)
            created_at_utc = ensure_utc(created_at)
            last_commit_utc = ensure_utc(last_commit_date)

            years_since_created = (now - created_at_utc).days / 365.25
            months_since_last_commit = (now - last_commit_utc).days / 30

            if years_since_created > 3 and months_since_last_commit > 12:
                repo_stats.add_anomaly("Old repository without updates in over a year")


class ReposAnalyzer:
    """Class responsible for analyzing multiple repositories with checkpointing and rate limiting"""

    def __init__(self, github_analyzer):
        """Initialize with reference to parent GithubAnalyzer"""
        self.github_analyzer = github_analyzer
        self.github = github_analyzer.github
        self.config = github_analyzer.config
        self.rate_display = github_analyzer.rate_display

    def analyze(self, repositories: List[Repository]) -> List[RepoStats]:
        """
        Analyze a specific list of repositories.

        This method analyzes a provided list of repositories with support for
        checkpointing, rate limiting, and parallel processing.
        Args:
            repositories: List of Repository objects to analyze

        Returns:
            List of RepoStats objects, one for each analyzed repository
        """
        logger.info(f"Starting analysis of {len(repositories)} specified repositories")

        analysis_state: Optional[AnalysisState] = None
        try:
            # Initialize analysis state
            analysis_state = self._initialize_analysis_state(repositories)

            # Early exit if no work to do
            if self._should_exit_early(analysis_state):
                return analysis_state.all_stats

            # Setup and execute analysis
            self._prepare_for_analysis()
            self._execute_analysis(analysis_state)
            self._finalize_analysis(analysis_state)

            logger.info(f"Successfully analyzed {len(analysis_state.all_stats)} repositories")
            return analysis_state.all_stats

        except (RateLimitExceededException, GithubException, Exception) as e:
            return self._handle_analysis_error(e, analysis_state if 'analysis_state' in locals() else None)

    def _initialize_analysis_state(self, repositories: List[Repository]) -> 'AnalysisState':
        """Initialize analysis state including checkpoint recovery"""
        all_stats = []
        analyzed_repo_names = []
        repos_to_analyze = repositories

        # Check for existing checkpoint
        checkpoint_data = self.github_analyzer.load_checkpoint()

        if checkpoint_data:
            all_stats = checkpoint_data.get('all_stats', [])
            analyzed_repo_names = checkpoint_data.get('analyzed_repos', [])
            repos_to_analyze = [repo for repo in repositories if repo.name not in analyzed_repo_names]

            logger.info(f"Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
            rprint(
                f"[blue]📋 Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories[/blue]")

        logger.info(f"Analyzing {len(repos_to_analyze)} repositories after checkpoint filtering")

        return AnalysisState(
            all_stats=all_stats,
            analyzed_repo_names=analyzed_repo_names,
            repos_to_analyze=repos_to_analyze,
            newly_analyzed_repos=[],
            total_repos=len(repos_to_analyze) + len(all_stats)
        )

    @staticmethod
    def _should_exit_early(state: 'AnalysisState') -> bool:
        """Check if analysis should exit early"""
        if not state.repos_to_analyze and not state.all_stats:
            logger.warning("No repositories found matching the criteria")
            return True

        if not state.repos_to_analyze and state.all_stats:
            logger.info("All repositories have already been analyzed according to checkpoint")
            return True

        return False

    def _prepare_for_analysis(self) -> None:
        """Prepare system for analysis (rate limit checks, displays)"""
        # Initialize GitHub with rate limit check
        self.github_analyzer.check_rate_limit()

        # Display initial rate limit usage
        rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
        self.rate_display.display_once()
        rprint("[bold]-------------------------------[/bold]")

    def _execute_analysis(self, state: 'AnalysisState') -> None:
        """Execute the main analysis logic"""
        should_use_parallel = (
                self.github_analyzer.max_workers > 1 and
                len(state.repos_to_analyze) > 1
        )

        if should_use_parallel:
            state.all_stats = self._analyze_parallel(
                state.repos_to_analyze,
                state.all_stats,
                state.analyzed_repo_names,
                state.newly_analyzed_repos,
                state.total_repos
            )
        else:
            state.all_stats = self._analyze_sequential(
                state.repos_to_analyze,
                state.all_stats,
                state.analyzed_repo_names,
                state.newly_analyzed_repos,
                state.total_repos
            )

    def _finalize_analysis(self, state: 'AnalysisState') -> None:
        """Finalize analysis (cleanup, final displays)"""
        # Final rate limit status display
        rprint("\n[bold]--- Final API Rate Status ---[/bold]")
        self.rate_display.display_once()
        rprint("[bold]----------------------------[/bold]")

        # Clean up checkpoint if all repositories were analyzed
        if self._should_cleanup_checkpoint(state):
            self._cleanup_checkpoint()

    def _should_cleanup_checkpoint(self, state: 'AnalysisState') -> bool:
        """Determine if checkpoint should be cleaned up"""
        return (
                self.config.get("ENABLE_CHECKPOINTING", False) and
                not state.repos_to_analyze
        )

    def _cleanup_checkpoint(self) -> None:
        """Clean up checkpoint file"""
        with contextlib.suppress(Exception):
            checkpoint_file = self.config.get("CHECKPOINT_FILE")
            if checkpoint_file:
                Path(checkpoint_file).unlink(missing_ok=True)

    def _handle_analysis_error(self, error: Exception, state: 'AnalysisState' = None) -> List[RepoStats]:
        """Handle analysis errors with appropriate logging and checkpointing"""
        if isinstance(error, RateLimitExceededException):
            logger.error("GitHub API rate limit exceeded during repository analysis")
        elif isinstance(error, GithubException):
            logger.error(f"GitHub API error: {error}")
        else:
            logger.error(f"Unexpected error during analysis: {error}")

        # Save checkpoint if we have progress and checkpointing is enabled
        if state and state.all_stats and self.config.get("ENABLE_CHECKPOINTING", False):
            self.github_analyzer.save_checkpoint(
                state.all_stats,
                state.analyzed_repo_names,
                state.repos_to_analyze
            )

        return state.all_stats if state else []

    def _analyze_parallel(self, repos_to_analyze: List[Repository], all_stats: List[RepoStats],
                          analyzed_repo_names: List[str], newly_analyzed_repos: List[Repository],
                          total_repos: int) -> List[RepoStats]:
        """Analyze repositories using parallel processing"""
        logger.info(f"Using parallel processing with {self.github_analyzer.max_workers} workers")

        with tqdm(total=total_repos, initial=len(all_stats),
                  desc="Analyzing repositories", leave=True, colour='green') as pbar:

            # Update progress bar for already analyzed repos from checkpoint
            if all_stats:
                pbar.set_description("Analyzing repositories (resumed from checkpoint)")

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
                names_new_analyzed_repos = [r.name for r in newly_analyzed_repos]
                _all_analyzed_repo_names = analyzed_repo_names + names_new_analyzed_repos
                _remaining_batch_repos = remaining_repos + batch

                if self.github_analyzer.check_ratelimit_and_checkpoint(all_stats, _all_analyzed_repo_names, _remaining_batch_repos):
                    logger.info("Stopping analysis due to approaching API rate limit")
                    return all_stats

                with concurrent.futures.ThreadPoolExecutor(max_workers=self.github_analyzer.max_workers) as executor:
                    # Submit all tasks for this batch
                    future_to_repo = {executor.submit(self.github_analyzer.analyze_single_repository, repo): repo for
                                      repo in
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
                self.github_analyzer.save_checkpoint(all_stats, analyzed_repo_names, remaining_repos)

        return all_stats

    def _analyze_sequential(self, repos_to_analyze: List[Repository], all_stats: List[RepoStats],
                            analyzed_repo_names: List[str], newly_analyzed_repos: List[Repository],
                            total_repos: int) -> List[RepoStats]:
        """Analyze repositories using sequential processing"""
        with tqdm(total=total_repos, initial=len(all_stats),
                  desc="Analyzing repositories", leave=True, colour='green') as pbar:

            # Update progress bar for already analyzed repos from checkpoint
            if all_stats:
                pbar.set_description("Analyzing repositories (resumed from checkpoint)")

            for repo in repos_to_analyze:
                # Periodically check and display rate limit status
                if len(newly_analyzed_repos) % 5 == 0 or len(newly_analyzed_repos) == 0:
                    rprint("\n[bold]--- Current API Rate Status ---[/bold]")
                    self.rate_display.display_once()
                    rprint("[bold]-------------------------------[/bold]")

                # Check if we need to checkpoint
                stop_repo = repos_to_analyze[repos_to_analyze.index(repo):]
                if self.github_analyzer.check_ratelimit_and_checkpoint(all_stats, analyzed_repo_names, stop_repo):
                    logger.info("Stopping analysis due to approaching API rate limit")
                    return all_stats

                try:
                    repo_stats = self.github_analyzer.analyze_single_repository(repo)
                    all_stats.append(repo_stats)
                    newly_analyzed_repos.append(repo)
                    analyzed_repo_names.append(repo.name)
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"Failed to analyze {repo.name}: {e}")

            # Final checkpoint after all repos complete
            if self.config["ENABLE_CHECKPOINTING"] and newly_analyzed_repos:
                self.github_analyzer.save_checkpoint(all_stats, analyzed_repo_names, [])

        return all_stats


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
            rprint("[dim]The script will automatically continue after the wait period.[/dim]")
            wait_time = 3600  # Cap to 1 hour for the progress bar

        # Show progress bar for the wait
        wait_seconds = int(wait_time)
        for _ in tqdm(range(wait_seconds), desc=desc, colour="yellow", leave=True):
            time.sleep(1)

    def check_ratelimit_and_checkpoint(self, all_stats, analyzed_repo_names, remaining_repos):
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
        file_analyzer = AnalyzerRepoFiles(self)
        return file_analyzer.analyze(repo)

    @staticmethod
    def calculate_scores(repo_stats: Dict[str, Any], repo: Repository) -> Dict[str, float]:
        """Calculate various quality scores for a repository"""
        score_calculator = ScoreCalculator()
        return score_calculator.calculate_scores(repo_stats, repo)

    def analyze_single_repository(self, repo: Repository) -> RepoStats:
        """Analyze a single repository and return detailed statistics"""
        single_analyzer = SingleRepoAnalyzer(self)
        return single_analyzer.analyze(repo)

    def detect_anomalies(self, repo_stats):
        detector = AnomalyDetctor(self.config)
        detector.detect(repo_stats)

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
        repos_analyzer = ReposAnalyzer(self)
        return repos_analyzer.analyze(repositories)
