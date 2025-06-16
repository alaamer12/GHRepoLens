#!/usr/bin/env python3
"""
GitHub Repository Analyzer - Google Colab Runner

This module provides a simple interface for running the GitHub Repository Analyzer in Google Colab.
It automatically installs required dependencies and handles Colab-specific configurations.
"""

import asyncio
import os
import sys


def setup_environment():
    """
    Set up the environment for running in Google Colab.
    Installs required dependencies if not already installed.
    """
    try:
        import nest_asyncio
        import pygithub
        from rich.console import Console
        print("All dependencies already installed")
    except ImportError:
        print("Installing required dependencies...")
        # Use %pip to avoid conflicts with Colab's package management
        if 'google.colab' in sys.modules:
            from IPython import get_ipython
            get_ipython().system('pip install nest-asyncio PyGithub rich')
        else:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "nest-asyncio", "PyGithub", "rich"])

        # Import after installation
        import nest_asyncio

    # Apply nest_asyncio to allow nested event loops in notebooks
    nest_asyncio.apply()


async def run_analyzer(github_token=None, github_username=None, mode="quicktest"):
    """
    Run the GitHub Repository Analyzer with the specified parameters.
    
    Args:
        github_token: GitHub personal access token (default: from env)
        github_username: GitHub username to analyze (default: from env)
        mode: Analysis mode (default: "quicktest")
    """
    # Import main module
    from main import run_analysis

    # Use provided token or get from environment
    token = github_token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError(
            "GitHub token is required. Set GITHUB_TOKEN environment variable or provide it as a parameter.")

    # Use provided username or get from environment
    username = github_username or os.environ.get("GITHUB_USERNAME")
    if not username:
        raise ValueError(
            "GitHub username is required. Set GITHUB_USERNAME environment variable or provide it as a parameter.")

    # Define organizations to include based on mode
    include_orgs = ["JsonAlchemy", "T2F-Labs"] if mode == "quicktest" else None

    # Run the analyzer
    await run_analysis(
        token=token,
        username=username,
        mode=mode,
        config_file=None,
        include_orgs=include_orgs,
        visibility="all"
    )


def run_colab(github_token=None, github_username=None, mode="quicktest"):
    """
    Main entry point for running the analyzer in Google Colab.
    
    Args:
        github_token: GitHub personal access token (default: from env)
        github_username: GitHub username to analyze (default: from env)
        mode: Analysis mode (default: "quicktest")
    """
    # Set up environment
    setup_environment()

    # Run the analyzer
    asyncio.run(run_analyzer(github_token, github_username, mode))


if __name__ == "__main__":
    # If run directly, use command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "quicktest"

    run_colab(mode=mode)
