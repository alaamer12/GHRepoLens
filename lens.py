"""
GitHub Repository Lens Module

This module provides the main interface for analyzing GitHub repositories.
It coordinates between the analyzer, reporter, and visualizer components.
"""

from pathlib import Path
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import requests
from github import Github
from github.Repository import Repository

from analyzer import GithubAnalyzer
from config import DEFAULT_CONFIG, Configuration, logger
from models import RepoStats
from reporter import GithubReporter
from utilities import Checkpoint, GitHubRateDisplay
from visualizer import GithubVisualizer


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
        self.rate_display = GitHubRateDisplay()
        
        # Create analyzer instance
        self.analyzer = GithubAnalyzer(self.github, username, self.config)
        # Set rate display for analyzer
        self.analyzer.rate_display = self.rate_display
        self.analyzer.checkpoint = self.checkpoint
        
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
            
            # Start continuous monitoring
            if self.rate_display.start(update_interval, self.github):
                logger.info(f"Started continuous rate monitoring (updates every {update_interval}s)")
                return True
            return False
        except Exception as e:
            logger.error(f"Error starting continuous rate monitoring: {e}")
            return False
            
    def stop_monitoring(self) -> bool:
        """
        Stop continuous rate monitoring.
        
        Returns:
            True if monitoring was successfully stopped, False otherwise
        """
        try:
            self.rate_display.stop()
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

    def analyze_all_repositories(self) -> List[RepoStats]:
        """
        Analyze all repositories for the user.
        
        Returns:
            List of RepoStats objects, one for each repository
        """
        # Delegate to the analyzer instance
        return self.analyzer.analyze_all_repositories()

    def generate_detailed_report(self, all_stats: List[RepoStats]) -> None:
        """
        Generate detailed per-repository report.
        
        Args:
            all_stats: List of RepoStats objects to include in the report
        """
        reporter = GithubReporter(self.username, self.reports_dir)
        reporter.generate_detailed_report(all_stats)

    def generate_aggregated_report(self, all_stats: List[RepoStats]) -> None:
        """
        Generate aggregated statistics report.
        
        Args:
            all_stats: List of RepoStats objects to include in the report
        """
        reporter = GithubReporter(self.username, self.reports_dir)
        reporter.generate_aggregated_report(all_stats)
        
    def create_visualizations(self, all_stats: List[RepoStats]) -> None:
        """
        Generate visual reports with charts and graphs.
        
        Args:
            all_stats: List of RepoStats objects to visualize
        """
        logger.info("Generating visual report")
        visualizer = GithubVisualizer(self.username, self.reports_dir)
        visualizer.create_visualizations(all_stats)

    def save_json_report(self, all_stats: List[RepoStats]) -> None:
        """
        Save data as JSON for programmatic consumption.
        
        Args:
            all_stats: List of RepoStats objects to export
        """
        exporter = GithubExporter(self.username, self.reports_dir)
        exporter.save_json_report(all_stats)


class GithubExporter:
    """
    Class responsible for exporting GitHub repository data to various formats.
    
    Handles the conversion of repository statistics into serializable formats
    and writes them to files.
    """
    
    def __init__(self, username: str, reports_dir: Path) -> None:
        """
        Initialize the exporter with username and reports directory.
        
        Args:
            username: GitHub username being analyzed
            reports_dir: Directory path where reports will be saved
        """
        self.username = username
        self.reports_dir = reports_dir
    
    def save_json_report(self, all_stats: List[RepoStats]) -> None:
        """
        Save data as JSON for programmatic consumption.
        
        Handles datetime serialization and error recovery for individual repositories.
        
        Args:
            all_stats: List of RepoStats objects to export as JSON
        """
        logger.info("Saving JSON report")
        
        # Count empty repositories
        empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
        
        # Custom JSON encoder for datetime objects
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj: Any) -> Any:
                if isinstance(obj, datetime):
                    # Ensure the datetime has timezone info before serialization
                    if obj.tzinfo is None:
                        obj = obj.replace(tzinfo=timezone.utc)
                    return obj.isoformat()
                return super().default(obj)
        
        # Convert RepoStats to dictionaries with field-by-field error handling
        repo_dicts: List[Dict[str, Any]] = []
        for stats in all_stats:
            try:
                # Manual conversion instead of using asdict to avoid serialization issues
                repo_dict: Dict[str, Any] = {}
                
                # Basic repository information
                repo_dict["name"] = stats.name
                repo_dict["is_private"] = stats.is_private
                repo_dict["default_branch"] = stats.default_branch
                repo_dict["is_fork"] = stats.is_fork
                repo_dict["is_archived"] = stats.is_archived
                repo_dict["is_template"] = stats.is_template
                
                # Handle datetime fields with timezone awareness
                repo_dict["created_at"] = stats.created_at.replace(tzinfo=timezone.utc) if stats.created_at else None
                repo_dict["last_pushed"] = stats.last_pushed.replace(tzinfo=timezone.utc) if stats.last_pushed else None
                repo_dict["last_commit_date"] = stats.last_commit_date.replace(tzinfo=timezone.utc) if stats.last_commit_date else None
                
                # Code statistics
                repo_dict["languages"] = dict(stats.languages) if stats.languages else {}
                repo_dict["total_files"] = stats.total_files
                repo_dict["total_loc"] = stats.total_loc
                repo_dict["avg_loc_per_file"] = stats.avg_loc_per_file
                repo_dict["file_types"] = dict(stats.file_types) if stats.file_types else {}
                repo_dict["size_kb"] = stats.size_kb
                
                # Quality indicators
                repo_dict["has_docs"] = stats.has_docs
                repo_dict["has_readme"] = stats.has_readme
                repo_dict["has_tests"] = stats.has_tests
                repo_dict["test_files_count"] = stats.test_files_count
                repo_dict["test_coverage_percentage"] = stats.test_coverage_percentage
                repo_dict["has_cicd"] = stats.has_cicd
                repo_dict["cicd_files"] = list(stats.cicd_files) if stats.cicd_files else []
                repo_dict["dependency_files"] = list(stats.dependency_files) if stats.dependency_files else []
                
                # Activity metrics
                repo_dict["is_active"] = stats.is_active
                repo_dict["commit_frequency"] = stats.commit_frequency
                repo_dict["commits_last_month"] = stats.commits_last_month
                repo_dict["commits_last_year"] = stats.commits_last_year
                
                # Community metrics
                repo_dict["license_name"] = stats.license_name
                repo_dict["license_spdx_id"] = stats.license_spdx_id
                repo_dict["contributors_count"] = stats.contributors_count
                repo_dict["open_issues"] = stats.open_issues
                repo_dict["open_prs"] = stats.open_prs
                repo_dict["closed_issues"] = stats.closed_issues
                repo_dict["topics"] = list(stats.topics) if stats.topics else []
                repo_dict["stars"] = stats.stars
                repo_dict["forks"] = stats.forks
                repo_dict["watchers"] = stats.watchers
                
                # Additional metadata
                repo_dict["description"] = stats.description
                repo_dict["homepage"] = stats.homepage
                
                # Analysis scores
                repo_dict["maintenance_score"] = stats.maintenance_score
                repo_dict["popularity_score"] = stats.popularity_score
                repo_dict["code_quality_score"] = stats.code_quality_score
                repo_dict["documentation_score"] = stats.documentation_score
                
                # Anomalies and structure
                repo_dict["anomalies"] = list(stats.anomalies) if stats.anomalies else []
                repo_dict["is_monorepo"] = stats.is_monorepo
                repo_dict["primary_language"] = stats.primary_language
                repo_dict["project_structure"] = dict(stats.project_structure) if stats.project_structure else {}
                
                repo_dicts.append(repo_dict)
                
            except Exception as e:
                logger.warning(f"Failed to convert repository '{stats.name}' to JSON: {str(e)}")
                # Add a simplified version instead
                repo_dicts.append({
                    "name": stats.name,
                    "error": f"Failed to serialize: {str(e)}",
                    "is_private": getattr(stats, "is_private", False),
                    "total_files": getattr(stats, "total_files", 0),
                    "total_loc": getattr(stats, "total_loc", 0)
                })
        
        json_data = {
            'metadata': {
                'username': self.username,
                'generated_at': datetime.now().replace(tzinfo=timezone.utc).isoformat(),
                'total_repositories': len(all_stats),
                'empty_repositories': len(empty_repos),
                'analyzer_version': '1.0.0'
            },
            'repositories': repo_dicts,
            'aggregated_stats': {
                'total_loc': sum(s.total_loc for s in non_empty_repos),
                'total_files': sum(s.total_files for s in non_empty_repos),
                'total_stars': sum(s.stars for s in all_stats),
                'total_forks': sum(s.forks for s in all_stats),
                'active_repos': sum(1 for s in non_empty_repos if s.is_active),
                'repos_with_docs': sum(1 for s in non_empty_repos if s.has_docs),
                'repos_with_tests': sum(1 for s in non_empty_repos if s.has_tests),
                'avg_maintenance_score': sum(s.maintenance_score for s in non_empty_repos) / len(non_empty_repos) if non_empty_repos else 0
            }
        }
        
        json_path = self.reports_dir / "repository_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, cls=DateTimeEncoder, ensure_ascii=False)
        
        logger.info(f"JSON report saved to {json_path}")
