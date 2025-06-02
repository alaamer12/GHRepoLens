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
- Checkpoint functionality to resume interrupted analysis
"""

import os
import atexit
from pathlib import Path
from typing import List, Optional

from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from tqdm.auto import tqdm

from config import DEFAULT_CONFIG, Configuration, create_sample_config, load_config_from_file, setup_logging, logger, shutdown_logging
from lens import GithubLens
from models import RepoStats

# Register shutdown_logging to be called when the program exits
atexit.register(shutdown_logging)

def run_analysis(
    token: str,
    username: str,
    demo_mode: bool = False,
    config_file: Optional[str] = None,
    test_mode: bool = False
) -> None:
    """
    Run GitHub repository analysis for the specified user.
    
    Performs comprehensive analysis of GitHub repositories, generates reports,
    and handles exceptions gracefully.

    Args:
        token: GitHub personal access token for API authentication
        username: GitHub username whose repositories will be analyzed
        demo_mode: If True, only analyze up to 10 repos (default: False)
        config_file: Path to custom configuration file (default: None)
    """
    logger.info(
        f"Starting GitHub Repository Analyzer{' (DEMO MODE)' if demo_mode else ''}"
    )

    create_sample_config()
    config: Configuration = DEFAULT_CONFIG.copy()

    if config_file and os.path.exists(config_file):
        logger.info(f"Loading configuration from {config_file}")
        file_config = load_config_from_file(config_file)
        config.update(file_config)

    config["GITHUB_TOKEN"] = token
    config["USERNAME"] = username

    if demo_mode:
        config["CHECKPOINT_FILE"] = "github_analyzer_demo_checkpoint.pkl"

    try:
        analyzer = GithubLens(config["GITHUB_TOKEN"], config["USERNAME"], config)
        _handle_checkpoint_message(config)

        if demo_mode:
            all_stats = _run_demo_mode(token, username, analyzer, test_mode=test_mode)
            if not all_stats:
                logger.error("❌ No repositories analyzed in demo mode")
                return
        else:
            all_stats = analyzer.analyze_all_repositories()
            if not all_stats:
                logger.error("❌ No repositories found or analyzed")
                return

        _generate_reports(analyzer, all_stats)
        _print_summary(analyzer, all_stats, demo_mode)

    except RateLimitExceededException:
        _handle_rate_limit_exceeded()
    except GithubException as e:
        _handle_github_exception(e)
    except Exception as e:
        _handle_generic_exception(e)
        raise


def _handle_checkpoint_message(config: Configuration) -> None:
    """
    Display checkpoint resume message if applicable.
    
    Args:
        config: Configuration dictionary containing checkpoint settings
    """
    checkpoint_exists = Path(config["CHECKPOINT_FILE"]).exists()
    if checkpoint_exists and config.get("RESUME_FROM_CHECKPOINT", False):
        print(f"\n📋 Found existing checkpoint file")
        print(f"🔄 Will resume analysis from checkpoint")


def _run_demo_mode(token: str, username: str, analyzer: GithubLens, test_mode: bool = False) -> List[RepoStats]:
    """
    Run analysis in demo mode (up to 10 repositories).
    
    Fetches and analyzes up to 10 repositories for demonstration purposes.
    
    Args:
        token: GitHub personal access token
        username: GitHub username to analyze
        analyzer: Initialized GithubLens instance
        
    Returns:
        List of RepoStats objects for analyzed repositories
    """
    github = Github(token)
    
    # Check if we're analyzing the authenticated user (to access private repos)
    auth_user = github.get_user()
    if username == auth_user.login:
        # If analyzing ourselves, use the authenticated user to get all repos including private
        print(f"\n👤 Analyzing authenticated user {username}, will include private repositories")
        user = auth_user
    else:
        # Otherwise get the specified user (which will only return public repos)
        user = github.get_user(username)
    
    demo_size = 10 if not test_mode else 1
    all_repos = list(user.get_repos())[:demo_size]

    print(f"\n🔬 Running demo analysis on up to {demo_size} repositories")
    print("\n--- Initial API Rate Status ---")
    analyzer.rate_display.display_once()
    print("-------------------------------")

    demo_stats: List[RepoStats] = []
    with tqdm(
        total=min(demo_size, len(all_repos)),
        desc="Analyzing repositories",
        leave=True,
        colour='green'
    ) as pbar:
        for repo in all_repos:
            try:
                stats = analyzer.analyze_single_repository(repo)
                demo_stats.append(stats)
                pbar.update(1)
            except Exception as e:
                logger.error(f"Failed to analyze {repo.name}: {e}")
                continue

            if analyzer.analyzer.check_rate_limit_and_checkpoint(
                demo_stats, [s.name for s in demo_stats], []
            ):
                break
    return demo_stats


def _generate_reports(analyzer: GithubLens, all_stats: List[RepoStats]) -> None:
    """
    Generate all reports for the analysis.
    
    Creates detailed reports, aggregated statistics, visualizations, 
    and JSON data export.
    
    Args:
        analyzer: GithubLens instance to use for report generation
        all_stats: List of repository statistics to include in reports
    """
    print("\n📝 Generating reports...")
    with tqdm(total=4, desc="Generating reports", colour='blue') as pbar:
        analyzer.generate_detailed_report(all_stats)
        pbar.update(1)
        analyzer.generate_aggregated_report(all_stats)
        pbar.update(1)
        analyzer.create_visualizations(all_stats)
        pbar.update(1)
        analyzer.save_json_report(all_stats)
        pbar.update(1)


def _print_summary(analyzer: GithubLens, all_stats: List[RepoStats], demo_mode: bool) -> None:
    """
    Print summary and report locations.
    
    Displays a summary of the analysis results and the locations of
    generated reports.
    
    Args:
        analyzer: GithubLens instance used for the analysis
        all_stats: List of repository statistics that were analyzed
        demo_mode: Whether the analysis was run in demo mode
    """
    print(f"\n🎉 Analysis Complete!")
    print(f"📊 Analyzed {len(all_stats)} repositories{' (demo mode)' if demo_mode else ''}")
    print(f"📁 Reports saved to: {analyzer.reports_dir.absolute()}")
    print(f"📄 Files generated:")
    print(f"   • repo_details.md - Detailed per-repository analysis")
    print(f"   • aggregated_stats.md - Summary statistics")
    print(f"   • visual_report.html - Interactive dashboard")
    print(f"   • repository_data.json - Raw data for programmatic use")
    print(f"\n📊 GitHub API Usage:")
    print(f"   • Total API requests used: {analyzer.api_requests_made}")


def _handle_rate_limit_exceeded() -> None:
    """
    Handle GitHub API rate limit exceeded exception.
    
    Provides user guidance on how to proceed when the rate limit is exceeded.
    """
    logger.error("❌ GitHub API rate limit exceeded. Please try again later.")
    print("\n⏰ GitHub API rate limit exceeded. Options:")
    print("1. Wait for the rate limit to reset (usually 1 hour)")
    print("2. Use a different GitHub token")
    print("3. Run again later to resume from checkpoint")


def _handle_github_exception(e: GithubException) -> None:
    """
    Handle generic GitHub API exceptions.
    
    Logs the error and informs the user about checkpoint functionality.
    
    Args:
        e: The GitHub exception that was raised
    """
    logger.error(f"❌ GitHub API error: {e}")
    print(f"\n❌ GitHub API error: {e}")
    print(f"💾 Your progress has been saved to checkpoint - run again later to resume")


def _handle_generic_exception(e: Exception) -> None:
    """
    Handle all other exceptions.
    
    Logs the error and informs the user about checkpoint functionality.
    
    Args:
        e: The exception that was raised
    """
    logger.error(f"❌ Error during analysis: {e}")
    print(f"\n❌ Error during analysis: {e}")
    print(f"💾 Your progress has been saved to checkpoint - run again later to resume")


def main() -> None:
    """
    Main entry point for the GitHub Repository Analyzer.
    
    Prompts the user for GitHub token and username if not provided as
    environment variables, and allows selection of demo or full analysis.
    """
    print("🔮 GitHub Repository Analyzer")
    print("-----------------------------")
    
    # Get GitHub token
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("\nPlease enter your GitHub Personal Access Token:")
        print("(Create one at https://github.com/settings/tokens)")
        token = input("> ").strip()
        
        if not token:
            print("❌ No GitHub token provided. Exiting.")
            return
    
    # Get GitHub username
    username = os.getenv("GITHUB_USERNAME")
    if not username:
        print("\nPlease enter the GitHub username to analyze:")
        username = input("> ").strip()
        
        if not username:
            print("❌ No GitHub username provided. Exiting.")
            return
    
    # Ask if demo mode
    print("\nRun in demo mode? (analyzes up to 10 repositories)")
    print("1. Yes - Demo mode")
    print("2. No - Full analysis")
    choice = input("> ").strip()
    
    demo_mode = choice == "1" or choice.lower() == "yes" or choice.lower() == "y"
    
    # Run the analysis
    run_analysis(token, username, demo_mode, test_mode=True)


if __name__ == "__main__":
    main()