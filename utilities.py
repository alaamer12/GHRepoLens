"""
Utility Classes and Functions for GitHub Repository RunnerAnalyzer

This module provides common utility functions and classes used across the GitHub
Repository RunnerAnalyzer tool. It includes utilities for checkpointing analysis progress,
file operations, and string/path manipulation.

Key components:
- Checkpoint: Class for saving and loading analysis checkpoints
- File operations: Functions for file type detection and analysis
"""

import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from console import logger


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


class Checkpoint:
    """
    Class for checkpointing analysis progress.
    
    Saves and loads checkpoint data to allow resuming analysis.
    """

    def __init__(self, config: Dict[str, Any], username: str) -> None:
        """
        Initialize a checkpoint handler.
        
        Args:
            config: Configuration dictionary
            username: GitHub username being analyzed
        """
        self.checkpoint_dir = Path(config.get("CHECKPOINT_DIR", "checkpoints"))
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.username = username
        self.checkpoint_file = self.checkpoint_dir / f"{username}_checkpoint.pkl"

    def save(self, all_stats: List, analyzed_repo_names: List[str], remaining_repos: List) -> bool:
        """
        Save a checkpoint of the current analysis state.
        
        Args:
            all_stats: List of repository statistics gathered so far
            analyzed_repo_names: List of repository names that have been analyzed
            remaining_repos: List of repository objects that still need to be analyzed
        """
        try:
            # Save a checkpoint with minimal data to allow resuming
            checkpoint_data = {
                'timestamp': datetime.now().replace(tzinfo=timezone.utc),
                'username': self.username,
                'analyzed_repo_names': analyzed_repo_names,
                'all_stats': all_stats,
                # We don't save the remaining_repos with the full repo objects
                # as they can't be properly serialized; instead we just save names
                'remaining_repo_names': [repo.name for repo in remaining_repos],
                'total_repositories': len(analyzed_repo_names) + len(remaining_repos),
                'completed_repositories': len(analyzed_repo_names)
            }

            with open(self.checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint_data, f)

            logger.info(f"Saved checkpoint for {self.username} ({len(analyzed_repo_names)} repos analyzed)")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def load(self) -> Optional[Dict[str, Any]]:
        """
        Load a saved checkpoint if one exists.
        
        Returns:
            Dictionary with checkpoint data if a valid checkpoint exists, otherwise None
        """
        if not self.checkpoint_file.exists():
            logger.info(f"No checkpoint file found for {self.username}")
            return None

        try:
            with open(self.checkpoint_file, 'rb') as f:
                # noinspection PickleLoad
                checkpoint_data = pickle.load(f)

            # Basic validation
            if not isinstance(checkpoint_data, dict) or 'username' not in checkpoint_data:
                logger.warning(f"Invalid checkpoint file for {self.username}")
                return None

            if checkpoint_data['username'] != self.username:
                logger.warning(f"Checkpoint username mismatch: expected {self.username}, "
                               f"found {checkpoint_data['username']}")
                return None

            checkpoint_age = datetime.now().replace(tzinfo=timezone.utc) - checkpoint_data['timestamp']
            hours_old = checkpoint_age.total_seconds() / 3600

            logger.info(f"Found checkpoint for {self.username} from "
                        f"{checkpoint_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({hours_old:.1f} hours ago)")

            logger.info(f"Checkpoint has {checkpoint_data['completed_repositories']} of "
                        f"{checkpoint_data['total_repositories']} repositories analyzed")

            return checkpoint_data

        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None

def is_test_file(file_path: str) -> bool:
    """
    Check if a file is likely a test file based on its name or location.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is likely a test file, False otherwise
    """
    path_str = str(file_path).lower()

    # Check for test directories
    test_dirs = {'/test/', '/tests/', '/spec/', '/specs/', '/unitTests/'}
    if any(test_dir in path_str for test_dir in test_dirs):
        return True

    # Check filename patterns
    filename = Path(file_path).name.lower()
    test_patterns = {'test_', '_test', 'spec_', '_spec'}
    test_suffixes = {'test.py', 'test.js', 'test.ts', 'test.java', 'test.cpp', 'test.cs',
                     'spec.js', 'spec.ts', 'spec.rb', 'test.go', 'test.php', 'test.rb'}

    return (any(pattern in filename for pattern in test_patterns) or
            any(filename.endswith(suffix) for suffix in test_suffixes))


def get_file_language(file_path: str) -> str:
    """
    Attempt to determine programming language from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Inferred programming language name or 'Other'
    """
    ext_to_language = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.jsx': 'JavaScript', '.tsx': 'TypeScript',
        '.java': 'Java', '.cpp': 'C++', '.c': 'C', '.cs': 'C#', '.go': 'Go', '.rb': 'Ruby',
        '.php': 'PHP', '.swift': 'Swift', '.m': 'Objective-C', '.rs': 'Rust', '.scala': 'Scala',
        '.kt': 'Kotlin', '.kts': 'Kotlin', '.sh': 'Shell', '.bash': 'Shell', '.html': 'HTML',
        '.css': 'CSS', '.scss': 'SCSS', '.sass': 'SASS', '.less': 'LESS', '.md': 'Markdown',
        '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML', '.xml': 'XML', '.sql': 'SQL',
        '.dart': 'Dart', '.r': 'R', '.lua': 'Lua', '.pl': 'Perl', '.jl': 'Julia',
        '.tex': 'LaTeX', '.ltx': 'LaTeX', '.latex': 'LaTeX'
    }
    return ext_to_language.get(Path(file_path).suffix.lower(), 'Other')
