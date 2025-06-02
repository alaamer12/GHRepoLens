#!/usr/bin/env python3
"""
GitHub Repository Analyzer - Main Entry Point

This module provides the main entry point for the GitHub Repository Analyzer tool.
It handles configuration loading, user input validation, and executes the analysis
of GitHub repositories. The analyzer provides detailed insights about repositories
including code quality, activity metrics, and community engagement.

Main features:
- Analysis of all repositories for a GitHub user
- Generation of detailed and aggregated reports
- Creation of visualizations for repository metrics
- Support for demo mode to analyze a limited set of repositories
- Test mode for quick validation
- Checkpoint functionality to resume interrupted analysis
"""

import os
import atexit
import asyncio
from pathlib import Path
from typing import List, Optional

import dotenv
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from github import Github
from github.GithubException import GithubException, RateLimitExceededException

from console import console, rprint, logger, print_header, print_info, print_warning, print_error, print_success, create_progress_bar
from config import DEFAULT_CONFIG, Configuration, create_sample_config, load_config_from_file, shutdown_logging
from lens import GithubLens
from models import RepoStats

# Register shutdown_logging to be called when the program exits
atexit.register(shutdown_logging)

async def run_analysis(
    token: str,
    username: str,
    mode: str = "full",
    config_file: Optional[str] = None,
) -> None:
    """
    Run GitHub repository analysis for the specified user.
    
    Performs comprehensive analysis of GitHub repositories, generates reports,
    and handles exceptions gracefully.

    Args:
        token: GitHub personal access token for API authentication
        username: GitHub username whose repositories will be analyzed
        mode: Analysis mode ("demo", "full", or "test")
        config_file: Path to custom configuration file (default: None)
    """
    demo_mode = mode == "demo"
    test_mode = mode == "test"

    with console.status(f"[bold green]Starting GitHub Repository Analyzer ({mode.upper()} MODE)"):
        logger.info(
            f"Starting GitHub Repository Analyzer ({mode.upper()} MODE)"
        )

        create_sample_config()
        config: Configuration = DEFAULT_CONFIG.copy()

        if config_file and os.path.exists(config_file):
            logger.info(f"Loading configuration from {config_file}")
            file_config = load_config_from_file(config_file)
            config.update(file_config)

        config["GITHUB_TOKEN"] = token
        config["USERNAME"] = username

        if demo_mode or test_mode:
            config["CHECKPOINT_FILE"] = f"github_analyzer_{mode}_checkpoint.pkl"

    try:
        analyzer = GithubLens(config["GITHUB_TOKEN"], config["USERNAME"], config)
        await _handle_checkpoint_message(config)

        if demo_mode or test_mode:
            all_stats = await _run_demo_mode(token, username, analyzer, test_mode)
            if not all_stats:
                logger.error(f"❌ No repositories analyzed in {mode} mode")
                return
        else:
            all_stats = await _run_full_analysis(analyzer)
            if not all_stats:
                logger.error("❌ No repositories found or analyzed")
                return

        await _generate_reports(analyzer, all_stats)
        _print_summary(analyzer, all_stats, mode)

    except RateLimitExceededException:
        _handle_rate_limit_exceeded()
    except GithubException as e:
        _handle_github_exception(e)
    except Exception as e:
        _handle_generic_exception(e)
        raise


async def _handle_checkpoint_message(config: Configuration) -> None:
    """
    Display checkpoint resume message if applicable.
    
    Args:
        config: Configuration dictionary containing checkpoint settings
    """
    checkpoint_exists = Path(config["CHECKPOINT_FILE"]).exists()
    if checkpoint_exists and config.get("RESUME_FROM_CHECKPOINT", False):
        print_info("Found existing checkpoint file")
        print_success("Will resume analysis from checkpoint")


async def _run_demo_mode(token: str, username: str, analyzer: GithubLens, test_mode: bool = False) -> List[RepoStats]:
    """
    Run analysis in demo mode (up to 10 repositories) or test mode (1 repository).
    
    Fetches and analyzes repositories for demonstration or testing purposes.
    
    Args:
        token: GitHub personal access token
        username: GitHub username to analyze
        analyzer: Initialized GithubLens instance
        test_mode: Whether to run in test mode (1 repo only)
        
    Returns:
        List of RepoStats objects for analyzed repositories
    """
    github = Github(token)
    
    # Check if we're analyzing the authenticated user (to access private repos)
    auth_user = github.get_user()
    if username == auth_user.login:
        # If analyzing ourselves, use the authenticated user to get all repos including private
        print_info(f"Analyzing authenticated user {username}, will include private repositories")
        user = auth_user
    else:
        # Otherwise get the specified user (which will only return public repos)
        user = github.get_user(username)
    
    demo_size = 1 if test_mode else 10
    all_repos = list(user.get_repos())[:demo_size]

    mode_name = "test" if test_mode else "demo"
    print_header(f"Running {mode_name} analysis on up to {demo_size} repositories")
    rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
    analyzer.rate_display.display_once()
    rprint("[bold]-------------------------------[/bold]")

    demo_stats: List[RepoStats] = []
    # Use our new progress bar from console
    progress = create_progress_bar(transient=False)
    
    with progress:
        task = progress.add_task(f"Analyzing repositories", total=min(demo_size, len(all_repos)))
        for repo in all_repos:
            try:
                stats = analyzer.analyze_single_repository(repo)
                demo_stats.append(stats)
                progress.update(task, advance=1, description=f"Analyzed {repo.name}")
            except Exception as e:
                logger.error(f"Failed to analyze {repo.name}: {e}")
                progress.update(task, advance=1, description=f"Failed to analyze {repo.name}")
                continue

            if analyzer.analyzer.check_rate_limit_and_checkpoint(
                demo_stats, [s.name for s in demo_stats], []
            ):
                break

    return demo_stats


async def _run_full_analysis(analyzer: GithubLens) -> List[RepoStats]:
    """
    Run full analysis of all repositories.
    
    Args:
        analyzer: Initialized GithubLens instance
        
    Returns:
        List of RepoStats objects for all analyzed repositories
    """
    print_header("Running full analysis of all repositories")
    rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
    analyzer.rate_display.display_once()
    rprint("[bold]-------------------------------[/bold]")

    # Run repository analysis and wait for completion
    return analyzer.analyze_all_repositories()


async def _generate_reports(analyzer: GithubLens, all_stats: List[RepoStats]) -> None:
    """
    Generate reports and visualizations for analyzed repositories.
    
    Args:
        analyzer: Initialized GithubLens instance
        all_stats: List of RepoStats objects for analyzed repositories
    """
    with console.status("[bold green]Generating reports and visualizations...") as status:
        logger.info("Generating reports")
        await asyncio.to_thread(analyzer.generate_report, all_stats)
        
        logger.info("Generating interactive dashboard")
        status.update("[bold green]Creating interactive dashboard...")
        await asyncio.to_thread(analyzer.generate_visualizations, all_stats)
        
        # Create reports directory if it doesn't exist
        Path(analyzer.config["REPORTS_DIR"]).mkdir(exist_ok=True)


def _print_summary(analyzer: GithubLens, all_stats: List[RepoStats], mode: str) -> None:
    """
    Print analysis summary to console.
    
    Args:
        analyzer: Initialized GithubLens instance
        all_stats: List of RepoStats objects for analyzed repositories
        mode: Analysis mode ("demo", "full", or "test")
    """
    analyzed_count = len(all_stats)
    summary_text = (
        f"✅ Analyzed {analyzed_count} repositories for @{analyzer.config['USERNAME']}\n\n"
        f"📊 Generated reports in {analyzer.config['REPORTS_DIR']} directory\n"
        f"📈 Created visualizations and interactive dashboard\n"
    )

    if mode == "demo":
        summary_text += "\n⚠️ Demo mode: Limited to 10 repositories\n"
        summary_text += "🔄 Run without --demo flag to analyze all repositories"
    elif mode == "test":
        summary_text += "\n⚠️ Test mode: Limited to 1 repository for quick testing\n"
        summary_text += "🔄 Run without --test flag to analyze all repositories"

    summary_panel = Panel(
        summary_text, 
        title="[bold]Analysis Complete[/bold]",
        border_style="green",
        padding=(1, 2)
    )
    
    console.print(summary_panel)
    
    # List reports and visualizations
    print_header("Generated Reports & Visualizations")
    
    reports_dir = Path(analyzer.config["REPORTS_DIR"])
    if reports_dir.exists():
        files = list(reports_dir.glob("*.html")) + list(reports_dir.glob("*.json"))
        for file in sorted(files):
            print_info(f"📄 {file.name}")
    else:
        print_warning("Reports directory not found")


def _handle_rate_limit_exceeded() -> None:
    """
    Handle GitHub API rate limit exceeded exception.
    """
    message = (
        "⛔ GitHub API rate limit exceeded!\n\n"
        "The GitHub API enforces rate limits to prevent abuse.\n"
        "Your analysis was interrupted because you reached this limit.\n\n"
        "Please wait an hour for the rate limit to reset, then try again.\n"
        "Your progress has been saved in the checkpoint file."
    )
    
    console.print(Panel(message, title="[bold red]Rate Limit Exceeded[/bold red]", border_style="red"))
    logger.error("GitHub API rate limit exceeded")


def _handle_github_exception(e: GithubException) -> None:
    """
    Handle GitHub API general exception.
    
    Args:
        e: GitHub exception to handle
    """
    error_message = str(e)
    if len(error_message) > 100:
        error_message = error_message[:100] + "..."
        
    message = (
        f"⚠️ GitHub API error occurred: {e.status} - {error_message}\n\n"
        "This could be due to:\n"
        "- Invalid or expired GitHub token\n"
        "- Network connectivity issues\n"
        "- User or repository not found\n\n"
        "Please check your GitHub token and try again."
    )
    
    console.print(Panel(message, title="[bold yellow]GitHub API Error[/bold yellow]", border_style="yellow"))
    logger.error(f"GitHub exception: {e}")


def _handle_generic_exception(e: Exception) -> None:
    """
    Handle general exception.
    
    Args:
        e: Exception to handle
    """
    error_message = str(e)
    if len(error_message) > 100:
        error_message = error_message[:100] + "..."
        
    message = (
        f"❌ An error occurred: {error_message}\n\n"
        "This could be due to:\n"
        "- Missing or invalid configuration\n"
        "- Network connectivity issues\n"
        "- Unexpected data format\n\n"
        "Check the log file for more details."
    )
    
    console.print(Panel(message, title="[bold red]Error[/bold red]", border_style="red"))
    logger.exception(f"Unexpected error: {e}")


async def main() -> None:
    """
    Main entry point for the GitHub Repository Analyzer tool.
    
    Handles command-line arguments, prompts for required inputs,
    and runs the analysis process.
    """
    # Welcome banner
    print_header("GitHub Repository Analyzer")
    
    # Load environment variables from .env file if present
    dotenv.load_dotenv()
    
    # Check for token from environment variable
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        # Prompt for GitHub token if not in environment
        github_token = Prompt.ask(
            "[bold]GitHub Token[/bold] (create at https://github.com/settings/tokens)",
            password=True
        )
        
    # Check for username from environment variable
    github_username = os.environ.get("GITHUB_USERNAME", "")
    if not github_username:
        # Prompt for GitHub username if not in environment
        github_username = Prompt.ask("[bold]GitHub Username[/bold] (to analyze)")
    
    # Ask for analysis mode
    mode_options = {
        "1": "full",
        "2": "demo",
        "3": "test"
    }
    
    print_header("Select Analysis Mode")
    console.print("[1] Full Analysis - Analyze all repositories (may take longer)")
    console.print("[2] Demo Mode - Analyze up to 10 repositories")
    console.print("[3] Test Mode - Analyze 1 repository (quick test)")
    
    mode_choice = Prompt.ask("[bold]Choose mode[/bold]", choices=["1", "2", "3"], default="1")
    selected_mode = mode_options[mode_choice]
    
    # Ask for custom config file
    use_config = Confirm.ask("Use custom config file?", default=False)
    config_file = None
    if use_config:
        config_file = Prompt.ask("[bold]Path to config file[/bold]", default="config.ini")
    
    # Run the analysis
    await run_analysis(
        token=github_token,
        username=github_username,
        mode=selected_mode,
        config_file=config_file
    )


if __name__ == "__main__":
    asyncio.run(main())