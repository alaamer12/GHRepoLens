"""
GitHub Repository RunnerAnalyzer - Main Entry Point

This module provides the main entry point for the GitHub Repository RunnerAnalyzer tool.
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

import argparse
import asyncio
import atexit
import os
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, NamedTuple

import dotenv
from github.GithubException import GithubException, RateLimitExceededException
from rich.prompt import Prompt, Confirm
import requests

from config import DEFAULT_CONFIG, create_sample_config, create_sample_env, shutdown_logging
from console import console, logger, print_header, print_info, print_warning, print_error, print_success, \
    configure_logging
from lens import GithubLens
from models import RepoStats
from runner_analyzer import RunnerAnalyzer, _print_summary, _handle_rate_limit_exceeded, _handle_github_exception, \
    _handle_generic_exception, run_analysis
from visualize import validate_deploy_and_optionally_delete

# Register shutdown_logging to be called when the program exits
atexit.register(shutdown_logging)


class PromptResults(NamedTuple):
    selected_mode: str
    selected_visibility: str
    config_file: str
    include_orgs: list
    iframe_mode: str
    vercel_token: str
    vercel_project_name: str


async def _run_quicktest_mode(
        token: str,
        username: str,
        analyzer,
) -> List:
    """Backward compatible wrapper for quicktest mode."""
    analyzer_instance = RunnerAnalyzer(None)
    return analyzer_instance.quicktest_mode(token, username, analyzer)


async def _generate_reports_with_quicktest(analyzer: GithubLens, all_stats: List[RepoStats],
                                           delete_project: bool) -> None:
    """
    Generate reports and visualizations for analyzed repositories with quicktest options.

    Args:
        analyzer: Initialized GithubLens instance
        all_stats: List of RepoStats objects for analyzed repositories
        delete_project: Whether to prompt for project deletion after deployment
    """
    with console.status("[bold green]Generating reports and visualizations...") as status:
        logger.info("Generating reports")
        await asyncio.to_thread(analyzer.generate_report, all_stats)

        logger.info("Generating interactive dashboard")
        status.update("[bold green]Creating interactive dashboard...")
        await asyncio.to_thread(analyzer.generate_visualizations, all_stats)

        # Create reports directory if it doesn't exist
        Path(analyzer.config["REPORTS_DIR"]).mkdir(exist_ok=True)

        # Check if iframe embedding is enabled and deploy charts if needed
        if analyzer.config.get("IFRAME_EMBEDDING", "disabled") != "disabled":
            status.update("[bold green]Deploying charts for iframe embedding...")
            # noinspection PyTypeChecker
            success, embedder = await asyncio.to_thread(
                validate_deploy_and_optionally_delete,
                analyzer.config,
            )

            # If deployment was successful and delete_project flag is set, prompt to delete
            if success and delete_project and embedder:
                if Confirm.ask(
                        "Would you like to delete the Vercel project now that testing is complete?",
                        default=True
                ):
                    status.update("[bold yellow]Deleting Vercel project...")
                    await asyncio.to_thread(embedder.delete_project)


def parse_args():
    parser = argparse.ArgumentParser(description="GitHub Repository RunnerAnalyzer")
    parser.add_argument('--quicktest', action='store_true',
                        help='Run quick test with predefined parameters')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging to the console')
    parser.add_argument('--iframe', choices=['disabled', 'partial', 'full'],
                        help='Enable iframe embedding of charts (requires Vercel account)')
    parser.add_argument('--delete-project', action='store_true',
                        help='Delete Vercel project after deployment (only with --quicktest)')
    parser.add_argument('--test-vercel', action='store_true',
                        help='Test Vercel token validity without running analysis')

    # Use parse_known_args to ignore any additional args (important for Google Colab)
    return parser.parse_known_args()


class EnvironmentManager:
    """Manages environment variables and configuration."""

    @staticmethod
    def load_environment(verbose: bool = False):
        """Load environment variables from .env file if present."""
        env_path = Path('.env')
        if env_path.exists():
            print_info(f"Loading environment variables from {env_path.absolute()}")
            dotenv.load_dotenv(dotenv_path=env_path, override=True)
        else:
            print_warning("No .env file found in the current directory")

        if verbose:
            EnvironmentManager._debug_environment_variables()

    @staticmethod
    def _debug_environment_variables():
        """Debug: Show loaded environment variables (without showing sensitive values)."""
        print_info("Loaded environment variables:")

        # Show non-sensitive variables
        for key in ["GITHUB_USERNAME", "IFRAME_EMBEDDING", "VERCEL_PROJECT_NAME"]:
            if key in os.environ:
                print_info(f"  {key} = {os.environ[key]}")

        # Show if sensitive tokens exist but not their values
        for key in ["GITHUB_TOKEN", "VERCEL_TOKEN"]:
            if key in os.environ:
                print_info(f"  {key} = [HIDDEN]")

    @staticmethod
    def get_required_env_var(var_name: str, error_message: str) -> Optional[str]:
        """Get required environment variable with error handling."""
        value = os.environ.get(var_name, "")
        if not value:
            print_error(error_message)
            print_info("You can create a .env file with your credentials. See .env.sample for an example.")
            return None
        return value


class VercelTokenValidator:
    """Handles Vercel token validation and testing."""

    @staticmethod
    def test_token(token: str) -> bool:
        """Test Vercel token validity."""
        print_info("Testing Vercel token validity...")
        try:
            headers = {
                "Authorization": f"Bearer {token.strip()}",
                "Content-Type": "application/json"
            }

            # Test user authentication
            if not VercelTokenValidator._test_user_auth(headers):
                return False

            # Test project listing
            return VercelTokenValidator._test_project_listing(headers)

        except Exception as e:
            print_error(f"Error testing Vercel token: {str(e)}")
            return False

    @staticmethod
    def _test_user_auth(headers: Dict[str, str]) -> bool:
        """Test user authentication."""
        response = requests.get("https://api.vercel.com/v2/user", headers=headers, timeout=10)

        if response.status_code == 200:
            user_data = response.json()
            username = user_data.get("user", {}).get("username", "unknown")
            print_success(f"Vercel token is valid! Authenticated as: {username}")
            return True
        else:
            print_error(f"Vercel token validation failed: HTTP {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return False

    @staticmethod
    def _test_project_listing(headers: Dict[str, str]) -> bool:
        """Test project listing capability."""
        print_info("Testing project listing...")
        proj_response = requests.get("https://api.vercel.com/v2/projects", headers=headers, timeout=10)

        if proj_response.status_code == 200:
            projects = proj_response.json()  # v2 API returns array directly
            print_success(f"Successfully listed {len(projects)} projects")

            # Show up to 5 projects
            for project in projects[:5]:
                print_info(f"  - {project.get('name')} (ID: {project.get('id')})")
            return True
        else:
            print_error(f"Failed to list projects: HTTP {proj_response.status_code}")
            print_info(f"Response: {proj_response.text[:200]}")
            return False


class QuickTestConfig:
    """Handles configuration for quicktest mode."""

    DEFAULT_ORGS = ["JsonAlchemy", "T2F-Labs"]

    @classmethod
    def create_config(cls, args) -> Optional[Dict[str, Any]]:
        """Create configuration for quicktest mode."""
        # Get required tokens
        github_token = EnvironmentManager.get_required_env_var(
            "GITHUB_TOKEN",
            "GitHub token not found in environment. Set GITHUB_TOKEN environment variable."
        )
        if not github_token:
            return None

        github_username = EnvironmentManager.get_required_env_var(
            "GITHUB_USERNAME",
            "GitHub username not found in environment. Set GITHUB_USERNAME environment variable."
        )
        if not github_username:
            return None

        # Get visibility setting
        visibility = cls._get_visibility()

        # Get iframe and Vercel configuration
        iframe_mode, vercel_token, vercel_project_name = cls._get_vercel_config(
            args, github_username
        )

        if iframe_mode != "disabled" and not vercel_token:
            return None

        # Create configuration object
        config = DEFAULT_CONFIG.copy()
        config.update({
            "GITHUB_TOKEN": github_token,
            "USERNAME": github_username,
            "VISIBILITY": visibility,
            "INCLUDE_ORGS": cls.DEFAULT_ORGS,
            "IFRAME_EMBEDDING": iframe_mode,
            "VERCEL_TOKEN": vercel_token,
            "VERCEL_PROJECT_NAME": vercel_project_name
        })

        return config

    @staticmethod
    def _get_visibility() -> str:
        """Get and validate visibility setting."""
        visibility = os.environ.get("GITHUB_VISIBILITY", "all")

        if visibility not in ["all", "public", "private"]:
            print_warning(f"Invalid visibility value '{visibility}', using default 'all'.")
            visibility = "all"

        return visibility

    @staticmethod
    def _get_vercel_config(args, github_username: str) -> tuple[str, str, str]:
        """Get Vercel configuration for iframe embedding."""
        iframe_mode = args.iframe or os.environ.get("IFRAME_EMBEDDING", "disabled")
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        vercel_project_name = os.environ.get("VERCEL_PROJECT_NAME", "")

        # Validate Vercel configuration if iframe embedding is enabled
        if iframe_mode != "disabled":
            if not vercel_token:
                print_error("Vercel token not found in environment. Set VERCEL_TOKEN environment variable.")
                print_info("You can create a .env file with your credentials. See .env.sample for an example.")
                print_info("Or get a token from https://vercel.com/account/tokens")
                return iframe_mode, "", ""

            if not vercel_project_name:
                # Generate a default project name based on username and timestamp
                timestamp = int(time.time())
                vercel_project_name = f"ghrepolens-{github_username.lower()}-{timestamp}"
                print_info(f"Generated Vercel project name: {vercel_project_name}")

        return iframe_mode, vercel_token, vercel_project_name


class InteractivePrompts:
    """Handles interactive user prompts."""

    @staticmethod
    def github_credentials() -> tuple[str, str]:
        """Get GitHub credentials from environment or user input."""
        github_token = os.environ.get("GITHUB_TOKEN", "")
        if not github_token:
            github_token = Prompt.ask(
                "[bold]GitHub Token[/bold] (create at https://github.com/settings/tokens)",
                password=True
            )

        github_username = os.environ.get("GITHUB_USERNAME", "")
        if not github_username:
            github_username = Prompt.ask("[bold]GitHub Username[/bold] (to analyze)")

        return github_token, github_username

    @staticmethod
    def analysis_mode() -> str:
        """Get analysis mode from user."""
        mode_options = {"1": "full", "2": "demo", "3": "test"}

        print_header("Select Analysis Mode")
        console.print("[1] Full Analysis - Analyze all repositories (may take longer)")
        console.print("[2] Demo Mode - Analyze up to 10 repositories")
        console.print("[3] Test Mode - Analyze 1 repository (quick test)")

        mode_choice = Prompt.ask("[bold]Choose mode[/bold]", choices=["1", "2", "3"], default="1")
        return mode_options[mode_choice]

    @staticmethod
    def get_visibility_setting() -> str:
        """Get repository visibility setting from user."""
        visibility_options = {"1": "all", "2": "public", "3": "private"}

        print_header("Select Repository Visibility")
        console.print("[1] All - Include both public and private repositories")
        console.print("[2] Public - Include only public repositories")
        console.print("[3] Private - Include only private repositories")

        visibility_choice = Prompt.ask("[bold]Choose visibility[/bold]", choices=["1", "2", "3"], default="1")
        return visibility_options[visibility_choice]

    @staticmethod
    def config_file() -> Optional[str]:
        """Get custom config file path from user."""
        use_config = Confirm.ask("Use custom config file?", default=False)
        if use_config:
            return Prompt.ask("[bold]Path to config file[/bold]", default="config.ini")
        return None

    @staticmethod
    def organization_list() -> List[str]:
        """Get organization list from user."""
        include_orgs = []
        include_orgs_option = Confirm.ask("Include organization repositories?", default=False)

        if include_orgs_option:
            org_input = Prompt.ask(
                "[bold]Organization names[/bold] (comma-separated)",
                default=""
            )

            if org_input:
                include_orgs = InteractivePrompts._parse_organization_input(org_input)

        return include_orgs

    @staticmethod
    def _parse_organization_input(org_input: str) -> List[str]:
        """Parse organization input string."""
        if "," in org_input or not org_input.strip():
            include_orgs = [org.strip() for org in org_input.split(",") if org.strip()]
            if include_orgs:
                print_info(f"Will include repositories from organizations: {', '.join(include_orgs)}")
            else:
                print_warning("No valid organization names provided. Continuing without organization repositories.")
        else:
            # Single organization name without commas
            include_orgs = [org_input.strip()]
            print_info(f"Will include repositories from organization: {include_orgs[0]}")

        return include_orgs

    @staticmethod
    def iframe_settings(args, github_username: str) -> tuple[str, str, str]:
        """Get iframe embedding settings from user."""
        iframe_mode = args.iframe
        vercel_token = ""
        vercel_project_name = ""

        if iframe_mode is None:  # Only ask if not provided in command line
            iframe_mode = InteractivePrompts._get_iframe_mode()

        # If iframe embedding is enabled, ask for Vercel token and project name
        if iframe_mode and iframe_mode != "disabled":
            vercel_token, vercel_project_name = InteractivePrompts._get_vercel_credentials(github_username)

        return iframe_mode, vercel_token, vercel_project_name

    @staticmethod
    def _get_iframe_mode() -> str:
        """Get iframe embedding mode from user."""
        iframe_options = {"1": "disabled", "2": "partial", "3": "full"}

        print_header("IFrame Embedding Options")
        console.print("[1] Disabled - No iframe embedding (default)")
        console.print("[2] Partial - Deploy key chart HTML files")
        console.print("[3] Full - Deploy all HTML files including dashboard")

        iframe_choice = Prompt.ask("[bold]Choose iframe embedding mode[/bold]", choices=["1", "2", "3"], default="1")
        return iframe_options[iframe_choice]

    @staticmethod
    def _get_vercel_credentials(github_username: str) -> tuple[str, str]:
        """Get Vercel credentials from user."""
        # Try to get token from environment
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        if not vercel_token:
            vercel_token = Prompt.ask("[bold]Vercel token[/bold] (required for deployment)", password=True)

        vercel_project_name = os.environ.get("VERCEL_PROJECT_NAME", "")
        if not vercel_project_name:
            vercel_project_name = Prompt.ask(
                "[bold]Vercel project name[/bold] (must be unique)",
                default=f"ghrepolens-{github_username.lower()}"
            )

        return vercel_token, vercel_project_name


async def run_quicktest(config: Dict[str, Any], delete_project: bool = False):
    """Run quicktest analysis mode."""
    try:
        analyzer = GithubLens(config["GITHUB_TOKEN"], config["USERNAME"], config)

        # Run the quicktest analysis
        all_stats = await _run_quicktest_mode(
            token=config["GITHUB_TOKEN"],
            username=config["USERNAME"],
            analyzer=analyzer,
        )

        if not all_stats:
            logger.error("❌ No repositories analyzed in quicktest mode")
            return

        # Generate reports with quicktest options
        await _generate_reports_with_quicktest(
            analyzer=analyzer,
            all_stats=all_stats,
            delete_project=delete_project
        )

        # Print summary
        _print_summary(analyzer, all_stats, "quicktest")

    except RateLimitExceededException:
        _handle_rate_limit_exceeded()
    except GithubException as e:
        _handle_github_exception(e)
    except Exception as e:
        _handle_generic_exception(e)
        raise


def collect_prompt_results(args, github_username) -> PromptResults:
    selected_mode = InteractivePrompts.analysis_mode()
    selected_visibility = InteractivePrompts.get_visibility_setting()
    config_file = InteractivePrompts.config_file()
    include_orgs = InteractivePrompts.organization_list()
    iframe_mode, vercel_token, vercel_project_name = InteractivePrompts.iframe_settings(args, github_username)

    return PromptResults(
        selected_mode=selected_mode,
        selected_visibility=selected_visibility,
        config_file=config_file,
        include_orgs=include_orgs,
        iframe_mode=iframe_mode,
        vercel_token=vercel_token,
        vercel_project_name=vercel_project_name
    )


async def main() -> None:
    """
    Main entry point for the GitHub Repository RunnerAnalyzer tool.

    Handles command-line arguments, prompts for required inputs,
    and runs the analysis process.
    """
    # Parse command-line arguments
    args, _ = parse_args()

    # Configure logging based on verbosity
    configure_logging(log_to_console=args.verbose)

    # Create sample configuration files if they don't exist
    create_sample_config()
    create_sample_env()

    # Load environment variables
    EnvironmentManager.load_environment(verbose=args.verbose)

    # Handle Vercel token testing
    if args.test_vercel:
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        if not vercel_token:
            print_error("No Vercel token found in environment variables")
            return

        VercelTokenValidator.test_token(vercel_token)
        return

    # Handle quicktest mode
    if args.quicktest:
        config = QuickTestConfig.create_config(args)
        if config is None:
            return

        await run_quicktest(config, args.delete_project)
        return

    # Interactive mode
    print_header("GitHub Repository RunnerAnalyzer")

    # Get GitHub credentials
    github_token, github_username = InteractivePrompts.github_credentials()

    # Get analysis settings
    results = collect_prompt_results(args, github_username)

    # Run the analysis
    await run_analysis(
        token=github_token,
        username=github_username,
        mode=results.selected_mode,
        config_file=results.config_file,
        include_orgs=results.include_orgs,
        visibility=results.selected_visibility,
        iframe_mode=results.iframe_mode,
        vercel_token=results.vercel_token,
        vercel_project_name=results.vercel_project_name
    )


if __name__ == "__main__":
    asyncio.run(main())
