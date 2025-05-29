#!/usr/bin/env python3
"""
Utility classes and functions for GitHub Repository Analyzer.
"""

import time
import pickle
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from tqdm.auto import tqdm
from config import logger, Configuration

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime object has UTC timezone information."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

class GitHubRateDisplay:
    """Class for displaying GitHub API rate usage information interactively."""
    
    def __init__(self):
        """Initialize the display handler."""
        self.running = False
        self.thread = None
        self.rate_data = {
            "used": 0,
            "remaining": 0,
            "limit": 0,
            "reset_time": None
        }
        self.update_interval = 30  # Update interval in seconds
        self.last_displayed = 0  # Track when the rate was last displayed
        self.box_width = 80  # Default box width
        
    def set_rate_data(self, used, remaining, limit, reset_time):
        """Update the rate usage data."""
        self.rate_data = {
            "used": used,
            "remaining": remaining,
            "limit": limit,
            "reset_time": reset_time
        }
    
    def update_from_api(self, github_client):
        """Update rate data directly from GitHub API client."""
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
    
    def start(self, update_interval=30, github_client=None):
        """Start displaying the rate usage information periodically."""
        import threading
        
        self.update_interval = update_interval
        self.github_client = github_client
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            return True
        return False
    
    def stop(self):
        """Stop displaying the rate usage information."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
    
    def _update_loop(self):
        """Main loop for updating the display."""
        import time
        
        while self.running:
            # Update from API if client is available
            if hasattr(self, 'github_client') and self.github_client:
                self.update_from_api(self.github_client)
                
            # Display the box with current data
            self._display_box()
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    def _get_terminal_width(self):
        """Get the width of the terminal."""
        import shutil
        
        try:
            term_width, _ = shutil.get_terminal_size((80, 20))
            return min(term_width - 4, 80)  # Leave some margin
        except Exception:
            return 80  # Default fallback
    
    def _clear_previous_display(self, num_lines=8):
        """Clear the previous display by moving cursor up and clearing lines."""
        import sys
        
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
    
    def _display_box(self, force_update=False):
        """Display the GitHub API rate usage information in a box."""
        import sys
        import time
        from datetime import datetime, timezone
        
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
    
    def display_once(self):
        """Display the rate usage information once immediately."""
        self._display_box(force_update=True)
    
    def is_low_on_requests(self, threshold):
        """Check if the remaining requests are below the threshold."""
        return self.rate_data["remaining"] <= threshold

class Checkpoint:
    """Class to handle saving and loading analysis checkpoints."""
    
    def __init__(self, config: Configuration, username: str):
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
    
    def load(self) -> Dict[str, Any]:
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
                
            # Log checkpoint info
            timestamp = checkpoint_data.get('timestamp', 'Unknown')
            analyzed_count = len(checkpoint_data.get('analyzed_repos', []))
            remaining_count = len(checkpoint_data.get('remaining_repo_names', []))
            
            logger.info(f"Loaded checkpoint from {timestamp}")
            logger.info(f"Checkpoint contains {analyzed_count} analyzed repos and {remaining_count} remaining repos")
            
            # Update API request counter
            self.api_requests_made = checkpoint_data.get('api_requests_made', 0)
            
            return checkpoint_data
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

def visualize_wait(wait_time: float, desc: str):
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

def is_binary_file(file_path: str) -> bool:
    """Check if file is binary based on extension"""
    from config import BINARY_EXTENSIONS
    ext = Path(file_path).suffix.lower()
    return ext in BINARY_EXTENSIONS

def is_config_file(file_path: str) -> bool:
    """Check if file is a configuration file"""
    from config import CONFIG_FILES
    filename = Path(file_path).name.lower()
    return filename in CONFIG_FILES
        
def is_cicd_file(file_path: str) -> bool:
    """Check if file is related to CI/CD configuration"""
    from config import CICD_FILES
    for pattern in CICD_FILES:
        if pattern in file_path.lower():
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

def get_file_language(file_path: str) -> str:
    """Determine language from file extension"""
    from config import LANGUAGE_EXTENSIONS
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(ext, 'Other')

def is_excluded_path(file_path: str) -> bool:
    """Check if a file path should be excluded from analysis"""
    from config import EXCLUDED_DIRECTORIES, BINARY_EXTENSIONS
    
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

def count_lines_of_code(content: str, file_path: str) -> int:
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
