import asyncio
import os
import random
from pathlib import Path
from typing import Optional, List

from github import Github, GithubException, RateLimitExceededException
from rich.panel import Panel

from config import create_sample_config, DEFAULT_CONFIG, load_config_from_file, Configuration
from console import logger, print_info, print_warning, print_header, rprint, create_progress_bar, console, print_success
from lens import GithubLens
from models import RepoStats
from visualize import validate_and_deploy_charts


class RunnerAnalyzer:
    """Handles GitHub repository analysis operations."""

    def __init__(self, config):
        self.config = config

    @staticmethod
    def _setup_config(token: str, username: str, config_file: Optional[str],
                      include_orgs: Optional[List[str]], visibility: str,
                      iframe_mode: str, vercel_token: str, vercel_project_name: str) -> dict:
        """Setup and configure analysis parameters."""
        create_sample_config()
        config = DEFAULT_CONFIG.copy()

        if config_file and os.path.exists(config_file):
            logger.info(f"Loading configuration from {config_file}")
            file_config = load_config_from_file(config_file)
            config.update(file_config)

        config["GITHUB_TOKEN"] = token
        config["USERNAME"] = username
        config["VISIBILITY"] = visibility

        if include_orgs:
            config["INCLUDE_ORGS"] = include_orgs

        config["IFRAME_EMBEDDING"] = iframe_mode
        if iframe_mode != "disabled":
            config["VERCEL_TOKEN"] = vercel_token
            config["VERCEL_PROJECT_NAME"] = vercel_project_name or f"ghrepolens-{username.lower()}"

        return config

    @staticmethod
    def _setup_checkpoint_file(config: dict, mode: str) -> None:
        """Setup checkpoint file for demo/test modes."""
        demo_mode = mode == "demo"
        test_mode = mode == "test"
        quicktest_mode = mode == "quicktest"

        if demo_mode or test_mode or quicktest_mode:
            config["CHECKPOINT_FILE"] = f"github_analyzer_{mode}_checkpoint.pkl"

    @staticmethod
    def _get_user_and_repos(github: Github, username: str) -> tuple:
        """Get GitHub user and their repositories."""
        auth_user = github.get_user()
        if username == auth_user.login:
            print_info(f"Analyzing authenticated user {username}, will include private repositories")
            user = auth_user
        else:
            user = github.get_user(username)

        repos = list(user.get_repos())
        return user, repos

    @staticmethod
    def _get_organization_repos(github: Github, include_orgs: Optional[List[str]]) -> dict:
        """Fetch repositories from specified organizations."""
        org_repos = {}
        if include_orgs:
            for org_name in include_orgs:
                try:
                    print_info(f"Fetching repositories for organization: {org_name}")
                    org = github.get_organization(org_name)
                    org_repos[org_name] = list(org.get_repos())
                    print_info(f"Found {len(org_repos[org_name])} repositories in organization {org_name}")
                except Exception as e:
                    print_warning(f"Failed to fetch repositories for organization {org_name}: {str(e)}")
                    logger.error(f"Failed to fetch organization {org_name}: {e}")
        return org_repos

    @staticmethod
    def _analyze_personal_repos(analyzer, repos: List, progress) -> List:
        """Analyze personal repositories with progress tracking."""
        stats = []
        task = progress.add_task("Analyzing personal repository", total=len(repos))

        for repo in repos:
            try:
                repo_stats = analyzer.analyze_repo(repo)
                stats.append(repo_stats)
                progress.update(task, advance=1, description=f"Analyzed {repo.name}")
            except Exception as e:
                logger.error(f"Failed to analyze {repo.name}: {e}")
                progress.update(task, advance=1, description=f"Failed to analyze {repo.name}")
                continue

        return stats

    @staticmethod
    def _analyze_org_repos(analyzer, org_name: str, org_repo_list: List, progress) -> List:
        """Analyze organization repositories with progress tracking."""
        org_stats = []
        task = progress.add_task(f"Analyzing {org_name} repository", total=len(org_repo_list))

        for repo in org_repo_list:
            try:
                stats = analyzer.analyze_repo(repo)
                org_stats.append(stats)
                progress.update(task, advance=1, description=f"Analyzed {repo.name}")
            except Exception as e:
                logger.error(f"Failed to analyze {org_name}/{repo.name}: {e}")
                progress.update(task, advance=1, description=f"Failed to analyze {org_name}/{repo.name}")
                continue

        return org_stats

    @staticmethod
    def _select_quicktest_repos(repos: List) -> List:
        """Select repositories for quicktest mode."""
        if not repos:
            return []
        return [repos[0]]  # Just pick the first repository for simplicity

    @staticmethod
    def _select_demo_repos(repos: List, demo_size: int) -> List:
        """Select repositories for demo mode."""
        if demo_size == 10:
            random.shuffle(repos)
        return repos[:demo_size]

    def _process_predefined_orgs(self, github: Github, analyzer, progress) -> dict:
        """Process predefined organizations for quicktest mode."""
        predefined_orgs = ["JsonAlchemy", "T2F-lab"]
        org_stats_map = {}

        for org_name in predefined_orgs:
            try:
                print_info(f"Fetching repositories for organization: {org_name}")
                org = github.get_organization(org_name)
                org_repos_list = list(org.get_repos())

                if not org_repos_list:
                    print_warning(f"No repositories found for organization {org_name}")
                    continue

                selected_org_repo = [org_repos_list[0]]
                print_info(f"Selected repository {selected_org_repo[0].name} from {org_name}")

                org_stats = self._analyze_org_repos(analyzer, org_name, selected_org_repo, progress)

                if org_stats:
                    org_stats_map[org_name] = org_stats

            except Exception as e:
                print_warning(f"Failed to fetch repositories for organization {org_name}: {str(e)}")
                logger.error(f"Failed to fetch organization {org_name}: {e}")

        return org_stats_map

    def _process_specified_orgs(self, analyzer, org_repos: dict, test_mode: bool, progress) -> dict:
        """Process specified organizations for demo/test mode."""
        org_stats_map = {}

        for org_name, org_repo_list in org_repos.items():
            if test_mode:
                org_repo_list = org_repo_list[:1]
            elif len(org_repo_list) > 5:
                random.shuffle(org_repo_list)
                org_repo_list = org_repo_list[:5]

            print_info(f"Analyzing up to {len(org_repo_list)} repositories from {org_name}")
            org_stats = self._analyze_org_repos(analyzer, org_name, org_repo_list, progress)

            if org_stats:
                org_stats_map[org_name] = org_stats

        return org_stats_map

    @staticmethod
    def _display_initial_status(analyzer, mode: str) -> None:
        """Display initial API rate status."""
        print_header(f"Running {mode} analysis")
        rprint("\n[bold]--- Initial API Rate Status ---[/bold]")
        analyzer.rate_display.display_once()
        rprint("[bold]-------------------------------[/bold]")

    def quicktest_mode(self, token: str, username: str, analyzer) -> List:
        """Run analysis in quicktest mode (1 personal repo and 1 repo per organization)."""
        github = Github(token)
        user, repos = self._get_user_and_repos(github, username)

        if not repos:
            print_warning(f"No repositories found for user {username}")
            return []

        selected_repos = self._select_quicktest_repos(repos)
        print_header(f"Running quicktest analysis on one personal repository: {selected_repos[0].name}")

        self._display_initial_status(analyzer, "quicktest")

        progress = create_progress_bar(transient=False)
        with progress:
            personal_stats = self._analyze_personal_repos(analyzer, selected_repos, progress)

        print_header("Analyzing organization repositories (one per org)")
        org_stats_map = self._process_predefined_orgs(github, analyzer, progress)

        analyzer.set_org_repo(org_stats_map)
        return personal_stats

    def demo_mode(self, token: str, username: str, analyzer, test_mode: bool = False,
                  include_orgs: Optional[List[str]] = None) -> List:
        """Run analysis in demo mode (up to 10 repositories) or test mode (1 repository)."""
        github = Github(token)
        user, repos = self._get_user_and_repos(github, username)

        org_repos = self._get_organization_repos(github, include_orgs)

        demo_size = 1 if test_mode else 10
        all_repos = self._select_demo_repos(repos, demo_size)

        mode_name = "test" if test_mode else "demo"
        self._display_initial_status(analyzer, f"{mode_name} analysis on up to {demo_size} repositories")

        progress = create_progress_bar(transient=False)
        demo_stats = []

        with progress:
            task = progress.add_task("Analyzing repositories", total=min(demo_size, len(all_repos)))
            for repo in all_repos:
                try:
                    stats = analyzer.analyze_repo(repo)
                    demo_stats.append(stats)
                    progress.update(task, advance=1, description=f"Analyzed {repo.name}")
                except Exception as e:
                    logger.error(f"Failed to analyze {repo.name}: {e}")
                    progress.update(task, advance=1, description=f"Failed to analyze {repo.name}")
                    continue

                if analyzer.analyzer.check_ratelimit_and_checkpoint(
                        demo_stats, [s.name for s in demo_stats], []
                ):
                    break

        if include_orgs and org_repos:
            print_header("Analyzing organization repositories")
            org_stats_map = self._process_specified_orgs(analyzer, org_repos, test_mode, progress)
            analyzer.set_org_repo(org_stats_map)

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
    return analyzer.analyze_all_repos()


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

        # Check if iframe embedding is enabled and deploy charts if needed
        if analyzer.config.get("IFRAME_EMBEDDING", "disabled") != "disabled":
            status.update("[bold green]Deploying charts for iframe embedding...")
            await asyncio.to_thread(validate_and_deploy_charts, analyzer.config)


def _print_summary(analyzer: GithubLens, all_stats: List[RepoStats], mode: str) -> None:
    """
    Print analysis summary to console.

    Args:
        analyzer: Initialized GithubLens instance
        all_stats: List of RepoStats objects for analyzed repositories
        mode: Analysis mode ("demo", "full", "test", or "quicktest")
    """
    analyzed_count = len(all_stats)
    summary_text = (
        f"✅ Analyzed {analyzed_count} repositories for @{analyzer.config['USERNAME']}\n\n"
        f"📊 Generated reports in {analyzer.config['REPORTS_DIR']} directory\n"
        f"📈 Created visualizations and interactive dashboard\n"
    )

    if analyzer.config.get("IFRAME_EMBEDDING", "disabled") != "disabled":
        summary_text += f"🌐 Charts deployed for iframe embedding (mode: {analyzer.config['IFRAME_EMBEDDING']})\n"

    if mode == "demo":
        summary_text += "\n⚠️ Demo mode: Limited to 10 repositories\n"
        summary_text += "🔄 Run without --demo flag to analyze all repositories"
    elif mode == "test":
        summary_text += "\n⚠️ Test mode: Limited to 1 repository for quick testing\n"
        summary_text += "🔄 Run without --test flag to analyze all repositories"
    elif mode == "quicktest":
        summary_text += "\n⚠️ Quicktest mode: Limited to 1 personal repository and 1 repository per organization\n"
        summary_text += "🔄 This is a temporary test mode for specific development purposes"

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


async def run_analysis(
        token: str,
        username: str,
        mode: str = "full",
        config_file: Optional[str] = None,
        include_orgs: Optional[List[str]] = None,
        visibility: str = "all",
        iframe_mode: str = "disabled",
        vercel_token: str = "",
        vercel_project_name: str = ""
) -> None:
    """
    Run GitHub repository analysis for the specified user.

    Performs comprehensive analysis of GitHub repositories, generates reports,
    and handles exceptions gracefully.

    Args:
        token: GitHub personal access token for API authentication
        username: GitHub username whose repositories will be analyzed
        mode: Analysis mode ("demo", "full", "test", or "quicktest")
        config_file: Path to custom configuration file (default: None)
        include_orgs: List of organization names to include in analysis (default: None)
        visibility: Repository visibility option ("all", "public", or "private")
        iframe_mode: Mode for iframe embedding ("disabled", "partial", "full")
        vercel_token: Vercel API token for deployment
        vercel_project_name: Unique project name for Vercel deployment
    """
    demo_mode = mode == "demo"
    test_mode = mode == "test"
    quicktest_mode = mode == "quicktest"

    with console.status(f"[bold green]Starting GitHub Repository RunnerAnalyzer ({mode.upper()} MODE)"):
        logger.info(f"Starting GitHub Repository RunnerAnalyzer ({mode.upper()} MODE)")

        analyzer_instance = RunnerAnalyzer(None)
        config = analyzer_instance._setup_config(
            token, username, config_file, include_orgs, visibility,
            iframe_mode, vercel_token, vercel_project_name
        )
        analyzer_instance._setup_checkpoint_file(config, mode)

    try:
        analyzer = GithubLens(config["GITHUB_TOKEN"], config["USERNAME"], config)
        await _handle_checkpoint_message(config)

        if quicktest_mode:
            all_stats = analyzer_instance.quicktest_mode(token, username, analyzer)
            if not all_stats:
                logger.error("❌ No repositories analyzed in quicktest mode")
                return
        elif demo_mode or test_mode:
            all_stats = analyzer_instance.demo_mode(token, username, analyzer, test_mode, include_orgs)
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
