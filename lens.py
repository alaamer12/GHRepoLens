"""
GitHub Repository Lens Module

This module provides the main interface for analyzing GitHub repositories.
It coordinates between the analyzer, reporter, and visualizer components.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict

import requests
from github import Github
from github.Organization import Organization
from github.Repository import Repository

from analyzer import GithubAnalyzer
from config import DEFAULT_CONFIG, Configuration, load_theme_config
from console import logger, RateLimitDisplay
from models import RepoStats
from reporter import GithubReporter
from utilities import Checkpoint
from visualize import GithubVisualizer


# noinspection PyTypeChecker,PyArgumentList
class GithubLens:
    """
    Main analyzer class for GitHub repositories with comprehensive analysis capabilities.
    
    Coordinates between different components to analyze repositories, generate reports,
    and create visualizations.
    """

    def __init__(self, token: str, username: str, config: Optional[Configuration] = None) -> None:
        """
        Initialize the analyzer with GitHub token and configuration.
        
        Args:
            token: GitHub personal access token for API authentication
            username: GitHub username to analyze
            config: Optional configuration dictionary to override defaults
        """
        self.org_repositories: Optional[Dict[str, List[RepoStats]]] = None
        self.github: Optional[Github] = None
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # Configure custom GitHub client with backoff visualization
        self.setup_github_client(token)
        self.username = username
        self.user = None
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        })

        # Create output directories
        self.reports_dir = Path(self.config["REPORTS_DIR"])
        self.clone_dir = Path(self.config["CLONE_DIR"])
        self.reports_dir.mkdir(exist_ok=True)
        if self.config["ANALYZE_CLONES"]:
            self.clone_dir.mkdir(exist_ok=True)

        # Setup executor for parallel processing
        self.max_workers = self.config["MAX_WORKERS"]

        # Checkpoint tracking
        self.checkpoint = Checkpoint(self.config, username)
        self.api_requests_made = 0
        self.analyzed_repos: List[str] = []

        # Initialize rate display for interactive display
        self.rate_display = RateLimitDisplay()

        # Create analyzer instance
        self.analyzer = GithubAnalyzer(self.github, username, self.config)
        # Set rate display for analyzer
        self.analyzer.rate_display = self.rate_display
        self.analyzer.checkpoint = self.checkpoint
        self.theme = load_theme_config()
        self.visualizer = GithubVisualizer(self.username, self.reports_dir, self.theme)

        logger.info(f"Initialized analyzer for user: {username}")

    def start_monitoring(self, update_interval: int = 30) -> bool:
        """
        Start continuous rate monitoring in a background thread.
        
        Args:
            update_interval: How often to update the display (in seconds)
        
        Returns:
            True if monitoring started, False otherwise
        """
        try:
            # Update the display once immediately
            self.rate_display.update_from_api(self.github)
            self.rate_display.display_once()

            # Start continuous monitoring - Note: implementation removed from utilities.py
            logger.info(f"Rate monitoring requested (updates every {update_interval}s)")
            return True
        except Exception as e:
            logger.error(f"Error starting continuous rate monitoring: {e}")
            return False

    @staticmethod
    def stop_monitoring() -> bool:
        """
        Stop continuous rate monitoring.
        
        Returns:
            True if monitoring was successfully stopped, False otherwise
        """
        try:
            # Stop monitoring - Note: implementation removed from utilities.py
            logger.info("Stopped continuous rate monitoring")
            return True
        except Exception as e:
            logger.error(f"Error stopping continuous rate monitoring: {e}")
            return False

    def setup_github_client(self, token: str) -> None:
        """
        Set up GitHub client with custom backoff handling to show progress bars.
        
        Args:
            token: GitHub personal access token
            
        Raises:
            Exception: If GitHub client initialization fails
        """
        try:
            self.github = Github(token)
        except Exception as e:
            logger.error(f"Error setting up GitHub client: {e}")
            raise

    def analyze_single_repository(self, repo: Repository) -> RepoStats:
        """
        Analyze a single repository using the GithubAnalyzer.
        
        Args:
            repo: GitHub repository object to analyze
            
        Returns:
            RepoStats object containing analysis results
        """
        # Pass to the analyzer instance
        return self.analyzer.analyze_single_repository(repo)

    def get_personal_repositories(self) -> List[Repository]:
        """
        Get personal repositories (non-organization) for the authenticated user.
        
        Returns:
            List of Repository objects owned by the user
        """
        try:
            user = self.github.get_user()
            username = user.login

            # Use visibility parameter if configured (all, public, or private)
            visibility = self.config.get("VISIBILITY", "all")

            # Get repositories using visibility parameter if specified
            if visibility != "all":
                all_repos = list(user.get_repos(visibility=visibility))
            else:
                all_repos = list(user.get_repos())

            # Filter repositories to only include those owned by the user
            personal_repos = [
                repo for repo in all_repos
                if repo.owner.login == username
            ]

            logger.info(f"Found {len(personal_repos)} personal repositories")
            return personal_repos
        except Exception as e:
            logger.error(f"Error getting personal repositories: {e}")
            return []

    def get_organization_repositories(self, org_name: str) -> List[Repository]:
        """
        Get repositories for a specific organization.
        
        Args:
            org_name: Name of the organization
            
        Returns:
            List of Repository objects from the organization
        """
        try:
            org: Organization = self.github.get_organization(org_name)

            # Use visibility parameter if configured (all, public, or private)
            visibility = self.config.get("VISIBILITY", "all")

            # Get repositories using visibility parameter if specified
            if visibility != "all":
                org_repos = list(org.get_repos(visibility=visibility))
            else:
                org_repos = list(org.get_repos())

            logger.info(f"Found {len(org_repos)} repositories in organization {org_name}")
            return org_repos
        except Exception as e:
            logger.error(f"Error getting repositories for organization {org_name}: {e}")
            return []

    def get_repositories_to_analyze(self) -> List[Repository]:
        """
        Get all repositories to analyze based on configuration.
        
        Returns:
            List of Repository objects to be analyzed
        """
        # Always include personal repositories
        repositories = self.get_personal_repositories()

        # Include repositories from specified organizations if configured
        include_orgs = self.config.get("INCLUDE_ORGS", [])
        if include_orgs:
            for org_name in include_orgs:
                org_repos = self.get_organization_repositories(org_name)
                repositories.extend(org_repos)
                logger.info(f"Added {len(org_repos)} repositories from organization {org_name}")

        # Apply repository filters
        filtered_repos = []
        for repo in repositories:
            # Skip forks if configured
            if self.config.get("SKIP_FORKS", False) and repo.fork:
                continue

            # Skip archived repositories if configured
            if self.config.get("SKIP_ARCHIVED", False) and repo.archived:
                continue

            # Apply visibility filter (supersedes INCLUDE_PRIVATE)
            visibility = self.config.get("VISIBILITY", "all")
            if visibility != "all":
                if visibility == "public" and repo.private:
                    continue
                if visibility == "private" and not repo.private:
                    continue
            # For backwards compatibility, also check INCLUDE_PRIVATE
            elif not self.config.get("INCLUDE_PRIVATE", True) and repo.private:
                continue

            filtered_repos.append(repo)

        logger.info(f"Selected {len(filtered_repos)} repositories for analysis after filtering")
        return filtered_repos

    def analyze_all_repositories(self) -> List[RepoStats]:
        """
        Analyze all repositories for the user.
        
        Returns:
            List of RepoStats objects, one for each repository
        """
        # Get repositories to analyze based on configuration
        repositories_to_analyze = self.get_repositories_to_analyze()

        # Delegate to the analyzer instance
        return self.analyzer.analyze_repositories(repositories_to_analyze)

    def generate_report(self, all_stats: List[RepoStats]) -> None:
        """
        Generate detailed reports and visualizations for the analyzed repositories.
        
        Args:
            all_stats: List of RepoStats objects to include in the reports
        """
        reporter = GithubReporter(self.username, self.reports_dir)
        reporter.generate_detailed_report(all_stats)
        logger.info("Generated detailed repository reports")

        # Generate visualizations
        self.generate_visualizations(all_stats)
        logger.info("Generated visual reports")

        # Save raw data as JSON
        self._save_json_report(all_stats)
        logger.info("Saved repository data in JSON format")

    def _save_json_report(self, all_stats: List[RepoStats]) -> None:
        """
        Save data as JSON for programmatic consumption.
        
        Args:
            all_stats: List of RepoStats objects to export
        """
        output_file = self.reports_dir / "repository_data.json"

        # Convert repository statistics to JSON-serializable form
        serializable_data = []
        for repo in all_stats:
            # Extract basic fields
            repo_data = {
                "name": repo.name,
                "is_private": repo.is_private,
                "default_branch": repo.default_branch,
                "is_fork": repo.is_fork,
                "is_archived": repo.is_archived,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "last_pushed": repo.last_pushed.isoformat() if repo.last_pushed else None,
                "description": repo.description,
                "homepage": repo.homepage,

                # Code stats
                "languages": repo.languages,
                "primary_language": repo.primary_language,
                "total_files": repo.total_files,
                "total_loc": repo.total_loc,
                "is_monorepo": repo.is_monorepo,

                # Quality indicators
                "has_docs": repo.has_docs,
                "has_tests": repo.has_tests,
                "has_ci": repo.has_cicd,

                # Activity metrics
                "is_active": repo.is_active,
                "commits_last_month": repo.commits_last_month,
                "commits_last_year": repo.commits_last_year,

                # Community metrics
                "license": repo.license_name,
                "stars": repo.stars,
                "forks": repo.forks,
                "contributors_count": repo.contributors_count,
                "open_issues": repo.open_issues,
                "topics": repo.topics,

                # Scores
                "maintenance_score": repo.maintenance_score,
                "popularity_score": repo.popularity_score,
                "code_quality_score": repo.code_quality_score,
                "documentation_score": repo.documentation_score,

                # Anomalies
                "anomalies": repo.anomalies
            }
            serializable_data.append(repo_data)

        # Use custom encoder for datetime objects
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj: Any) -> Any:
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, cls=DateTimeEncoder, indent=2)

        logger.info(f"Saved repository data to {output_file}")

    def generate_visualizations(self, all_stats: List[RepoStats]) -> None:
        """
        Generate visualizations and interactive dashboard for the analyzed repositories.
        
        Args:
            all_stats: List of RepoStats objects to include in the visualizations
        """
        # Load theme configuration
        theme = load_theme_config()

        # Create visualizer instance
        visualizer = GithubVisualizer(self.username, self.reports_dir, theme)

        # Check for organization repositories from previously set data
        org_repos = getattr(self, 'org_repositories', None)

        # If no org repositories were set directly, check config for org names to include
        if not org_repos and self.config.get("INCLUDE_ORGS"):
            include_orgs = self.config.get("INCLUDE_ORGS", [])
            visualizer.set_org_repos_included(include_orgs)

        # Generate visualizations with organization info if available
        visualizer.create_visualizations(all_stats, org_repos)
        logger.info("Generated visualizations and interactive dashboard")

    def set_organization_repositories(self, org_repos_map: Dict[str, List[RepoStats]]) -> None:
        """
        Set organization repositories data in the lens.
        
        Args:
            org_repos_map: Dictionary mapping organization names to lists of repository statistics
        """
        self.org_repositories = org_repos_map
        logger.info(f"Set organization repositories for {len(org_repos_map)} organizations")

        # The visualizer is created later, so we don't need to set anything here
        # The generate_visualizations method will use the org_repositories data
