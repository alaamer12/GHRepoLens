"""
Console and Logging Interface Module

This module provides a centralized interface for console output, printing,
and logging throughout the application. It configures and exports:
- Rich console for formatted terminal output
- Rich print function for colorful text display
- Rich logger for structured logging
- Custom progress bars and status displays
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from rich import box
from rich import print as rich_print
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn
)
from rich.text import Text
from rich.theme import Theme

# Custom theme with consistent color scheme
CONSOLE_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "green",
    "highlight": "magenta",
    "heading": "bold blue",
    "subheading": "bold cyan",
    "progress.percentage": "bright_white",
    "progress.remaining": "bright_white",
    "progress.elapsed": "bright_white",
    "progress.description": "bold cyan",
    "progress.spinner": "bright_magenta",
    "progress.bar": "yellow",
    "progress.bar.finished": "bright_green",
    "rate_limit.low": "red",
    "rate_limit.medium": "yellow",
    "rate_limit.good": "green",
})

# Initialize Rich console with theme
console = Console(theme=CONSOLE_THEME, highlight=True)

# Export rich_print as rprint for consistent naming across the application
rprint = rich_print


# Custom progress columns with labeled time displays
class LabeledElapsedColumn(TimeElapsedColumn):
    """Custom time elapsed column with a label"""

    def render(self, task):
        return Text(f"⏱ Elapsed: {super().render(task)}", style="progress.elapsed")


class LabeledRemainingColumn(TimeRemainingColumn):
    """Custom time remaining column with a label"""

    def render(self, task):
        return Text(f"⏳ Left: {super().render(task)}", style="progress.remaining")


def create_progress_bar(
        expand: bool = True,
        transient: bool = False,
        refresh_per_second: int = 10
) -> Progress:
    """
    Create a consistently styled progress bar for use throughout the application
    
    Args:
        expand: Whether the progress bar should expand to fill available width
        transient: Whether the progress display should be cleared on completion
        refresh_per_second: Number of screen refreshes per second
        
    Returns:
        A configured Rich Progress instance
    """
    return Progress(
        SpinnerColumn(style="progress.spinner"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            bar_width=None,
            complete_style="progress.bar",
            finished_style="progress.bar.finished",
            pulse_style="bright_blue"
        ),
        TaskProgressColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        LabeledElapsedColumn(),
        LabeledRemainingColumn(),
        expand=expand,
        transient=transient,
        refresh_per_second=refresh_per_second,
        console=console,
    )


# Log file configuration
def get_log_filename() -> str:
    """Generate a timestamped log filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"ghlens_{timestamp}.log"


# Configure logging with Rich
def configure_logging(
        log_file: Optional[str] = None,
        log_level: int = logging.INFO,
        log_to_console: bool = True,
        log_to_file: bool = True,
) -> logging.Logger:
    """
    Configure and return the application logger with Rich formatting
    
    Args:
        log_file: Path to log file (if None, a default timestamped file will be used)
        log_level: Logging level (default: INFO)
        log_to_console: Whether to output logs to console
        log_to_file: Whether to output logs to a file
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Set up log filename
    if log_file is None:
        log_file = log_dir / get_log_filename()
    else:
        log_file = Path(log_file)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set up formatters
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Configure console handler with Rich
    if log_to_console:
        console_handler = RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    # Configure file handler
    if log_to_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Return module-specific logger
    logger = logging.getLogger("ghlens")
    return logger


# Create and export the default logger
logger = configure_logging()


# Helper functions for formatted output
def print_header(text: str, style: str = "heading") -> None:
    """Print a formatted header text"""
    console.print(f"\n[{style}]{text}[/{style}]")


def print_subheader(text: str, style: str = "subheading") -> None:
    """Print a formatted subheader text"""
    console.print(f"[{style}]{text}[/{style}]")


def print_info(text: str) -> None:
    """Print info text"""
    console.print(f"[info]ℹ️ {text}[/info]")


def print_success(text: str) -> None:
    """Print success text"""
    console.print(f"[success]✅ {text}[/success]")


def print_warning(text: str) -> None:
    """Print warning text"""
    console.print(f"[warning]⚠️ {text}[/warning]")


def print_error(text: str) -> None:
    """Print error text"""
    console.print(f"[error]❌ {text}[/error]")


def display_panel(title: str, content: str, style: str = "info") -> None:
    """Display content in a styled panel"""
    console.print(Panel(content, title=title, style=style, box=box.ROUNDED))


class RateLimitDisplay:
    """Display GitHub API rate limit information"""

    def __init__(self, console: Console = console):
        """Initialize rate limit display with console"""
        self.console = console
        self.rate_data = {
            "limit": 0,
            "remaining": 0,
            "reset_time": None,
            "used": 0
        }

    def update_from_api(self, github_client: Any) -> None:
        """Update rate limit data from GitHub client"""
        try:
            rate_limit = github_client.get_rate_limit()
            self.rate_data["limit"] = rate_limit.core.limit
            self.rate_data["remaining"] = rate_limit.core.remaining
            self.rate_data["reset_time"] = rate_limit.core.reset
            self.rate_data["used"] = rate_limit.core.limit - rate_limit.core.remaining
        except Exception as e:
            logger.warning(f"Could not update rate limit data: {e}")

    def _get_status_style(self) -> str:
        """Get color style based on remaining requests"""
        remaining = self.rate_data["remaining"]
        limit = self.rate_data["limit"]

        if remaining == 0:
            return "rate_limit.low"
        elif remaining < limit * 0.2:
            return "rate_limit.low"
        elif remaining < limit * 0.5:
            return "rate_limit.medium"
        else:
            return "rate_limit.good"

    def display_once(self) -> None:
        """Display current rate limit status"""
        if not self.rate_data.get("limit"):
            self.console.print("[warning]No rate limit data available yet[/warning]")
            return

        style = self._get_status_style()
        reset_time = self.rate_data["reset_time"]
        reset_str = reset_time if reset_time else "Unknown"

        self.console.print(
            f"[{style}]API Requests: "
            f"{self.rate_data['remaining']}/{self.rate_data['limit']} remaining "
            f"(resets at {reset_str})[/{style}]"
        )


# Export main interfaces
__all__ = [
    'console',
    'rprint',
    'logger',
    'create_progress_bar',
    'print_header',
    'print_subheader',
    'print_info',
    'print_success',
    'print_warning',
    'print_error',
    'display_panel',
    'RateLimitDisplay',
    'configure_logging'
]
