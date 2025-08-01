"""
GitHub Repository Reporter Module

This module generates detailed reports based on repository analysis data.
It creates Markdown reports with repository statistics, code quality metrics,
and project insights.
"""

from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

from console import logger
from models import RepoStats


class ReportAggregator:
    """Helper class for aggregating repository statistics"""

    def __init__(self, reports_dir, username, all_stats: List[RepoStats]):
        self.reports_dir = reports_dir
        self.all_stats = all_stats
        self.username = username
        self.empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        self.non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]

    def get_basic_stats(self) -> Dict:
        """Calculate basic repository statistics"""
        total_repos = len(self.all_stats)
        total_empty_repos = len(self.empty_repos)
        non_empty_count = len(self.non_empty_repos)

        # Calculate totals
        total_loc = sum(stats.total_loc for stats in self.non_empty_repos)
        total_files = sum(stats.total_files for stats in self.non_empty_repos)
        total_stars = sum(stats.stars for stats in self.all_stats)
        total_forks = sum(stats.forks for stats in self.all_stats)
        total_watchers = sum(stats.watchers for stats in self.all_stats)

        # Calculate excluded files statistics
        total_excluded_files = sum(getattr(stats, 'excluded_file_count', 0) for stats in self.all_stats)
        all_files_including_excluded = total_files + total_excluded_files

        # Calculate averages (only for non-empty repos)
        avg_loc_per_repo = self._safe_divide(total_loc, non_empty_count)
        avg_files_per_repo = self._safe_divide(total_files, non_empty_count)
        avg_maintenance_score = self._safe_divide(
            sum(stats.maintenance_score for stats in self.non_empty_repos),
            non_empty_count
        )

        return {
            'total_repos': total_repos,
            'total_empty_repos': total_empty_repos,
            'total_loc': total_loc,
            'total_files': total_files,
            'total_stars': total_stars,
            'total_forks': total_forks,
            'total_watchers': total_watchers,
            'total_excluded_files': total_excluded_files,
            'all_files_including_excluded': all_files_including_excluded,
            'non_empty_count': non_empty_count,
            'avg_loc_per_repo': avg_loc_per_repo,
            'avg_files_per_repo': avg_files_per_repo,
            'avg_maintenance_score': avg_maintenance_score
        }

    def get_quality_metrics(self):
        """Calculate quality-related metrics"""
        non_empty_count = len(self.non_empty_repos)

        # Count repositories with various quality features
        quality_counts = self._count_quality_features()

        # Documentation and README quality breakdown
        docs_size_categories = Counter(
            s.docs_size_category for s in self.non_empty_repos if s.has_docs
        )
        readme_categories = Counter(
            s.readme_comprehensiveness for s in self.non_empty_repos if s.has_readme
        )

        # Release statistics
        release_stats = self._calculate_release_stats()

        # Test coverage information
        coverage_stats = self._calculate_coverage_stats()

        # License statistics
        license_counts = Counter(
            stats.license_name for stats in self.all_stats if stats.license_name
        )

        return {
            'non_empty_count': non_empty_count,
            **quality_counts,
            'docs_size_categories': docs_size_categories,
            'readme_categories': readme_categories,
            **release_stats,
            **coverage_stats,
            'license_counts': license_counts
        }

    def get_rankings(self) -> Dict:
        """Get repository rankings"""
        return {
            'top_by_loc': self._get_top_by_metric(
                self.non_empty_repos, lambda x: x.total_loc, 10
            ),
            'top_by_stars': self._get_top_by_metric(
                self.all_stats, lambda x: x.stars, 10
            ),
            'top_by_quality': self._get_top_by_metric(
                self.non_empty_repos, lambda x: x.code_quality_score, 10
            ),
            'top_by_activity': self._get_top_by_metric(
                self.non_empty_repos, lambda x: x.commits_last_month, 10
            )
        }

    def get_language_stats(self) -> Dict:
        """Get language-related statistics"""
        # Aggregate language data across repositories with consistency checking
        all_languages = self._get_consistent_language_data(self.non_empty_repos)
        sorted_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)

        # Primary language distribution
        primary_languages = Counter(
            stats.primary_language for stats in self.non_empty_repos
            if stats.primary_language
        )

        return {
            'all_languages': all_languages,
            'sorted_languages': sorted_languages,
            'primary_languages': primary_languages
        }

    def get_quality_scores(self) -> Dict:
        """Calculate average quality scores"""
        non_empty_count = len(self.non_empty_repos)

        if non_empty_count == 0:
            return {
                'avg_maintenance_score': 0.0,
                'avg_code_quality': 0.0,
                'avg_docs_quality': 0.0,
                'avg_popularity': 0.0
            }

        return {
            'avg_maintenance_score': self._safe_divide(
                sum(stats.maintenance_score for stats in self.non_empty_repos),
                non_empty_count
            ),
            'avg_code_quality': self._safe_divide(
                sum(stats.code_quality_score for stats in self.non_empty_repos),
                non_empty_count
            ),
            'avg_docs_quality': self._safe_divide(
                sum(stats.documentation_score for stats in self.non_empty_repos),
                non_empty_count
            ),
            'avg_popularity': self._safe_divide(
                sum(stats.popularity_score for stats in self.non_empty_repos),
                non_empty_count
            )
        }

    def get_monorepo_stats(self) -> Dict:
        """Get monorepo-related statistics"""
        monorepos = [s for s in self.non_empty_repos if s.is_monorepo]

        if not monorepos:
            return {
                'monorepos': [],
                'count': 0,
                'avg_loc': 0,
                'top_monorepos': []
            }

        avg_loc = self._safe_divide(sum(s.total_loc for s in monorepos), len(monorepos))
        top_monorepos = self._get_top_by_metric(monorepos, lambda x: x.total_loc, 5)

        return {
            'monorepos': monorepos,
            'count': len(monorepos),
            'avg_loc': avg_loc,
            'top_monorepos': top_monorepos
        }

    def get_commit_activity(self) -> Dict:
        """Get commit activity statistics"""
        total_commits_last_month = sum(stats.commits_last_month for stats in self.non_empty_repos)
        total_commits_last_year = sum(stats.commits_last_year for stats in self.non_empty_repos)

        active_repos = sum(1 for stats in self.non_empty_repos if stats.is_active)
        avg_monthly_commits = self._safe_divide(total_commits_last_month, active_repos)

        return {
            'total_commits_last_month': total_commits_last_month,
            'total_commits_last_year': total_commits_last_year,
            'avg_monthly_commits': avg_monthly_commits
        }

    def generate_aggregated_report(self) -> None:
        """Generate aggregated statistics report"""
        logger.info("Generating aggregated statistics report")

        report_path = self.reports_dir / "aggregated_stats.md"

        # Initialize aggregator
        aggregator = self

        # Get all statistics
        stats_data = self._gather_all_statistics(aggregator)

        with open(report_path, 'w', encoding='utf-8') as f:
            self._write_report_header(f)
            self._write_overview_section(f, stats_data['basic_stats'])
            self._write_community_stats_section(f, stats_data['basic_stats'])
            self._write_language_usage_section(f, stats_data['language_stats'], stats_data['basic_stats'])
            self._write_quality_metrics_section(f, stats_data['quality_metrics'], stats_data['basic_stats'])
            self._write_excluded_files_section(f, stats_data['basic_stats'])
            self._write_license_distribution_section(f, stats_data['quality_metrics'], stats_data['basic_stats'])
            self._write_rankings_section(f, stats_data['rankings'], aggregator)
            self._write_primary_language_section(f, stats_data['language_stats'], stats_data['quality_metrics'],
                                                 aggregator)
            self._write_quality_scores_section(f, stats_data['quality_scores'], aggregator)
            self._write_monorepo_section(f, stats_data['monorepo_stats'], stats_data['quality_metrics'])
            self._write_commit_activity_section(f, stats_data['commit_activity'], stats_data['quality_metrics'],
                                                aggregator)

        logger.info(f"Aggregated report saved to {report_path}")

    # Helper methods

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        """Safely divide two numbers, returning 0 if denominator is 0"""
        return numerator / denominator if denominator > 0 else 0.0

    def _count_quality_features(self) -> Dict:
        """Count repositories with various quality features"""
        return {
            'active_repos': sum(1 for stats in self.non_empty_repos if stats.is_active),
            'repos_with_docs': sum(1 for stats in self.non_empty_repos if stats.has_docs),
            'repos_with_tests': sum(1 for stats in self.non_empty_repos if stats.has_tests),
            'repos_with_readme': sum(1 for stats in self.non_empty_repos if stats.has_readme),
            'repos_with_packages': sum(1 for stats in self.non_empty_repos if stats.has_packages),
            'repos_with_deployments': sum(1 for stats in self.non_empty_repos if stats.has_deployments),
            'repos_with_releases': sum(1 for stats in self.non_empty_repos if stats.has_releases)
        }

    def _calculate_release_stats(self) -> Dict:
        """Calculate release-related statistics"""
        repos_with_releases = sum(1 for s in self.non_empty_repos if s.has_releases)
        total_releases = sum(s.release_count for s in self.non_empty_repos if s.has_releases)
        avg_releases = self._safe_divide(total_releases, repos_with_releases)

        return {
            'total_releases': total_releases,
            'avg_releases': avg_releases
        }

    def _calculate_coverage_stats(self) -> Dict:
        """Calculate test coverage statistics"""
        repos_with_coverage = [
            s for s in self.non_empty_repos
            if s.quality.test_coverage_percentage is not None
        ]

        if not repos_with_coverage:
            return {
                'repos_with_coverage': repos_with_coverage,
                'avg_test_coverage': 0,
                'coverage_distribution': {'high': 0, 'medium': 0, 'low': 0}
            }

        avg_test_coverage = self._safe_divide(
            sum(s.quality.test_coverage_percentage for s in repos_with_coverage),
            len(repos_with_coverage)
        )

        coverage_distribution = {
            'high': sum(1 for s in repos_with_coverage if s.quality.test_coverage_percentage > 70),
            'medium': sum(1 for s in repos_with_coverage if 30 < s.quality.test_coverage_percentage <= 70),
            'low': sum(1 for s in repos_with_coverage if s.quality.test_coverage_percentage <= 30)
        }

        return {
            'repos_with_coverage': repos_with_coverage,
            'avg_test_coverage': avg_test_coverage,
            'coverage_distribution': coverage_distribution
        }

    @staticmethod
    def _get_top_by_metric(repos: List, metric_func, limit: int) -> List:
        """Get top repositories by a given metric"""
        return sorted(repos, key=metric_func, reverse=True)[:limit]

    def _get_consistent_language_data(self, repos: List[RepoStats]) -> Dict[str, int]:
        """Process language data with consistency checks to avoid inflated LOC counts"""
        # Calculate total LOC sum for validation
        total_loc_sum = sum(repo.total_loc for repo in repos)
        logger.info(f"Total LOC across repositories: {total_loc_sum:,}")

        # Collect language data with consistency checks
        all_languages = defaultdict(int)
        skipped_repos = 0

        for repo in repos:
            # Check if repository has any language data
            lang_sum = sum(repo.languages.values())

            if lang_sum == 0:
                # If repository has LOC but no language data, add to "Unknown"
                if repo.total_loc > 0:
                    all_languages["Unknown"] += repo.total_loc
                    logger.info(
                        f"Adding {repo.total_loc} LOC from {repo.name} to 'Unknown' language (no language data)")
                continue

            # Skip repositories with anomalous language data (language sum much larger than total LOC)
            if lang_sum > repo.total_loc * 1.1:  # Allow 10% margin for rounding
                # Instead of skipping, add to "Unknown" language
                all_languages["Unknown"] += repo.total_loc
                logger.warning(
                    f"Repository {repo.name} has inconsistent language data. Adding its {repo.total_loc} LOC to 'Unknown'.")
                skipped_repos += 1
                continue

            # Add languages for repositories with consistent data
            for lang, loc in repo.languages.items():
                all_languages[lang] += loc

        if skipped_repos > 0:
            logger.warning(
                f"Found {skipped_repos} repositories with inconsistent language data (added to 'Unknown' language)")

        # Verify and log the total sum of language-specific LOC
        lang_loc_sum = sum(all_languages.values())
        logger.info(f"Sum of language-specific LOC: {lang_loc_sum:,}")

        # Final adjustment if still different
        if lang_loc_sum != total_loc_sum:
            all_languages = self._adjust_language_totals(all_languages, total_loc_sum, lang_loc_sum)

        return all_languages

    @staticmethod
    def _adjust_language_totals(all_languages: Dict, total_loc_sum: int, lang_loc_sum: int) -> Dict:
        """Adjust language totals to match expected total LOC"""
        logger.info(f"Adjusting language data to match total LOC: {total_loc_sum:,}")

        if lang_loc_sum < total_loc_sum:
            # Add difference to Unknown
            difference = total_loc_sum - lang_loc_sum
            all_languages["Unknown"] = all_languages.get("Unknown", 0) + difference
            logger.info(f"Added {difference:,} missing LOC to 'Unknown' language")
        elif lang_loc_sum > total_loc_sum:
            # Scale down proportionally
            scaling_factor = total_loc_sum / lang_loc_sum
            logger.warning(f"Scaling language LOC by factor of {scaling_factor:.2f} to match total LOC")
            all_languages = {lang: int(loc * scaling_factor) for lang, loc in all_languages.items()}

        return all_languages

    @staticmethod
    def _gather_all_statistics(aggregator) -> Dict:
        """Gather all statistics needed for the report"""
        return {
            'basic_stats': aggregator.get_basic_stats(),
            'quality_metrics': aggregator.get_quality_metrics(),
            'rankings': aggregator.get_rankings(),
            'language_stats': aggregator.get_language_stats(),
            'quality_scores': aggregator.get_quality_scores(),
            'monorepo_stats': aggregator.get_monorepo_stats(),
            'commit_activity': aggregator.get_commit_activity()
        }

    def _write_report_header(self, f):
        """Write the report header"""
        f.write("# 📊 Aggregated Repository Statistics\n\n")
        f.write(f"**User:** {self.username}\n")
        f.write(f"**Generated:** {datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def _write_overview_section(self, f, basic_stats: Dict):
        """Write the overview section"""
        f.write("## 🔍 Overview\n\n")
        f.write(f"- **Total Repositories Analyzed:** {basic_stats['total_repos']:,}\n")

        if basic_stats['total_empty_repos'] > 0:
            empty_percentage = self._safe_divide(
                basic_stats['total_empty_repos'] * 100,
                basic_stats['total_repos']
            )
            f.write(f"- **Empty Repositories:** {basic_stats['total_empty_repos']:,} ({empty_percentage:.1f}%)\n")

        f.write(f"- **Total Lines of Code:** {basic_stats['total_loc']:,}\n")
        f.write(f"- **Total Files Analyzed:** {basic_stats['total_files']:,}\n")

        # Add excluded files information if applicable
        if basic_stats['total_excluded_files'] > 0:
            excluded_percentage = self._safe_divide(
                basic_stats['total_excluded_files'] * 100,
                basic_stats['all_files_including_excluded']
            )
            f.write(
                f"- **Files Excluded from Analysis:** {basic_stats['total_excluded_files']:,} ({excluded_percentage:.1f}% of all files)\n")
            f.write(f"- **Total Files (Including Excluded):** {basic_stats['all_files_including_excluded']:,}\n")

        f.write(f"- **Average LOC per Repository:** {basic_stats['avg_loc_per_repo']:,.0f} (excluding empty repos)\n")
        f.write(
            f"- **Average Files per Repository:** {basic_stats['avg_files_per_repo']:.1f} (excluding empty repos)\n")
        f.write(
            f"- **Average Maintenance Score:** {basic_stats['avg_maintenance_score']:.1f}/100 (excluding empty repos)\n")
        f.write("\n")

    @staticmethod
    def _write_community_stats_section(f, basic_stats: Dict):
        """Write the community statistics section"""
        f.write("## 👥 Community Statistics\n\n")
        f.write(f"- **Total Stars:** ⭐ {basic_stats['total_stars']:,}\n")
        f.write(f"- **Total Forks:** 🍴 {basic_stats['total_forks']:,}\n")
        f.write(f"- **Total Watchers:** 👀 {basic_stats['total_watchers']:,}\n")
        f.write("\n")

    def _write_language_usage_section(self, f, language_stats: Dict, basic_stats: Dict):
        """Write the language usage section"""
        f.write("## 💻 Language Usage Summary\n\n")

        if language_stats['sorted_languages']:
            f.write("| Language | Lines of Code | Percentage |\n")
            f.write("|----------|---------------|------------|\n")
            for lang, loc in language_stats['sorted_languages'][:15]:  # Top 15 languages
                percentage = self._safe_divide(loc * 100, basic_stats['total_loc'])
                f.write(f"| {lang} | {loc:,} | {percentage:.1f}% |\n")
        else:
            f.write("No language data available.\n")
        f.write("\n")

    def _write_quality_metrics_section(self, f, quality_metrics: Dict, basic_stats: Dict):
        """Write the quality metrics section"""
        f.write("## ✅ Quality Metrics\n\n")

        non_empty_percent = self._safe_divide(
            (basic_stats['total_repos'] - basic_stats['total_empty_repos']) * 100,
            basic_stats['total_repos']
        )
        f.write(f"- **Non-Empty Repositories:** {quality_metrics['non_empty_count']} ({non_empty_percent:.1f}%)\n")

        if quality_metrics['non_empty_count'] > 0:
            self._write_quality_details(f, quality_metrics)
        else:
            self._write_empty_quality_details(f)

        # License count
        license_percentage = self._safe_divide(
            len(quality_metrics['license_counts']) * 100,
            basic_stats['total_repos']
        )
        f.write(
            f"- **Repositories with License:** {len(quality_metrics['license_counts'])} ({license_percentage:.1f}% of total)\n")
        f.write("\n")

    def _write_quality_details(self, f, quality_metrics: Dict):
        """Write detailed quality metrics for non-empty repositories"""
        non_empty_count = quality_metrics['non_empty_count']

        # Documentation stats
        docs_percentage = self._safe_divide(quality_metrics['repos_with_docs'] * 100, non_empty_count)
        f.write(
            f"- **Repositories with Documentation:** {quality_metrics['repos_with_docs']} ({docs_percentage:.1f}% of non-empty)\n")

        # Documentation quality breakdown
        self._write_quality_doc(f, quality_metrics)

        # README stats
        readme_percentage = self._safe_divide(quality_metrics['repos_with_readme'] * 100, non_empty_count)
        f.write(
            f"- **Repositories with README:** {quality_metrics['repos_with_readme']} ({readme_percentage:.1f}% of non-empty)\n")

        # README quality breakdown
        self._write_quality_readme(f, quality_metrics)

        # Other quality metrics
        quality_metrics_to_write = [
            ('repos_with_tests', 'Tests'),
            ('repos_with_packages', 'Package Management'),
            ('repos_with_deployments', 'Deployment Configuration'),
            ('repos_with_releases', 'Releases')
        ]

        for metric_key, metric_name in quality_metrics_to_write:
            count = quality_metrics[metric_key]
            percentage = self._safe_divide(count * 100, non_empty_count)
            f.write(f"- **Repositories with {metric_name}:** {count} ({percentage:.1f}% of non-empty)\n")

        # Release details
        if quality_metrics['repos_with_releases'] > 0:
            f.write(f"  - **Total Releases:** {quality_metrics['total_releases']}\n")
            f.write(
                f"  - **Average Releases per Repository:** {quality_metrics['avg_releases']:.1f} (repos with releases only)\n")

        # Test coverage information
        if quality_metrics['repos_with_coverage']:
            self._write_coverage_details(f, quality_metrics)

        # Activity stats
        activity_percentage = self._safe_divide(quality_metrics['active_repos'] * 100, non_empty_count)
        f.write(
            f"- **Active Repositories:** {quality_metrics['active_repos']} ({activity_percentage:.1f}% of non-empty)\n")

    def _write_quality_doc(self, f, quality_metrics):
        if quality_metrics['docs_size_categories']:
            f.write("  - **Documentation Size Categories:**\n")
            for category in ["None", "Small", "Intermediate", "Big"]:
                if category in quality_metrics['docs_size_categories']:
                    count = quality_metrics['docs_size_categories'][category]
                    percentage = self._safe_divide(count * 100, quality_metrics['repos_with_docs'])
                    f.write(f"    - {category}: {count} repos ({percentage:.1f}% of documented repos)\n")

    def _write_quality_readme(self, f, quality_metrics):
        if quality_metrics['readme_categories']:
            f.write("  - **README Quality Categories:**\n")
            for category in ["None", "Small", "Good", "Comprehensive"]:
                if category in quality_metrics['readme_categories']:
                    count = quality_metrics['readme_categories'][category]
                    percentage = self._safe_divide(count * 100, quality_metrics['repos_with_readme'])
                    f.write(f"    - {category}: {count} repos ({percentage:.1f}% of repos with README)\n")

    @staticmethod
    def _write_empty_quality_details(f):
        """Write quality metrics when there are no non-empty repositories"""
        quality_items = [
            "Documentation", "README", "Tests",
            "Package Management", "Deployment Configuration", "Releases"
        ]
        for item in quality_items:
            f.write(f"- **Repositories with {item}:** 0 (0.0% of non-empty)\n")
        f.write("- **Active Repositories:** 0 (0.0% of non-empty)\n")

    def _write_coverage_details(self, f, quality_metrics: Dict):
        """Write test coverage details"""
        f.write(f"  - **Average Test Coverage:** {quality_metrics['avg_test_coverage']:.1f}% (estimated)\n")

        repos_with_coverage_len = len(quality_metrics['repos_with_coverage'])
        if repos_with_coverage_len > 0:
            coverage_dist = quality_metrics['coverage_distribution']
            for coverage_level, threshold_desc in [('high', '>70%'), ('medium', '30-70%'), ('low', '<30%')]:
                count = coverage_dist[coverage_level]
                percentage = self._safe_divide(count * 100, repos_with_coverage_len)
                f.write(
                    f"  - **{coverage_level.title()} Coverage ({threshold_desc}):** {count} repos ({percentage:.1f}% of tested)\n")

    @staticmethod
    def _write_excluded_files_section(f, basic_stats: Dict):
        """Write the excluded files section if applicable"""
        if basic_stats['total_excluded_files'] > 0:
            f.write("## 📁 Files & Directories Exclusion\n\n")
            f.write("For accuracy, the following content was excluded from LOC analysis:\n\n")
            f.write("- **Build artifacts:** bin, obj, build, dist, target, Debug, Release, x64, etc.\n")
            f.write("- **Package directories:** node_modules, vendor, venv, .gradle, etc.\n")
            f.write("- **IDE settings:** .vs, .vscode, .idea, __pycache__, etc.\n")
            f.write("- **Generated files:** Binary files, compiled outputs, etc.\n")
            f.write(
                "\nThis exclusion provides more accurate source code metrics by focusing on developer-written code rather than including auto-generated files, binary artifacts, or third-party dependencies.\n\n")

    def _write_license_distribution_section(self, f, quality_metrics: Dict, basic_stats: Dict):
        """Write the license distribution section"""
        if quality_metrics['license_counts']:
            f.write("## ⚖️ License Distribution\n\n")
            f.write("| License | Count | Percentage |\n")
            f.write("|---------|-------|------------|\n")

            for license_name, count in quality_metrics['license_counts'].most_common(10):
                percentage = self._safe_divide(count * 100, basic_stats['total_repos'])
                f.write(f"| {license_name} | {count} | {percentage:.1f}% |\n")
            f.write("\n")

    @staticmethod
    def _write_rankings_section(f, rankings: Dict, aggregator):
        """Write the repository rankings section"""
        f.write("## 🏆 Repository Rankings\n\n")

        # Top repositories by LOC
        f.write("### 📏 Top 10 Largest Repositories (by LOC)\n\n")
        for i, stats in enumerate(rankings['top_by_loc'], 1):
            f.write(f"{i}. **{stats.name}** - {stats.total_loc:,} LOC\n")
        f.write("\n")

        # Top repositories by stars
        f.write("### ⭐ Top 10 Most Starred Repositories\n\n")
        for i, stats in enumerate(rankings['top_by_stars'], 1):
            empty_tag = " (empty)" if "Empty repository with no files" in stats.anomalies else ""
            f.write(f"{i}. **{stats.name}** - {stats.stars:,} stars{empty_tag}\n")
        f.write("\n")

        # Top repositories by code quality
        if aggregator.non_empty_repos:
            f.write("### 💯 Top 10 Highest Quality Repositories\n\n")
            for i, stats in enumerate(rankings['top_by_quality'], 1):
                f.write(f"{i}. **{stats.name}** - Quality Score: {stats.code_quality_score:.1f}/100\n")
            f.write("\n")

            # Top repositories by activity
            f.write("### 🔥 Top 10 Most Active Repositories\n\n")
            for i, stats in enumerate(rankings['top_by_activity'], 1):
                f.write(f"{i}. **{stats.name}** - {stats.commits_last_month} commits last month\n")
            f.write("\n")

    def _write_primary_language_section(self, f, language_stats: Dict, quality_metrics: Dict, aggregator):
        """Write the primary language distribution section"""
        if aggregator.non_empty_repos and language_stats['primary_languages']:
            f.write("## 📊 Primary Language Distribution\n\n")
            f.write("| Language | Repositories | Percentage |\n")
            f.write("|----------|--------------|------------|\n")

            for lang, count in language_stats['primary_languages'].most_common(10):
                percentage = self._safe_divide(count * 100, quality_metrics['non_empty_count'])
                f.write(f"| {lang} | {count} | {percentage:.1f}% |\n")
            f.write("\n")

    @staticmethod
    def _write_quality_scores_section(f, quality_scores: Dict, aggregator):
        """Write the average quality scores section"""
        if aggregator.non_empty_repos:
            f.write("## 📈 Average Quality Scores\n\n")
            f.write(f"- **Average Maintenance Score:** {quality_scores['avg_maintenance_score']:.1f}/100\n")
            f.write(f"- **Average Code Quality Score:** {quality_scores['avg_code_quality']:.1f}/100\n")
            f.write(f"- **Average Documentation Score:** {quality_scores['avg_docs_quality']:.1f}/100\n")
            f.write(f"- **Average Popularity Score:** {quality_scores['avg_popularity']:.1f}/100\n")
            f.write("\n")

    def _write_monorepo_section(self, f, monorepo_stats: Dict, quality_metrics: Dict):
        """Write the monorepo analysis section"""
        if monorepo_stats['count'] > 0:
            monorepo_percentage = self._safe_divide(
                monorepo_stats['count'] * 100,
                quality_metrics['non_empty_count']
            )
            f.write("## 📦 Monorepo Analysis\n\n")
            f.write(
                f"- **Monorepos Detected:** {monorepo_stats['count']} ({monorepo_percentage:.1f}% of non-empty repos)\n")
            f.write(f"- **Average LOC in Monorepos:** {monorepo_stats['avg_loc']:,.0f}\n")
            f.write("\n")

            # Top monorepos
            f.write("### Largest Monorepos\n\n")
            for i, stats in enumerate(monorepo_stats['top_monorepos'], 1):
                f.write(f"{i}. **{stats.name}** - {stats.total_loc:,} LOC\n")
            f.write("\n")

    @staticmethod
    def _write_commit_activity_section(f, commit_activity: Dict, quality_metrics: Dict, aggregator):
        """Write the commit activity summary section"""
        if aggregator.non_empty_repos:
            f.write("## 📅 Commit Activity Summary\n\n")
            f.write(f"- **Total Commits (Last Month):** {commit_activity['total_commits_last_month']:,}\n")
            f.write(f"- **Total Commits (Last Year):** {commit_activity['total_commits_last_year']:,}\n")

            if quality_metrics['active_repos'] > 0:
                f.write(
                    f"- **Average Monthly Commits per Active Repo:** {commit_activity['avg_monthly_commits']:.1f} (active repos only)\n")
            else:
                f.write("- **Average Monthly Commits per Active Repo:** 0.0 (no active repos found)\n")
            f.write("\n")


class DetailedReportGenerator:
    """Helper class for generating detailed repository reports"""

    def __init__(self, username: str, all_stats: List[RepoStats]):
        self.username = username
        self.all_stats = all_stats
        self.empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        self.non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]

    def write_header(self, f):
        """Write the report header"""
        f.write("# 📊 Detailed Repository Analysis Report\n\n")
        f.write(f"**User:** {self.username}\n")
        f.write(f"**Generated:** {datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Repositories:** {len(self.all_stats)}\n\n")

    def write_table_of_contents(self, f):
        """Write the table of contents"""
        f.write("## 📋 Table of Contents\n\n")
        for i, stats in enumerate(self.all_stats, 1):
            anchor = stats.name.lower().replace(' ', '-').replace('_', '-')
            f.write(f"{i}. [🔗 {stats.name}](#{anchor})\n")
        f.write("\n---\n\n")

    def write_empty_repositories_section(self, f):
        """Write the empty repositories section"""
        if not self.empty_repos:
            return

        f.write("## 🗑️ Empty Repositories\n\n")
        f.write("The following repositories are empty (have no files or commits):\n\n")
        for repo in self.empty_repos:
            f.write(f"- **{repo.name}** - Created on {repo.created_at.strftime('%Y-%m-%d')}\n")
        f.write("\n---\n\n")

    def _get_top_maintained_repos(self, limit: int = 10):
        """Get top maintained repositories sorted by maintenance score"""
        return sorted(self.non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:limit]

    def write_top_maintained_section(self, f):
        """Write the top maintained repositories section"""
        f.write("### 🔧 Top 10 Best Maintained Repositories\n\n")
        top_by_maintenance = self._get_top_maintained_repos()
        for i, stats in enumerate(top_by_maintenance, 1):
            f.write(f"{i}. **{stats.name}** - {stats.maintenance_score:.1f}/100\n")
        f.write("\n")

    def _get_active_repos_sorted(self, limit: int = 10):
        """Get active repositories sorted by last commit date"""
        active_repos = [
            s for s in self.all_stats
            if s.activity.is_active and "Empty repository with no files" not in s.scores.anomalies
        ]
        return sorted(active_repos, key=lambda x: x.activity.last_commit_date, reverse=True)[:limit]

    def write_most_active_section(self, f):
        """Write the most active repositories section"""
        f.write("### 🚀 Most Active Repositories (Recent Activity)\n\n")
        active_repos_sorted = self._get_active_repos_sorted()
        for i, stats in enumerate(active_repos_sorted, 1):
            last_commit_str = stats.activity.last_commit_date.strftime('%Y-%m-%d')
            f.write(f"{i}. **{stats.name}** - Last commit: {last_commit_str}\n")
        f.write("\n")

    def _get_oldest_repos(self, limit: int = 5):
        """Get oldest repositories"""
        return sorted(self.all_stats, key=lambda x: x.created_at)[:limit]

    def _get_newest_repos(self, limit: int = 5):
        """Get newest repositories"""
        return sorted(self.all_stats, key=lambda x: x.created_at, reverse=True)[:limit]

    def write_oldest_projects_section(self, f):
        """Write oldest projects section"""
        f.write("### 🏛️ Oldest Projects\n")
        oldest_repos = self._get_oldest_repos()
        for i, stats in enumerate(oldest_repos, 1):
            f.write(f"{i}. **{stats.name}** - Created: {stats.created_at.strftime('%Y-%m-%d')}\n")
        f.write("\n")

    def write_newest_projects_section(self, f):
        """Write newest projects section"""
        f.write("### 🆕 Newest Projects\n")
        newest_repos = self._get_newest_repos()
        for i, stats in enumerate(newest_repos, 1):
            f.write(f"{i}. **{stats.name}** - Created: {stats.created_at.strftime('%Y-%m-%d')}\n")
        f.write("\n")

    def write_project_age_analysis(self, f):
        """Write the project age analysis section"""
        f.write("## 📅 Project Age Analysis\n\n")
        self.write_oldest_projects_section(f)
        self.write_newest_projects_section(f)

    def _get_large_repos_without_docs(self, min_loc: int = 1000, limit: int = 5):
        """Get large repositories without documentation"""
        large_no_docs = [s for s in self.all_stats if s.total_loc > min_loc and not s.has_docs]
        return sorted(large_no_docs, key=lambda x: x.total_loc, reverse=True)[:limit]

    def write_large_repos_without_docs(self, f):
        """Write large repositories without documentation section"""
        large_no_docs = self._get_large_repos_without_docs()
        if not large_no_docs:
            return

        f.write("### 📚 Large Repositories Without Documentation\n")
        for stats in large_no_docs:
            f.write(f"- **{stats.name}** - {stats.total_loc:,} LOC, no documentation\n")
        f.write("\n")

    def _get_large_repos_without_tests(self, min_loc: int = 1000, limit: int = 5):
        """Get large repositories without tests"""
        large_no_tests = [s for s in self.all_stats if s.total_loc > min_loc and not s.has_tests]
        return sorted(large_no_tests, key=lambda x: x.total_loc, reverse=True)[:limit]

    def write_large_repos_without_tests(self, f):
        """Write large repositories without tests section"""
        large_no_tests = self._get_large_repos_without_tests()
        if not large_no_tests:
            return

        f.write("### 🧪 Large Repositories Without Tests\n")
        for stats in large_no_tests:
            f.write(f"- **{stats.name}** - {stats.total_loc:,} LOC, no tests\n")
        f.write("\n")

    def _get_stale_repos(self, min_loc: int = 100, limit: int = 10):
        """Get potentially stale repositories"""
        stale_repos = [s for s in self.all_stats if not s.is_active and s.total_loc > min_loc]
        return sorted(stale_repos, key=lambda x: x.last_commit_date)[:limit]

    def write_stale_repos_section(self, f):
        """Write potentially stale repositories section"""
        stale_repos = self._get_stale_repos()
        if not stale_repos:
            return

        f.write("### 💤 Potentially Stale Repositories\n")
        for stats in stale_repos:
            last_activity_str = stats.last_commit_date.strftime('%Y-%m-%d')
            f.write(f"- **{stats.name}** - Last activity: {last_activity_str}\n")
        f.write("\n")

    def write_anomaly_detection(self, f):
        """Write the anomaly detection section"""
        f.write("## 🚨 Repository Anomalies\n\n")
        self.write_large_repos_without_docs(f)
        self.write_large_repos_without_tests(f)
        self.write_stale_repos_section(f)

    @staticmethod
    def _format_repo_type_badges(stats):
        """Format repository type badges"""
        repo_type = []
        if stats.is_fork:
            repo_type.append("🍴 Fork")
        if stats.is_archived:
            repo_type.append("📦 Archived")
        if stats.is_template:
            repo_type.append("📋 Template")
        if "Empty repository with no files" in stats.anomalies:
            repo_type.append("🗑️ Empty")
        if not repo_type:
            repo_type.append("📁 Regular")
        return " | ".join(repo_type)

    @staticmethod
    def _format_last_pushed_date(stats):
        """Format last pushed date with null handling"""
        return stats.last_pushed.strftime('%Y-%m-%d') if stats.last_pushed else 'Unknown'

    def write_individual_repository_basic_info(self, f, stats):
        """Write basic information for an individual repository"""
        f.write("### ℹ️ Basic Information\n")
        f.write(f"- **Repository Name:** {stats.name}\n")
        f.write(f"- **Visibility:** {'🔒 Private' if stats.is_private else '🌍 Public'}\n")
        f.write(f"- **Default Branch:** {stats.default_branch}\n")
        f.write(f"- **Type:** {self._format_repo_type_badges(stats)}\n")
        f.write(f"- **Created:** {stats.created_at.strftime('%Y-%m-%d')}\n")
        f.write(f"- **Last Pushed:** {self._format_last_pushed_date(stats)}\n")

        if stats.description:
            f.write(f"- **Description:** {stats.description}\n")
        if stats.homepage:
            f.write(f"- **Homepage:** {stats.homepage}\n")
        f.write("\n")

    @staticmethod
    def write_individual_repository_code_stats(f, stats):
        """Write code statistics for an individual repository"""
        f.write("### 📈 Code Statistics\n")
        f.write(f"- **Total Files:** {stats.total_files:,}\n")
        f.write(f"- **Total Lines of Code:** {stats.total_loc:,}\n")
        f.write(f"- **Average LOC per File:** {stats.avg_loc_per_file:.1f}\n")
        f.write(f"- **Repository Size:** {stats.size_kb:,} KB\n")
        f.write("\n")

    @staticmethod
    def _get_top_languages(stats, limit: int = 10):
        """Get top languages for a repository"""
        if not stats.languages:
            return []
        return sorted(stats.languages.items(), key=lambda x: x[1], reverse=True)[:limit]

    def write_individual_repository_languages(self, f, stats):
        """Write languages section for an individual repository"""
        if not stats.languages:
            return

        f.write("### 💻 Languages Used\n")
        sorted_langs = self._get_top_languages(stats)
        for lang, loc in sorted_langs:
            percentage = (loc / stats.total_loc * 100) if stats.total_loc > 0 else 0
            f.write(f"- **{lang}:** {loc:,} LOC ({percentage:.1f}%)\n")
        f.write("\n")

    @staticmethod
    def _get_top_file_types(stats, limit: int = 10):
        """Get top file types for a repository"""
        if not stats.file_types:
            return []
        return sorted(stats.file_types.items(), key=lambda x: x[1], reverse=True)[:limit]

    def write_individual_repository_file_types(self, f, stats):
        """Write file types section for an individual repository"""
        if not stats.file_types:
            return

        f.write("### 📄 File Types\n")
        sorted_types = self._get_top_file_types(stats)
        for file_type, count in sorted_types:
            f.write(f"- **{file_type}:** {count} files\n")
        f.write("\n")

    @staticmethod
    def _write_documentation_details(f, stats):
        """Write documentation details"""
        if stats.has_docs:
            f.write(f"  - **Documentation Size:** {stats.docs_size_category} ({stats.docs_files_count} files)\n")

    @staticmethod
    def _write_readme_details(f, stats):
        """Write README details"""
        if stats.has_readme:
            f.write(f"  - **README Quality:** {stats.readme_comprehensiveness} ({stats.readme_line_count} lines)\n")

    @staticmethod
    def _write_test_details(f, stats):
        """Write test details"""
        if not stats.has_tests:
            return

        f.write(f"  - **Test Files:** {stats.test_files_count} files\n")
        if stats.quality.test_coverage_percentage is not None:
            coverage = stats.quality.test_coverage_percentage
            coverage_emoji = "🟢" if coverage > 70 else "🟡" if coverage > 30 else "🔴"
            f.write(f"  - **Estimated Test Coverage:** {coverage_emoji} {coverage:.1f}% (estimated from file count)\n")

    @staticmethod
    def _write_releases_info(f, stats):
        """Write releases information"""
        if stats.has_releases:
            f.write(f" ({stats.release_count} releases)\n")
        else:
            f.write("\n")

    def write_individual_repository_quality_indicators(self, f, stats):
        """Write quality indicators section for an individual repository"""
        f.write("### ✅ Quality Indicators\n")
        f.write(f"- **Has Documentation:** {'✅ Yes' if stats.has_docs else '❌ No'}\n")
        self._write_documentation_details(f, stats)

        f.write(f"- **Has README:** {'✅ Yes' if stats.has_readme else '❌ No'}\n")
        self._write_readme_details(f, stats)

        f.write(f"- **Has Tests:** {'✅ Yes' if stats.has_tests else '❌ No'}\n")
        self._write_test_details(f, stats)

        f.write(f"- **Has CI/CD:** {'✅ Yes' if stats.has_cicd else '❌ No'}\n")
        f.write(f"- **Has Package Management:** {'✅ Yes' if stats.has_packages else '❌ No'}\n")
        f.write(f"- **Has Deployment Config:** {'✅ Yes' if stats.has_deployments else '❌ No'}\n")
        f.write(f"- **Has Releases:** {'✅ Yes' if stats.has_releases else '❌ No'}")
        self._write_releases_info(f, stats)

        f.write(f"- **Is Active:** {'✅ Yes' if stats.is_active else '❌ No'} (commits in last 6 months)\n")
        f.write(f"- **License:** {stats.license_name or '❌ No License'}\n")
        f.write(f"- **Maintenance Score:** {stats.maintenance_score:.1f}/100\n")
        f.write("\n")

    @staticmethod
    def write_individual_repository_dependencies(f, stats):
        """Write dependencies section for an individual repository"""
        if not stats.dependency_files:
            return

        f.write("### 📦 Dependency Files\n")
        for dep_file in stats.dependency_files:
            f.write(f"- `{dep_file}`\n")
        f.write("\n")

    @staticmethod
    def write_individual_repository_community_stats(f, stats):
        """Write community statistics section for an individual repository"""
        f.write("### 👥 Community Statistics\n")
        f.write(f"- **Stars:** ⭐ {stats.stars:,}\n")
        f.write(f"- **Forks:** 🍴 {stats.forks:,}\n")
        f.write(f"- **Watchers:** 👀 {stats.watchers:,}\n")
        f.write(f"- **Contributors:** 👤 {stats.contributors_count:,}\n")
        f.write(f"- **Open Issues:** 🐛 {stats.open_issues:,}\n")
        f.write(f"- **Open Pull Requests:** 🔄 {stats.open_prs:,}\n")
        f.write("\n")

    @staticmethod
    def write_individual_repository_topics(f, stats):
        """Write topics section for an individual repository"""
        if not stats.topics:
            return

        f.write("### 🏷️ Topics\n")
        f.write(f"- {' | '.join(f'`{topic}`' for topic in stats.topics)}\n")
        f.write("\n")

    @staticmethod
    def _format_last_commit_date(stats):
        """Format last commit date with null handling"""
        if stats.last_commit_date:
            return stats.last_commit_date.strftime('%Y-%m-%d %H:%M:%S')
        return 'Unknown'

    def write_individual_repository_activity(self, f, stats):
        """Write activity section for an individual repository"""
        f.write("### 📅 Activity\n")
        f.write(f"- **Last Commit:** {self._format_last_commit_date(stats)}\n")
        f.write(f"- **Commits Last Month:** {stats.commits_last_month:,}\n")
        f.write(f"- **Commits Last Year:** {stats.commits_last_year:,}\n")
        if stats.commit_frequency is not None:
            f.write(f"- **Monthly Commit Frequency:** {stats.commit_frequency:.1f}\n")
        f.write("\n")

    @staticmethod
    def _analyze_project_organization(stats):
        """Analyze project organization patterns"""
        if not stats.project_structure:
            return []

        structure_keys = [d.lower() for d in stats.project_structure.keys()]
        patterns = []

        has_src = any(d in ['src', 'source', 'lib', 'app'] for d in structure_keys)
        has_tests = any(d in ['test', 'tests', 'spec', 'specs'] for d in structure_keys)
        has_docs = any(d in ['doc', 'docs', 'documentation'] for d in structure_keys)
        has_scripts = any(d in ['script', 'scripts', 'tools', 'util', 'utils'] for d in structure_keys)
        has_examples = any(d in ['example', 'examples', 'demo', 'demos', 'sample', 'samples'] for d in structure_keys)

        if has_src and has_tests:
            patterns.append("Standard src/test organization")
        if has_docs:
            patterns.append("Documented project")
        if has_scripts:
            patterns.append("Includes utility scripts")
        if has_examples:
            patterns.append("Includes examples/demos")

        return patterns

    @staticmethod
    def _get_structure_overview(stats):
        """Get project structure overview"""
        if not stats.project_structure:
            return None, None

        total_dirs = len(stats.project_structure)
        total_dir_files = sum(stats.project_structure.values())
        return total_dirs, total_dir_files

    @staticmethod
    def _get_top_directories(stats, limit: int = 8):
        """Get top directories by file count"""
        if not stats.project_structure:
            return []
        return sorted(stats.project_structure.items(), key=lambda x: x[1], reverse=True)[:limit]

    def write_individual_repository_project_structure(self, f, stats):
        """Write project structure section for an individual repository"""
        if not stats.project_structure:
            return

        f.write("### 📂 Project Structure\n")

        total_dirs, total_dir_files = self._get_structure_overview(stats)
        patterns = self._analyze_project_organization(stats)

        f.write(f"Repository contains {total_dirs} top-level directories with {total_dir_files} files.\n\n")

        if patterns:
            f.write(f"**Project Organization Pattern:** {', '.join(patterns)}\n\n")

        f.write("**Top-level directories:**\n\n")
        top_directories = self._get_top_directories(stats)
        for dir_name, count in top_directories:
            percentage = (count / total_dir_files * 100) if total_dir_files > 0 else 0
            f.write(f"- `{dir_name}/` - {count} files ({percentage:.1f}%)\n")
        f.write("\n")

    @staticmethod
    def write_individual_repository_quality_scores(f, stats):
        """Write quality scores section for an individual repository"""
        f.write("### 🏆 Quality Scores\n")
        f.write(f"- **Primary Language:** {stats.primary_language or 'Unknown'}\n")
        f.write(f"- **Maintenance Score:** {stats.maintenance_score:.1f}/100\n")
        f.write(f"- **Code Quality Score:** {stats.code_quality_score:.1f}/100\n")
        f.write(f"- **Documentation Score:** {stats.documentation_score:.1f}/100\n")
        f.write(f"- **Popularity Score:** {stats.popularity_score:.1f}/100\n")
        if stats.is_monorepo:
            f.write("- **Repository Type:** 📦 Monorepo (multiple major languages)\n")
        f.write("\n")

    @staticmethod
    def write_empty_repository_section(f):
        """Write section for empty repository"""
        f.write("### ⚠️ Empty Repository\n")
        f.write("This repository does not contain any files or commits.\n\n")
        f.write("---\n\n")

    def write_detailed_repository_sections(self, f, stats):
        """Write all detailed sections for a non-empty repository"""
        self.write_individual_repository_code_stats(f, stats)
        self.write_individual_repository_languages(f, stats)
        self.write_individual_repository_file_types(f, stats)
        self.write_individual_repository_quality_indicators(f, stats)
        self.write_individual_repository_dependencies(f, stats)
        self.write_individual_repository_community_stats(f, stats)
        self.write_individual_repository_topics(f, stats)
        self.write_individual_repository_activity(f, stats)
        self.write_individual_repository_project_structure(f, stats)
        self.write_individual_repository_quality_scores(f, stats)

    def write_individual_repository_report(self, f, stats):
        """Write the complete report for an individual repository"""
        anchor = stats.name.lower().replace(' ', '-').replace('_', '-')
        f.write(f"## <a id='{anchor}'></a>📦 {stats.name}\n\n")

        # Basic info for all repositories
        self.write_individual_repository_basic_info(f, stats)

        # Handle empty repositories differently
        if "Empty repository with no files" in stats.anomalies:
            self.write_empty_repository_section(f)
            return

        # Write detailed analysis for non-empty repositories
        self.write_detailed_repository_sections(f, stats)
        f.write("---\n\n")

    def generate(self, report_path: Path):
        """Generate the complete detailed report"""
        with open(report_path, 'w', encoding='utf-8') as f:
            self.write_header(f)
            self.write_table_of_contents(f)
            self.write_empty_repositories_section(f)
            self.write_top_maintained_section(f)
            self.write_most_active_section(f)
            self.write_project_age_analysis(f)
            self.write_anomaly_detection(f)

            # Individual repository reports
            for stats in self.all_stats:
                self.write_individual_repository_report(f, stats)


class GithubReporter:
    """Class responsible for generating reports from GitHub repository data"""

    def __init__(self, username: str, reports_dir: Path):
        """Initialize the reporter with username and reports directory"""
        self.username = username
        self.reports_dir = reports_dir

    def generate_detailed_report(self, all_stats: List[RepoStats]) -> None:
        """Generate detailed per-repository report"""
        logger.info("Generating detailed repository report")

        report_path = self.reports_dir / "repo_details.md"

        generator = DetailedReportGenerator(self.username, all_stats)
        generator.generate(report_path)

        logger.info(f"Detailed report saved to {report_path}")

    def generate_aggregated_report(self, all_stats: List[RepoStats]) -> None:
        """Generate aggregated statistics report"""
        logger.info("Generating detailed repository report")

        report_path = self.reports_dir / "repo_agg_details.md"

        agger = ReportAggregator(report_path, self.username, all_stats)
        agger.generate_aggregated_report()

        logger.info(f"Detailed report saved to {report_path}")

    def generate_reports(self, all_stats: List[RepoStats]) -> None:
        self.generate_detailed_report(all_stats)
        self.generate_aggregated_report(all_stats)
