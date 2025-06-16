"""
GitHub Repository Visualizer Module

This module generates interactive visualizations and dashboards for repository analysis.
It creates HTML reports with charts, graphs, and insights from repository data.
"""

import json
import os
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, NamedTuple, Optional, Dict

import matplotlib.pyplot as plt
import plotly.graph_objects as go
import seaborn as sns

from visualize.static import HTMLVisualizer
from visualize.static import JSCreator
from config import ThemeConfig, DefaultTheme
from console import logger
from models import RepoStats
from visualize import PersonalRepoAnalysis, OrganizationRepoAnalysis, CreateDetailedCharts


class HtmlContent(NamedTuple):
    """Named tuple for HTML dashboard content sections"""
    head_section: str
    body_start: str
    creator_section: str
    repo_type_tabs: str
    stats_section: str
    charts_section: str
    additional_charts_section: str
    chart_modal_container: str
    footer_section: str
    js_part1: str
    js_part2: str
    js_part3: str

    def combine(self) -> str:
        """Combine all HTML sections into a complete dashboard"""
        return "\n".join([
            self.head_section,
            self.body_start,
            self.creator_section,
            self.repo_type_tabs,
            self.stats_section,
            self.charts_section,
            self.additional_charts_section,
            self.chart_modal_container,
            self.footer_section,
            self.js_part1,
            self.js_part2,
            self.js_part3
        ])


def _get_ext_to_lang_mapping() -> dict:
    """Get the mapping of file extensions to languages"""
    return {
        ".py": "Python",
        ".js": "JavaScript",
        ".tsx": "TypeScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".rb": "Ruby",
        ".php": "PHP",
        ".go": "Go",
        ".rs": "Rust",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".html": "HTML",
        ".css": "CSS",
        ".sh": "Shell",
        ".vue": "Vue",
        ".dart": "Dart",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".scala": "Scala",
        ".m": "Objective-C",
        ".mm": "Objective-C",
        ".pl": "Perl",
        ".pm": "Perl",
        ".r": "R",
        ".lua": "Lua",
        ".groovy": "Groovy",
        ".sql": "SQL",
        ".md": "Markdown",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".xml": "XML",
        ".toml": "TOML",
        ".ex": "Elixir",
        ".exs": "Elixir",
        ".elm": "Elm",
        ".clj": "Clojure",
        ".fs": "F#",
        ".hs": "Haskell",
        ".jl": "Julia",
        ".nim": "Nim",
        ".zig": "Zig",
        ".tex": "LaTeX",
        ".ltx": "LaTeX",
        ".latex": "LaTeX"
    }


def get_timestamp():
    """Get current timestamp in UTC format"""
    return datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


class GithubVisualizer:
    """Class responsible for creating visualizations from GitHub repository data"""

    def __init__(self, username: str, reports_dir: Path, theme: Optional[ThemeConfig] = None):
        """Initialize the visualizer with username and reports directory"""
        self.all_stats: Optional[List[RepoStats]] = None
        self.username = username
        self.reports_dir = reports_dir
        self.assets_dir = Path(__file__).resolve().parent.parent / "assets"  # Changed from Path("static") / "assets" to just "assets"
        self.theme = theme if theme is not None else DefaultTheme.get_default_theme()
        self.prepo_analysis = PersonalRepoAnalysis(username, theme)
        # Initialize the organization repo analysis (will be used only if org repos are included)
        self.orepo_analysis = None
        # Flag to track if organization repos are included
        self.has_org_repos = False
        # Store org names for later use
        self.org_names = []

        # Copy assets to the reports directory
        self.copy_assets(reports_dir)

    def copy_assets(self, reports_dir: Path) -> None:
        """Copy assets to the reports directory"""
        assets_dir = self.assets_dir
        static_dir = reports_dir / "static" / "assets"  # Use reports_dir instead of hardcoded Path("reports/static/assets")
        os.makedirs(static_dir, exist_ok=True)

        for asset in assets_dir.glob("*"):
            try:
                shutil.copy(asset, static_dir / asset.name)
                logger.info(f"Copied asset {asset.name} to {static_dir}")
            except Exception as e:
                logger.error(f"Failed to copy asset {asset.name}: {str(e)}")

    def set_org_repos_included(self, org_names: List[str]) -> None:
        """Set flag to indicate organization repositories are included"""
        if org_names and len(org_names) > 0:
            self.has_org_repos = True
            self.org_names = org_names
            # Initialize the organization repo analysis with org names
            self.orepo_analysis = OrganizationRepoAnalysis(self.username, org_names, self.theme)
            logger.info(f"Organization repositories will be included: {', '.join(org_names)}")
        else:
            self.has_org_repos = False
            logger.info("No organization repositories will be included")

    def create_visualizations(self, all_stats: List[RepoStats], org_repos: Dict[str, List[RepoStats]] = None) -> None:
        """Generate visual reports with charts and graphs"""
        logger.info("Generating visual report")

        # Store all_stats as an instance attribute for later use
        self.all_stats = all_stats

        # Set org repos flag and process org repos if provided
        if org_repos and len(org_repos) > 0:
            self.set_org_repos_included(list(org_repos.keys()))
            # Process organization repositories if there are any
            if self.orepo_analysis:
                self.orepo_analysis.process_repositories(org_repos)

        logger.info(f"Organization repos flag: {self.has_org_repos}")
        logger.info(f"Organization names: {self.org_names}")

        # Filter out empty repositories for most visualizations
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]

        # Set up visualization environment
        self._setup_visualization_environment()

        # Process language data
        self._process_language_data(non_empty_repos)

        # Create main dashboard figure
        fig = self._create_dashboard_figure(non_empty_repos)

        # Create detailed charts
        self._create_detailed_charts()

        # Generate and save HTML dashboard
        self._save_dashboard_html(fig, non_empty_repos)

    @staticmethod
    def _setup_visualization_environment():
        """Set up the visualization environment with proper styling"""
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")

    def _process_language_data(self, non_empty_repos: List[RepoStats]) -> None:
        """Process and validate language data for repositories"""
        # Verify total LOC for sanity check
        total_loc_sum = sum(stats.total_loc for stats in non_empty_repos)
        logger.info(f"Total LOC across all repositories: {total_loc_sum:,}")

        # Debug output to verify LOC calculations
        logger.info("DEBUG: Running diagnostic on each repository's LOC calculations")
        for stats in non_empty_repos:
            self.debug_print_repo_stats(stats)

        # Collect language data more carefully
        all_languages = defaultdict(int)
        # Keep track of repositories that need their primary language changed to "Unknown"
        self.repos_with_unknown_language = set()
        # Store inferred languages based on file extensions
        self.inferred_languages = {}

        # Debug info: log repositories and their assigned languages before processing
        logger.info("Repository language data before processing:")
        for stats in non_empty_repos:
            logger.info(f"  {stats.name}: primary_language={stats.primary_language}, " +
                        f"language_data={stats.languages}, total_loc={stats.total_loc}")

        for stats in non_empty_repos:
            self._process_repo_language(stats, all_languages)

        # Log the repositories marked as having unknown language
        logger.info(f"Repositories with unknown language: {list(self.repos_with_unknown_language)}")
        logger.info(f"Repositories with inferred languages: {self.inferred_languages}")

        # Verify and log the total sum of language-specific LOC
        lang_loc_sum = sum(all_languages.values())
        logger.info(f"Sum of language-specific LOC: {lang_loc_sum:,}")

        # Final sanity check and adjustment
        self._adjust_language_totals(all_languages, total_loc_sum, lang_loc_sum)

        # Store processed language data for later use
        self.all_languages = all_languages

    @staticmethod
    def _standardize_language_name(language: str) -> str:
        """
        Standardize language names to handle aliases and variations.
        
        Args:
            language: The language name to standardize
            
        Returns:
            Standardized language name
        """
        # Language standardization mapping
        language_aliases = {
            'TeX': 'LaTeX',  # Treat TeX as LaTeX
            'React': 'JavaScript',  # For backward compatibility, treat React as JavaScript
            'ReactJS': 'JavaScript'
        }

        return language_aliases.get(language, language)

    def _process_repo_language(self, stats: RepoStats, all_languages: dict) -> None:
        """Process language data for a single repository"""
        # Check if repository has any valid language data
        lang_sum = sum(stats.languages.values())

        if lang_sum == 0:
            # No language data
            if stats.total_loc > 0:
                # Try to infer language from file types
                inferred_language = self._infer_language_from_file_types(stats)

                if inferred_language != "Unknown":
                    logger.info(f"Inferred language '{inferred_language}' for {stats.name} based on file extensions")
                    all_languages[inferred_language] += stats.total_loc
                    self.inferred_languages[stats.name] = inferred_language
                else:
                    # If we couldn't infer a language, use "Unknown"
                    logger.info(f"Adding {stats.total_loc} LOC from {stats.name} to 'Unknown' language")
                    all_languages["Unknown"] += stats.total_loc
                    self.repos_with_unknown_language.add(stats.name)
            else:
                # Zero LOC, just mark as unknown
                self.repos_with_unknown_language.add(stats.name)
        else:
            # Repository has language data
            for lang, loc in stats.languages.items():
                # Standardize language names (e.g., treat TeX as LaTeX)
                standardized_lang = self._standardize_language_name(lang)
                all_languages[standardized_lang] += loc

    @staticmethod
    def _infer_language_from_file_types(stats: RepoStats) -> str:
        """Infer the primary language of a repository based on file extensions"""
        # Map of file extensions to languages
        ext_to_lang = _get_ext_to_lang_mapping()

        # Count files by extension
        file_counts = defaultdict(int)
        for ext, count in stats.file_types.items():
            file_counts[ext] += count

        # Find the most common programming language extension
        max_count = 0
        inferred_language = "Unknown"
        for ext, count in file_counts.items():
            if ext in ext_to_lang and count > max_count:
                max_count = count
                inferred_language = ext_to_lang[ext]

        # Standardize the inferred language name
        return GithubVisualizer._standardize_language_name(inferred_language)

    @staticmethod
    def _adjust_language_totals(all_languages: dict, total_loc_sum: int, lang_loc_sum: int) -> None:
        """Adjust language totals to match the overall LOC count"""
        if total_loc_sum > 0 and abs(lang_loc_sum - total_loc_sum) > total_loc_sum * 0.01:  # 1% tolerance
            logger.warning(f"Language LOC sum ({lang_loc_sum}) differs from total LOC ({total_loc_sum})")
            # Add adjustment to make totals match exactly
            diff = total_loc_sum - lang_loc_sum
            if diff > 0:
                all_languages["Unknown"] = all_languages.get("Unknown", 0) + diff
                logger.info(f"Added {diff} LOC to 'Unknown' to match total LOC")
            else:
                # If language sum is higher than total, scale down proportionally
                scaling_factor = total_loc_sum / lang_loc_sum
                logger.info(f"Scaling languages by factor {scaling_factor:.4f} to match total LOC")
                for lang in all_languages:
                    all_languages[lang] = int(all_languages[lang] * scaling_factor)

    def _create_dashboard_figure(self, non_empty_repos: List[RepoStats]) -> go.Figure:
        """Create the main dashboard figure with multiple subplots"""
        # Set any data the PersonalRepoAnalysis needs
        self.prepo_analysis.all_languages = self.all_languages

        # Delegate to the PersonalRepoAnalysis class
        return self.prepo_analysis.create_dashboard_figure(non_empty_repos)

    def _create_detailed_charts(self) -> None:
        """Create detailed charts for in-depth analysis"""
        logger.info("Starting to create detailed charts...")

        # Ensure the static directory exists
        static_dir = Path("reports/static")
        os.makedirs(static_dir, exist_ok=True)

        # Create detailed charts
        detailed_charts = CreateDetailedCharts(self.all_stats, self.theme, self.reports_dir)
        detailed_charts.create()

        # Verify that charts were created
        chart_files = list(self.reports_dir.glob("*.png"))
        logger.info(f"Created {len(chart_files)} chart files: {[f.name for f in chart_files]}")

    def _save_dashboard_html(self, fig: go.Figure, non_empty_repos: List[RepoStats]) -> None:
        """Generate and save the HTML dashboard"""
        # Create HTML with Tailwind CSS, custom styling and interactivity
        html_content = self._generate_dashboard_html(fig, non_empty_repos)

        # Save as interactive HTML
        report_path = self.reports_dir / "visual_report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Visual report saved to {report_path}")

    def _generate_dashboard_html(self, fig, non_empty_repos):
        """Generate HTML content for the dashboard with Tailwind CSS and theme support"""
        # Get timestamp for the report
        timestamp = get_timestamp()

        # Create statistics
        stats = self._calculate_repository_statistics(non_empty_repos)

        # Log information about repos with unknown language
        self._log_unknown_language_repositories()

        # Prepare repository data for the table
        repos_table_data, languages_in_table = self._prepare_repository_table_data(non_empty_repos)

        # Log summary of languages in table
        self._log_language_summary(languages_in_table)

        # Convert to JSON for JavaScript
        repos_json = json.dumps(repos_table_data)

        # Create HTML content using HTMLVisualizer
        html_content = self._build_html_content(fig, timestamp, stats, repos_json)

        return html_content

    @staticmethod
    def _calculate_repository_statistics(non_empty_repos):
        """Calculate key statistics from repository data"""
        return {
            "total_repos": len(non_empty_repos),
            "total_loc": f"{sum(s.total_loc for s in non_empty_repos):,}",
            "total_stars": f"{sum(s.stars for s in non_empty_repos):,}",
            "active_repos": sum(1 for s in non_empty_repos if s.is_active)
        }

    def _log_unknown_language_repositories(self):
        """Log information about repositories with unknown languages"""
        if hasattr(self, 'repos_with_unknown_language'):
            logger.info(
                f"In _generate_dashboard_html: Found repos_with_unknown_language with {len(self.repos_with_unknown_language)} entries")
            logger.info(f"  Content: {sorted(list(self.repos_with_unknown_language))}")
        else:
            logger.warning("In _generate_dashboard_html: repos_with_unknown_language attribute not found!")

    def _prepare_repository_table_data(self, non_empty_repos):
        """Prepare repository data for the dashboard table"""
        repos_table_data = []
        languages_in_table = {}

        for repo in non_empty_repos:
            language = self._determine_repository_language(repo)

            # Track languages for later summary
            languages_in_table[repo.name] = language

            # Create a comprehensive dictionary with all available metadata
            repo_data = {
                # Basic Info
                "name": repo.name,
                "language": language,
                "description": repo.description,
                "url": f"https://github.com/{self.username}/{repo.name}",
                "default_branch": repo.default_branch,
                "is_fork": repo.is_fork,
                "is_archived": repo.is_archived,
                "is_template": repo.is_template,
                "homepage": repo.homepage,

                # Stats
                "stars": repo.stars,
                "forks": repo.forks,
                "watchers": repo.watchers,
                "loc": repo.total_loc,
                "size_kb": repo.size_kb,
                "total_files": repo.total_files,
                "avg_loc_per_file": round(repo.avg_loc_per_file, 2),
                "open_issues": repo.open_issues,
                "closed_issues": repo.closed_issues,
                "open_prs": repo.open_prs,

                # Dates
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.last_pushed.isoformat() if repo.last_pushed else None,
                "last_commit_date": repo.last_commit_date.isoformat() if repo.last_commit_date else None,

                # Development
                "primary_language": repo.primary_language,
                "file_types": repo.file_types,
                "project_structure": repo.project_structure,
                "is_monorepo": repo.is_monorepo,
                "contributors_count": repo.contributors_count,
                "commit_frequency": repo.commit_frequency,
                "commits_last_month": repo.commits_last_month,
                "commits_last_year": repo.commits_last_year,

                # Quality
                "has_ci": repo.has_cicd,
                "has_tests": repo.has_tests,
                "test_files_count": repo.test_files_count,
                "test_coverage_percentage": repo.test_coverage_percentage,
                "has_docs": repo.has_docs,
                "docs_files_count": repo.docs_files_count,
                "docs_size_category": repo.docs_size_category,
                "readme_comprehensiveness": repo.readme_comprehensiveness,
                "readme_line_count": repo.readme_line_count,

                # Infrastructure
                "has_deployments": repo.has_deployments,
                "deployment_files": repo.deployment_files,
                "has_packages": repo.has_packages,
                "package_files": repo.package_files,
                "has_releases": repo.has_releases,
                "release_count": repo.release_count,
                "dependency_files": repo.dependency_files,
                "cicd_files": repo.cicd_files,

                # Community
                "license_name": repo.license_name,
                "license_spdx_id": repo.license_spdx_id,
                "topics": repo.topics,

                # Scores
                "is_active": repo.is_active,
                "maintenance": f"{repo.maintenance_score:.1f}",
                "code_quality_score": round(repo.code_quality_score, 2),
                "documentation_score": round(repo.documentation_score, 2),
                "popularity_score": round(repo.popularity_score, 2),
                "anomalies": repo.anomalies
            }

            repos_table_data.append(repo_data)

        return repos_table_data, languages_in_table

    def _determine_repository_language(self, repo):
        """Determine the primary language for a repository"""
        # Check if this repository has an inferred language
        if hasattr(self, 'inferred_languages') and repo.name in self.inferred_languages:
            language = self.inferred_languages[repo.name]
        # Otherwise check if it's marked as Unknown
        elif hasattr(self, 'repos_with_unknown_language') and repo.name in self.repos_with_unknown_language:
            language = "Unknown"
        # Fallback to the original primary language
        else:
            language = repo.primary_language or "Unknown"

        # Standardize the language name
        language = self._standardize_language_name(language)

        # Log individual language decisions
        if repo.primary_language != language:
            logger.info(
                f"Repository {repo.name}: Overriding primary_language '{repo.primary_language}' with '{language}'")

        return language

    @staticmethod
    def _log_language_summary(languages_in_table):
        """Log summary of languages used in repositories"""
        logger.info("Summary of languages in repository table:")
        for repo_name, language in sorted(languages_in_table.items()):
            logger.info(f"  {repo_name}: {language}")

    def _build_html_content(self, fig, timestamp, stats, repos_json):
        """Build the complete HTML content for the dashboard"""
        html_visualizer = HTMLVisualizer(self.username, self.reports_dir, self.theme)
        js_creator = JSCreator(self.theme, html_visualizer.bg_html_js)
        # Create JavaScript sections
        js_part2 = js_creator.create_js_part2(
            fig,
            stats["total_repos"],
            stats["total_loc"],
            stats["total_stars"],
            stats["active_repos"]
        )
        js_part1 = js_creator.create_js_part1()
        repo_table_js = js_creator.create_repo_table_js(repos_json)
        repo_tabs_js = js_creator.create_repo_tabs_js(self.has_org_repos)
        js_part3 = js_creator.create_js_part3(repo_table_js, repo_tabs_js)

        # Create HTML content as named tuple
        html_content = HtmlContent(
            head_section=html_visualizer.create_head_section(),
            body_start=html_visualizer.create_body_start(timestamp),
            creator_section=html_visualizer.create_creator_section(),
            repo_type_tabs=html_visualizer.create_repo_type_tabs(self.has_org_repos),
            stats_section=html_visualizer.create_stats_section(),
            charts_section=html_visualizer.create_charts_section(self.has_org_repos, self.orepo_analysis,
                                                                 self.prepo_analysis),
            additional_charts_section=html_visualizer.create_additional_charts_section(),
            chart_modal_container=html_visualizer.create_chart_modal_container(),
            footer_section=html_visualizer.create_footer_section(timestamp),
            js_part1=js_part1,
            js_part2=js_part2,
            js_part3=js_part3
        )

        # Return the combined HTML content
        return html_content.combine()

    @staticmethod
    def debug_print_repo_stats(repo_stats: RepoStats) -> None:
        """Debug method to print detailed information about a repository's LOC calculations"""
        lang_sum = sum(repo_stats.languages.values())
        logger.info(f"DEBUG: Repository: {repo_stats.name}")
        logger.info(f"DEBUG: Languages: {repo_stats.languages}")
        logger.info(f"DEBUG: Language sum: {lang_sum}")
        logger.info(f"DEBUG: total_loc: {repo_stats.total_loc}")
        logger.info(f"DEBUG: Difference: {lang_sum - repo_stats.total_loc}")
        # Force recalculation
        repo_stats.code_stats.calculate_primary_language()
        logger.info(f"DEBUG: After recalculation, total_loc: {repo_stats.total_loc}")
