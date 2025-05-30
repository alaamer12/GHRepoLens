"""
Utility Classes and Functions for GitHub Repository Analyzer

This module provides common utility functions and classes used across the GitHub
Repository Analyzer tool. It includes utilities for handling GitHub API rate limits,
checkpointing analysis progress, file operations, and string/path manipulation.

Key components:
- GitHubRateDisplay: Class for displaying and monitoring GitHub API rate limits
- Checkpoint: Class for saving and loading analysis checkpoints
- File operations: Functions for file type detection and analysis
"""

import time
import pickle
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Set, Tuple

from tqdm.auto import tqdm
from config import logger, Configuration

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime object has UTC timezone information.
    
    Args:
        dt: Datetime object to ensure timezone information for
        
    Returns:
        Datetime object with UTC timezone, or None if input was None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

class GitHubRateDisplay:
    """
    Class for displaying GitHub API rate usage information interactively.
    
    Provides real-time monitoring of GitHub API rate limits with a
    terminal-based display. Can run in a background thread to continuously
    update rate information.
    """
    
    def __init__(self) -> None:
        """Initialize the display handler with default settings."""
        self.running = False
        self.thread = None
        self.rate_data: Dict[str, Any] = {
            "used": 0,
            "remaining": 0,
            "limit": 0,
            "reset_time": None
        }
        self.update_interval = 30  # Update interval in seconds
        self.last_displayed = 0  # Track when the rate was last displayed
        self.box_width = 80  # Default box width
        
    def set_rate_data(self, used: int, remaining: int, limit: int, reset_time: Optional[datetime]) -> None:
        """
        Update the rate usage data.
        
        Args:
            used: Number of API requests used in this period
            remaining: Number of API requests remaining in this period
            limit: Total API request limit for this period
            reset_time: Datetime when the rate limit will reset
        """
        self.rate_data = {
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "reset_time": reset_time
        }
    
    def update_from_api(self, github_client: Any) -> bool:
        """
        Update rate data directly from GitHub API client.
        
        Args:
            github_client: GitHub API client instance to fetch rate data from
            
        Returns:
            True if rate data was successfully updated, False otherwise
        """
        try:
            rate_limit = github_client.get_rate_limit().core
            remaining = rate_limit.remaining
            limit = rate_limit.limit
            reset_time = rate_limit.reset
            used = limit - remaining
            
            self.set_rate_data(used, remaining, limit, reset_time)
            return True
        except Exception as e:
            logger.error(f"Error updating rate data from API: {e}")
            return False
    
    def start(self, update_interval: int = 30, github_client: Optional[Any] = None) -> bool:
        """
        Start displaying the rate usage information periodically.
        
        Args:
            update_interval: How often to update the display in seconds
            github_client: GitHub API client instance to fetch rate data from
            
        Returns:
            True if monitoring started, False otherwise
        """
        import threading
        
        self.update_interval = update_interval
        self.github_client = github_client
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            return True
        return False
    
    def stop(self) -> bool:
        """
        Stop displaying the rate usage information.
        
        Returns:
            True if monitoring was successfully stopped, False otherwise
        """
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
            return True
        return False
    
    def _update_loop(self) -> None:
        """
        Main loop for updating the display.
        
        This method runs in a separate thread to periodically update
        the rate limit display.
        """
        import time
        
        while self.running:
            # Update from API if client is available
            if hasattr(self, 'github_client') and self.github_client:
                self.update_from_api(self.github_client)
                
            # Display the box with current data
            self._display_box()
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    def _get_terminal_width(self) -> int:
        """
        Get the width of the terminal.
        
        Returns:
            Width of the terminal in characters, defaults to 80 if not determinable
        """
        try:
            term_width, _ = shutil.get_terminal_size((80, 20))
            return min(term_width - 4, 80)  # Leave some margin
        except Exception:
            return 80  # Default fallback
    
    def _clear_previous_display(self, num_lines: int = 8) -> None:
        """
        Clear the previous display by moving cursor up and clearing lines.
        
        Args:
            num_lines: Number of lines to clear from the previous display
        """
        if self.last_displayed > 0:
            # Move up to the beginning of the previous box
            sys.stdout.write(f"\033[{num_lines}A")
            
            # Clear each line of the previous box
            for _ in range(num_lines):
                sys.stdout.write("\033[2K")  # Clear entire line
                sys.stdout.write("\033[1B")  # Move down one line
            
            # Move back up to start position
            sys.stdout.write(f"\033[{num_lines}A")
        
        self.last_displayed = time.time()
    
    def _display_box(self, force_update: bool = False) -> None:
        """
        Display the GitHub API rate usage information in a box.
        
        Args:
            force_update: Whether to update the display regardless of last update time
        """
        # Skip if recently displayed and not forced
        current_time = time.time()
        if not force_update and (current_time - self.last_displayed) < self.update_interval:
            return
            
        # Get terminal width for box sizing
        self.box_width = self._get_terminal_width()
        
        # Extract rate data
        used = self.rate_data["used"]
        remaining = self.rate_data["remaining"]
        limit = self.rate_data["limit"]
        reset_time = self.rate_data["reset_time"]
        
        # Calculate time until reset
        now = datetime.now().replace(tzinfo=timezone.utc)
        minutes_until_reset = 0
        if reset_time:
            minutes_until_reset = (reset_time - now).total_seconds() / 60
        
        # Calculate percentage and progress bar
        percentage = (used / limit * 100) if limit > 0 else 0
        bar_length = self.box_width - 30  # Leave space for text
        filled_length = int(bar_length * used // limit) if limit > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Clear previous display if needed
        self._clear_previous_display()
        
        # Draw the box with updated information
        sys.stdout.write("┌" + "─" * (self.box_width - 2) + "┐\n")
        sys.stdout.write(f"│ 📊 GitHub API Rate Usage {' ' * (self.box_width - 27)}│\n")
        sys.stdout.write(f"│ Used: {used:,}/{limit:,} ({percentage:.1f}%)  {' ' * (self.box_width - 30 - len(str(used)) - len(str(limit)) - 9)}│\n")
        sys.stdout.write(f"│ [{bar}] {' ' * (self.box_width - bar_length - 5)}│\n")
        sys.stdout.write(f"│ Remaining: {remaining:,} requests {' ' * (self.box_width - 24 - len(str(remaining)))}│\n")
        sys.stdout.write(f"│ Reset in: {minutes_until_reset:.1f} minutes {' ' * (self.box_width - 26 - len(f'{minutes_until_reset:.1f}'))}│\n")
        
        # Handle the case where reset_time is None
        if reset_time:
            reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
            sys.stdout.write(f"│ Reset time: {reset_time_str} UTC {' ' * (self.box_width - 46)}│\n")
        else:
            sys.stdout.write(f"│ Reset time: Unknown {' ' * (self.box_width - 29)}│\n")
        
        sys.stdout.write("└" + "─" * (self.box_width - 2) + "┘\n")
        sys.stdout.flush()
        
        self.last_displayed = current_time
    
    def display_once(self) -> None:
        """Display the rate usage information once immediately."""
        self._display_box(force_update=True)
    
    def is_low_on_requests(self, threshold: int) -> bool:
        """
        Check if the remaining requests are below the threshold.
        
        Args:
            threshold: Threshold value to check against
            
        Returns:
            True if remaining requests are below or equal to threshold, False otherwise
        """
        return self.rate_data["remaining"] <= threshold

class Checkpoint:
    """
    Class to handle saving and loading analysis checkpoints.
    
    Manages serialization and deserialization of analysis state to allow
    resuming interrupted analysis operations.
    """
    
    def __init__(self, config: Configuration, username: str) -> None:
        """
        Initialize checkpoint manager with configuration and username.
        
        Args:
            config: Configuration dictionary containing checkpoint settings
            username: GitHub username being analyzed
        """
        self.config = config
        self.username = username
        self.checkpoint_path = Path(config["CHECKPOINT_FILE"])
        self.api_requests_made = 0
    
    def save(self, all_stats: List, analyzed_repo_names: List[str], remaining_repos: List) -> None:
        """
        Save a checkpoint of the current analysis state.
        
        Args:
            all_stats: List of RepoStats objects for the analyzed repositories
            analyzed_repo_names: List of repository names that have been analyzed
            remaining_repos: List of Repository objects that remain to be analyzed
        """
        if not self.config["ENABLE_CHECKPOINTING"]:
            return
            
        logger.info("Saving analysis checkpoint")
        
        # Prepare checkpoint data
        checkpoint_data = {
            'timestamp': datetime.now().replace(tzinfo=timezone.utc).isoformat(),
            'username': self.username,
            'analyzed_repos': analyzed_repo_names,
            'remaining_repo_names': [repo.name for repo in remaining_repos],
            'all_stats': all_stats,
            'api_requests_made': self.api_requests_made
        }
        
        # Save to file
        try:
            with open(self.checkpoint_path, 'wb') as f:
                pickle.dump(checkpoint_data, f)
            logger.info(f"Checkpoint saved to {self.checkpoint_path}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load(self) -> Optional[Dict[str, Any]]:
        """
        Load the latest checkpoint if it exists.
        
        Returns:
            Dictionary containing checkpoint data, or None if no checkpoint or not enabled
        """
        if not (self.config["ENABLE_CHECKPOINTING"] and self.config["RESUME_FROM_CHECKPOINT"]):
            return None
            
        if not self.checkpoint_path.exists():
            logger.info("No checkpoint file found")
            return None
            
        try:
            with open(self.checkpoint_path, 'rb') as f:
                checkpoint_data = pickle.load(f)
                
            # Validate checkpoint data
            if checkpoint_data.get('username') != self.username:
                logger.warning(f"Checkpoint is for a different user ({checkpoint_data.get('username')}), not using it")
                return None
                
            # Extract metadata
            timestamp = checkpoint_data.get('timestamp', 'unknown')
            analyzed_count = len(checkpoint_data.get('analyzed_repos', []))
            remaining_count = len(checkpoint_data.get('remaining_repo_names', []))
            
            logger.info(f"Loaded checkpoint from {timestamp}")
            logger.info(f"Checkpoint contains {analyzed_count} analyzed repos and {remaining_count} remaining repos")
            
            self.api_requests_made = checkpoint_data.get('api_requests_made', 0)
            return checkpoint_data
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

def visualize_wait(wait_time: float, desc: str = "Rate limit exceeded, waiting") -> None:
    """
    Display an animated progress bar while waiting for rate limit to reset.
    
    Args:
        wait_time: Time to wait in seconds
        desc: Description to show in the progress bar
    """
    # Use tqdm to create a nice progress bar for the wait time
    with tqdm(
        total=int(wait_time),
        desc=desc,
        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} seconds',
        colour='yellow'
    ) as pbar:
        for _ in range(int(wait_time)):
            time.sleep(1)
            pbar.update(1)

def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is likely binary based on its extension.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is likely binary, False otherwise
    """
    from config import BINARY_EXTENSIONS
    return any(file_path.endswith(ext) for ext in BINARY_EXTENSIONS)

def is_config_file(file_path: str) -> bool:
    """
    Check if a file is a configuration file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is a configuration file, False otherwise
    """
    from config import CONFIG_FILES
    return any(file_path.endswith(name) for name in CONFIG_FILES)

def is_cicd_file(file_path: str) -> bool:
    """
    Check if a file is related to CI/CD.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is a CI/CD file, False otherwise
    """
    from config import CICD_FILES
    return any(cicd_path in file_path for cicd_path in CICD_FILES)

def is_test_file(file_path: str) -> bool:
    """
    Check if a file is a test file.
    
    Uses multiple heuristics to determine if a file is likely to be a test file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is likely a test file, False otherwise
    """
    path_lower = file_path.lower()
    
    # Check for directory-based patterns
    if '/test/' in path_lower or '/tests/' in path_lower or '\\test\\' in path_lower or '\\tests\\' in path_lower:
        return True
        
    # Check for file naming patterns
    file_name = Path(file_path).name.lower()
    if (file_name.startswith('test_') or 
        file_name.endswith('_test.py') or 
        file_name.endswith('test.js') or 
        file_name.endswith('spec.js') or 
        file_name.endswith('test.tsx') or 
        file_name.endswith('spec.tsx') or 
        file_name.endswith('test.ts') or 
        file_name.endswith('spec.ts')):
        return True
        
    return False

def get_file_language(file_path: str) -> str:
    """
    Determine the programming language of a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name, or "Unknown" if not recognized
    """
    from config import LANGUAGE_EXTENSIONS
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(ext, "Unknown")

def is_excluded_path(file_path: str) -> bool:
    """
    Check if a file path should be excluded from analysis.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if the path should be excluded, False otherwise
    """
    from config import EXCLUDED_DIRECTORIES
    
    # Convert to Path object for easier path manipulation
    path = Path(file_path)
    
    # Check if any part of the path matches excluded directories
    path_parts = path.parts
    for part in path_parts:
        if part.lower() in EXCLUDED_DIRECTORIES:
            return True
            
    # Special case for __pycache__, .git, and other dot directories
    for part in path_parts:
        if part.startswith('__') and part.endswith('__'):
            return True
        if part.startswith('.') and len(part) > 1:
            # Allow .github and some other important dot directories
            if part.lower() not in {'.github', '.circleci', '.vscode', '.idea'}:
                return True
    
    return False

def count_lines_of_code(content: str, file_path: str) -> int:
    """
    Count relevant lines of code in a file, excluding comments and blank lines.
    
    Different rules are applied based on the file type to exclude comments properly.
    
    Args:
        content: File content as a string
        file_path: Path to the file (used to determine language)
        
    Returns:
        Number of relevant lines of code
    """
    lines = content.splitlines()
    extension = Path(file_path).suffix.lower()
    
    # Skip binary files
    if is_binary_file(file_path):
        return 0
        
    # Different comment patterns for different languages
    if extension in {'.py', '.pyx', '.pyi'}:
        in_multiline = False
        code_lines = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Skip completely empty lines
            if not stripped:
                continue
                
            # Handle multiline string literals that might be docstrings
            if in_multiline:
                if '"""' in stripped or "'''" in stripped:
                    in_multiline = False
                continue
                
            if stripped.startswith('#'):
                continue  # Skip comment lines
                
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_multiline = True
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    in_multiline = False
                continue
                
            code_lines += 1
            
        return code_lines
        
    elif extension in {'.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.cs', '.go', '.swift'}:
        in_multiline = False
        code_lines = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Skip completely empty lines
            if not stripped:
                continue
                
            # Handle multiline comments
            if in_multiline:
                if '*/' in stripped:
                    in_multiline = False
                continue
                
            if stripped.startswith('//'):
                continue  # Skip single line comment
                
            if stripped.startswith('/*'):
                in_multiline = True
                if '*/' in stripped:
                    in_multiline = False
                continue
                
            code_lines += 1
            
        return code_lines
        
    else:
        # For all other files, just count non-empty lines
        return sum(1 for line in lines if line.strip()) 
