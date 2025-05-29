#!/usr/bin/env python3
"""
GitHub Repository Analyzer - Main entry point

This module provides the main entry point for the GitHub Repository Analyzer tool.
It handles configuration loading, user input validation, and executes the analysis.
"""

import os
from pathlib import Path

from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from tqdm.auto import tqdm

from config import DEFAULT_CONFIG, Configuration, create_sample_config, load_config_from_file, setup_logging
from lens import GithubLens

# Initialize logger
logger = setup_logging()

from typing import Optional

def run_analysis(
    token: str,
    username: str,
    demo_mode: bool = False,
    config_file: Optional[str] = None
) -> None:
    """
    Run GitHub repository analysis for the specified user.

    Args:
        token: GitHub personal access token
        username: GitHub username to analyze
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
            all_stats = _run_demo_mode(token, username, analyzer)
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
    """Display checkpoint resume message if applicable."""
    checkpoint_exists = Path(config["CHECKPOINT_FILE"]).exists()
    if checkpoint_exists and config.get("RESUME_FROM_CHECKPOINT", False):
        print(f"\n📋 Found existing checkpoint file")
        print(f"🔄 Will resume analysis from checkpoint")

def _run_demo_mode(token: str, username: str, analyzer: GithubLens):
    """Run analysis in demo mode (up to 10 repositories)."""
    github = Github(token)
    user = github.get_user(username)
    all_repos = list(user.get_repos())[:10]

    print(f"\n🔬 Running demo analysis on up to 10 repositories")
    print("\n--- Initial API Rate Status ---")
    analyzer.rate_display.display_once()
    print("-------------------------------")

    demo_stats = []
    with tqdm(
        total=min(10, len(all_repos)),
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

            if analyzer.check_rate_limit_and_checkpoint(
                demo_stats, [s.name for s in demo_stats], []
            ):
                break
    return demo_stats

def _generate_reports(analyzer: GithubLens, all_stats) -> None:
    """Generate all reports for the analysis."""
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

def _print_summary(analyzer: GithubLens, all_stats, demo_mode: bool) -> None:
    """Print summary and report locations."""
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
    """Handle GitHub API rate limit exceeded exception."""
    logger.error("❌ GitHub API rate limit exceeded. Please try again later.")
    print("\n⏰ GitHub API rate limit exceeded. Options:")
    print("1. Wait for the rate limit to reset (usually 1 hour)")
    print("2. Use a different GitHub token")
    print("3. Run again later to resume from checkpoint")

def _handle_github_exception(e: Exception) -> None:
    """Handle generic GitHub API exceptions."""
    logger.error(f"❌ GitHub API error: {e}")
    print(f"\n❌ GitHub API error: {e}")
    print(f"💾 Your progress has been saved to checkpoint - run again later to resume")

def _handle_generic_exception(e: Exception) -> None:
    """Handle all other exceptions."""
    logger.error(f"❌ Error during analysis: {e}")
    print(f"\n❌ Error during analysis: {e}")
    print(f"💾 Your progress has been saved to checkpoint - run again later to resume")

def main():
    """
    Main entry point for the GitHub Repository Analyzer.
    Prompts the user for GitHub token and username if not provided.
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
    run_analysis(token, username, demo_mode)

if __name__ == "__main__":
    main()