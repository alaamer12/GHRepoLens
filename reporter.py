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
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 📊 Detailed Repository Analysis Report\n\n")
            f.write(f"**User:** {self.username}\n")
            f.write(f"**Generated:** {datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Repositories:** {len(all_stats)}\n\n")
            
            # Table of Contents
            f.write("## 📋 Table of Contents\n\n")
            for i, stats in enumerate(all_stats, 1):
                anchor = stats.name.lower().replace(' ', '-').replace('_', '-')
                f.write(f"{i}. [🔗 {stats.name}](#{anchor})\n")
            f.write("\n---\n\n")
            
            # Empty repositories
            empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
            if empty_repos:
                f.write("## 🗑️ Empty Repositories\n\n")
                f.write("The following repositories are empty (have no files or commits):\n\n")
                for repo in empty_repos:
                    f.write(f"- **{repo.name}** - Created on {repo.created_at.strftime('%Y-%m-%d')}\n")
                f.write("\n---\n\n")
            
            # Top repositories by maintenance score
            f.write("### 🔧 Top 10 Best Maintained Repositories\n\n")
            # Filter out empty repositories for this ranking
            non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
            top_by_maintenance = sorted(non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:10]
            for i, stats in enumerate(top_by_maintenance, 1):
                f.write(f"{i}. **{stats.name}** - {stats.maintenance_score:.1f}/100\n")
            f.write("\n")
            
            # Most active repositories
            f.write("### 🚀 Most Active Repositories (Recent Activity)\n\n")
            active_repos_sorted = sorted([s for s in all_stats if s.activity.is_active and "Empty repository with no files" not in s.scores.anomalies], 
                                       key=lambda x: x.activity.last_commit_date, reverse=True)[:10]
            for i, stats in enumerate(active_repos_sorted, 1):
                f.write(f"{i}. **{stats.name}** - Last commit: {stats.activity.last_commit_date.strftime('%Y-%m-%d')}\n")
            f.write("\n")
            
            # Project age analysis
            f.write("## 📅 Project Age Analysis\n\n")
            oldest_repos = sorted(all_stats, key=lambda x: x.created_at)[:5]
            newest_repos = sorted(all_stats, key=lambda x: x.created_at, reverse=True)[:5]
            
            f.write("### 🏛️ Oldest Projects\n")
            for i, stats in enumerate(oldest_repos, 1):
                f.write(f"{i}. **{stats.name}** - Created: {stats.created_at.strftime('%Y-%m-%d')}\n")
            f.write("\n")
            
            f.write("### 🆕 Newest Projects\n")
            for i, stats in enumerate(newest_repos, 1):
                f.write(f"{i}. **{stats.name}** - Created: {stats.created_at.strftime('%Y-%m-%d')}\n")
            f.write("\n")
            
            # Anomaly detection
            f.write("## 🚨 Repository Anomalies\n\n")
            
            # Large repos without docs
            large_no_docs = [s for s in all_stats if s.total_loc > 1000 and not s.has_docs]
            if large_no_docs:
                f.write("### 📚 Large Repositories Without Documentation\n")
                for stats in sorted(large_no_docs, key=lambda x: x.total_loc, reverse=True)[:5]:
                    f.write(f"- **{stats.name}** - {stats.total_loc:,} LOC, no documentation\n")
                f.write("\n")
            
            # Large repos without tests
            large_no_tests = [s for s in all_stats if s.total_loc > 1000 and not s.has_tests]
            if large_no_tests:
                f.write("### 🧪 Large Repositories Without Tests\n")
                for stats in sorted(large_no_tests, key=lambda x: x.total_loc, reverse=True)[:5]:
                    f.write(f"- **{stats.name}** - {stats.total_loc:,} LOC, no tests\n")
                f.write("\n")
            
            # Stale repositories
            stale_repos = [s for s in all_stats if not s.is_active and s.total_loc > 100]
            if stale_repos:
                f.write("### 💤 Potentially Stale Repositories\n")
                for stats in sorted(stale_repos, key=lambda x: x.last_commit_date)[:10]:
                    f.write(f"- **{stats.name}** - Last activity: {stats.last_commit_date.strftime('%Y-%m-%d')}\n")
                f.write("\n")
            
            # Individual repository reports
            for stats in all_stats:
                anchor = stats.name.lower().replace(' ', '-').replace('_', '-')
                f.write(f"## <a id='{anchor}'></a>📦 {stats.name}\n\n")
                
                # Basic info
                f.write("### ℹ️ Basic Information\n")
                f.write(f"- **Repository Name:** {stats.name}\n")
                f.write(f"- **Visibility:** {'🔒 Private' if stats.is_private else '🌍 Public'}\n")
                f.write(f"- **Default Branch:** {stats.default_branch}\n")
                f.write(f"- **Type:** ")
                
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
                
                f.write(" | ".join(repo_type) + "\n")
                f.write(f"- **Created:** {stats.created_at.strftime('%Y-%m-%d')}\n")
                f.write(f"- **Last Pushed:** {stats.last_pushed.strftime('%Y-%m-%d') if stats.last_pushed else 'Unknown'}\n")
                
                if stats.description:
                    f.write(f"- **Description:** {stats.description}\n")
                if stats.homepage:
                    f.write(f"- **Homepage:** {stats.homepage}\n")
                f.write("\n")
                
                # Skip detailed analysis for empty repositories
                if "Empty repository with no files" in stats.anomalies:
                    f.write("### ⚠️ Empty Repository\n")
                    f.write("This repository does not contain any files or commits.\n\n")
                    f.write("---\n\n")
                    continue
            
                # Code statistics
                f.write("### 📈 Code Statistics\n")
                f.write(f"- **Total Files:** {stats.total_files:,}\n")
                f.write(f"- **Total Lines of Code:** {stats.total_loc:,}\n")
                f.write(f"- **Average LOC per File:** {stats.avg_loc_per_file:.1f}\n")
                f.write(f"- **Repository Size:** {stats.size_kb:,} KB\n")
                f.write("\n")
                
                # Languages
                if stats.languages:
                    f.write("### 💻 Languages Used\n")
                    sorted_langs = sorted(stats.languages.items(), key=lambda x: x[1], reverse=True)
                    for lang, loc in sorted_langs[:10]:  # Top 10 languages
                        percentage = (loc / stats.total_loc * 100) if stats.total_loc > 0 else 0
                        f.write(f"- **{lang}:** {loc:,} LOC ({percentage:.1f}%)\n")
                    f.write("\n")
                
                # File types
                if stats.file_types:
                    f.write("### 📄 File Types\n")
                    sorted_types = sorted(stats.file_types.items(), key=lambda x: x[1], reverse=True)
                    for file_type, count in sorted_types[:10]:  # Top 10 file types
                        f.write(f"- **{file_type}:** {count} files\n")
                    f.write("\n")
                
                # Quality indicators
                f.write("### ✅ Quality Indicators\n")
                f.write(f"- **Has Documentation:** {'✅ Yes' if stats.has_docs else '❌ No'}\n")
                if stats.has_docs:
                    f.write(f"  - **Documentation Size:** {stats.docs_size_category} ({stats.docs_files_count} files)\n")
                f.write(f"- **Has README:** {'✅ Yes' if stats.has_readme else '❌ No'}\n")
                if stats.has_readme:
                    f.write(f"  - **README Quality:** {stats.readme_comprehensiveness} ({stats.readme_line_count} lines)\n")
                f.write(f"- **Has Tests:** {'✅ Yes' if stats.has_tests else '❌ No'}\n")
                if stats.has_tests:
                    f.write(f"  - **Test Files:** {stats.test_files_count} files\n")
                    if stats.quality.test_coverage_percentage is not None:
                        coverage_emoji = "🟢" if stats.quality.test_coverage_percentage > 70 else "🟡" if stats.quality.test_coverage_percentage > 30 else "🔴"
                        f.write(f"  - **Estimated Test Coverage:** {coverage_emoji} {stats.quality.test_coverage_percentage:.1f}% (estimated from file count)\n")
                f.write(f"- **Has CI/CD:** {'✅ Yes' if stats.has_cicd else '❌ No'}\n")
                f.write(f"- **Has Package Management:** {'✅ Yes' if stats.has_packages else '❌ No'}\n")
                f.write(f"- **Has Deployment Config:** {'✅ Yes' if stats.has_deployments else '❌ No'}\n")
                f.write(f"- **Has Releases:** {'✅ Yes' if stats.has_releases else '❌ No'}")
                if stats.has_releases:
                    f.write(f" ({stats.release_count} releases)\n")
                else:
                    f.write("\n")
                f.write(f"- **Is Active:** {'✅ Yes' if stats.is_active else '❌ No'} (commits in last 6 months)\n")
                f.write(f"- **License:** {stats.license_name or '❌ No License'}\n")
                f.write(f"- **Maintenance Score:** {stats.maintenance_score:.1f}/100\n")
                f.write("\n")
                
                # Dependencies
                if stats.dependency_files:
                    f.write("### 📦 Dependency Files\n")
                    for dep_file in stats.dependency_files:
                        f.write(f"- `{dep_file}`\n")
                    f.write("\n")
                
                # Community stats
                f.write("### 👥 Community Statistics\n")
                f.write(f"- **Stars:** ⭐ {stats.stars:,}\n")
                f.write(f"- **Forks:** 🍴 {stats.forks:,}\n")
                f.write(f"- **Watchers:** 👀 {stats.watchers:,}\n")
                f.write(f"- **Contributors:** 👤 {stats.contributors_count:,}\n")
                f.write(f"- **Open Issues:** 🐛 {stats.open_issues:,}\n")
                f.write(f"- **Open Pull Requests:** 🔄 {stats.open_prs:,}\n")
                f.write("\n")
                
                # Topics
                if stats.topics:
                    f.write("### 🏷️ Topics\n")
                    f.write(f"- {' | '.join(f'`{topic}`' for topic in stats.topics)}\n")
                    f.write("\n")
                
                # Activity
                f.write("### 📅 Activity\n")
                f.write(f"- **Last Commit:** {stats.last_commit_date.strftime('%Y-%m-%d %H:%M:%S') if stats.last_commit_date else 'Unknown'}\n")
                f.write(f"- **Commits Last Month:** {stats.commits_last_month:,}\n")
                f.write(f"- **Commits Last Year:** {stats.commits_last_year:,}\n")
                if stats.commit_frequency is not None:
                    f.write(f"- **Monthly Commit Frequency:** {stats.commit_frequency:.1f}\n")
                f.write("\n")
                
                # Project structure
                if stats.project_structure:
                    f.write("### 📂 Project Structure\n")
                    sorted_structure = sorted(stats.project_structure.items(), key=lambda x: x[1], reverse=True)
                    
                    # Calculate directory stats
                    total_dirs = len(stats.project_structure)
                    total_dir_files = sum(stats.project_structure.values())
                    
                    # Identify potential project organization patterns
                    has_src = any(d.lower() in ['src', 'source', 'lib', 'app'] for d in stats.project_structure)
                    has_tests = any(d.lower() in ['test', 'tests', 'spec', 'specs'] for d in stats.project_structure)
                    has_docs = any(d.lower() in ['doc', 'docs', 'documentation'] for d in stats.project_structure)
                    has_scripts = any(d.lower() in ['script', 'scripts', 'tools', 'util', 'utils'] for d in stats.project_structure)
                    has_examples = any(d.lower() in ['example', 'examples', 'demo', 'demos', 'sample', 'samples'] for d in stats.project_structure)
                    
                    # Repository organization pattern
                    patterns = []
                    if has_src and has_tests:
                        patterns.append("Standard src/test organization")
                    if has_docs:
                        patterns.append("Documented project")
                    if has_scripts:
                        patterns.append("Includes utility scripts")
                    if has_examples:
                        patterns.append("Includes examples/demos")
                    
                    # Write project structure overview
                    f.write(f"Repository contains {total_dirs} top-level directories with {total_dir_files} files.\n\n")
                    if patterns:
                        f.write(f"**Project Organization Pattern:** {', '.join(patterns)}\n\n")
                    
                    # Show top directories
                    f.write("**Top-level directories:**\n\n")
                    for dir_name, count in sorted_structure[:8]:  # Show top 8 directories
                        percentage = (count / total_dir_files * 100) if total_dir_files > 0 else 0
                        f.write(f"- `{dir_name}/` - {count} files ({percentage:.1f}%)\n")
                    f.write("\n")
                
                # Additional scores
                f.write("### 🏆 Quality Scores\n")
                f.write(f"- **Primary Language:** {stats.primary_language or 'Unknown'}\n")
                f.write(f"- **Maintenance Score:** {stats.maintenance_score:.1f}/100\n")
                f.write(f"- **Code Quality Score:** {stats.code_quality_score:.1f}/100\n")
                f.write(f"- **Documentation Score:** {stats.documentation_score:.1f}/100\n")
                f.write(f"- **Popularity Score:** {stats.popularity_score:.1f}/100\n")
                if stats.is_monorepo:
                    f.write(f"- **Repository Type:** 📦 Monorepo (multiple major languages)\n")
                f.write("\n")
                
                f.write("---\n\n")
        
        logger.info(f"Detailed report saved to {report_path}")

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
                    logger.info(f"Adding {repo.total_loc} LOC from {repo.name} to 'Unknown' language (no language data)")
                continue
            
            # Skip repositories with anomalous language data (language sum much larger than total LOC)
            if lang_sum > repo.total_loc * 1.1:  # Allow 10% margin for rounding
                # Instead of skipping, add to "Unknown" language
                all_languages["Unknown"] += repo.total_loc
                logger.warning(f"Repository {repo.name} has inconsistent language data. Adding its {repo.total_loc} LOC to 'Unknown'.")
                skipped_repos += 1
                continue
                
            # Add languages for repositories with consistent data
            for lang, loc in repo.languages.items():
                all_languages[lang] += loc
        
        if skipped_repos > 0:
            logger.warning(f"Found {skipped_repos} repositories with inconsistent language data (added to 'Unknown' language)")
        
        # Verify and log the total sum of language-specific LOC
        lang_loc_sum = sum(all_languages.values())
        logger.info(f"Sum of language-specific LOC: {lang_loc_sum:,}")
        
        # Final adjustment if still different
        if lang_loc_sum != total_loc_sum:
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

    def generate_aggregated_report(self, all_stats: List[RepoStats]) -> None:
        """Generate aggregated statistics report"""
        logger.info("Generating aggregated statistics report")
        
        report_path = self.reports_dir / "aggregated_stats.md"
        
        # Separate empty and non-empty repositories
        empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
        
        # Calculate aggregated statistics (excluding empty repos for most metrics)
        total_repos = len(all_stats)
        total_empty_repos = len(empty_repos)
        total_loc = sum(stats.total_loc for stats in non_empty_repos)
        total_files = sum(stats.total_files for stats in non_empty_repos)
        total_stars = sum(stats.stars for stats in all_stats)  # Include stars from all repos
        total_forks = sum(stats.forks for stats in all_stats)  # Include forks from all repos
        total_watchers = sum(stats.watchers for stats in all_stats)  # Include watchers from all repos
        
        # Calculate excluded files statistics
        total_excluded_files = sum(getattr(stats, 'excluded_file_count', 0) for stats in all_stats)
        all_files_including_excluded = total_files + total_excluded_files
        
        # Aggregate language data across repositories with consistency checking
        all_languages = self._get_consistent_language_data(non_empty_repos)
        sorted_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)
        
        # License statistics
        license_counts = Counter(stats.license_name for stats in all_stats if stats.license_name)
        
        # Activity statistics
        active_repos = sum(1 for stats in non_empty_repos if stats.is_active)
        repos_with_docs = sum(1 for stats in non_empty_repos if stats.has_docs)
        repos_with_tests = sum(1 for stats in non_empty_repos if stats.has_tests)
        
        # Average statistics (only for non-empty repos)
        non_empty_count = len(non_empty_repos)
        avg_loc_per_repo = total_loc / non_empty_count if non_empty_count > 0 else 0
        avg_files_per_repo = total_files / non_empty_count if non_empty_count > 0 else 0
        avg_maintenance_score = sum(stats.maintenance_score for stats in non_empty_repos) / non_empty_count if non_empty_count > 0 else 0
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 📊 Aggregated Repository Statistics\n\n")
            f.write(f"**User:** {self.username}\n")
            f.write(f"**Generated:** {datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overview
            f.write("## 🔍 Overview\n\n")
            f.write(f"- **Total Repositories Analyzed:** {total_repos:,}\n")
            if total_empty_repos > 0:
                f.write(f"- **Empty Repositories:** {total_empty_repos:,} ({total_empty_repos/total_repos*100:.1f}%)\n")
            f.write(f"- **Total Lines of Code:** {total_loc:,}\n")
            f.write(f"- **Total Files Analyzed:** {total_files:,}\n")
            
            # Add excluded files information if applicable
            if total_excluded_files > 0:
                excluded_percentage = (total_excluded_files / all_files_including_excluded * 100) if all_files_including_excluded > 0 else 0
                f.write(f"- **Files Excluded from Analysis:** {total_excluded_files:,} ({excluded_percentage:.1f}% of all files)\n")
                f.write(f"- **Total Files (Including Excluded):** {all_files_including_excluded:,}\n")
            
            f.write(f"- **Average LOC per Repository:** {avg_loc_per_repo:,.0f} (excluding empty repos)\n")
            f.write(f"- **Average Files per Repository:** {avg_files_per_repo:.1f} (excluding empty repos)\n")
            f.write(f"- **Average Maintenance Score:** {avg_maintenance_score:.1f}/100 (excluding empty repos)\n")
            f.write("\n")
            
            # Community stats
            f.write("## 👥 Community Statistics\n\n")
            f.write(f"- **Total Stars:** ⭐ {total_stars:,}\n")
            f.write(f"- **Total Forks:** 🍴 {total_forks:,}\n")
            f.write(f"- **Total Watchers:** 👀 {total_watchers:,}\n")
            f.write("\n")
            
            # Language usage
            f.write("## 💻 Language Usage Summary\n\n")
            if sorted_languages:
                f.write("| Language | Lines of Code | Percentage |\n")
                f.write("|----------|---------------|------------|\n")
                for lang, loc in sorted_languages[:15]:  # Top 15 languages
                    percentage = (loc / total_loc * 100) if total_loc > 0 else 0
                    f.write(f"| {lang} | {loc:,} | {percentage:.1f}% |\n")
            else:
                f.write("No language data available.\n")
            f.write("\n")
            
            # Quality metrics
            f.write("## ✅ Quality Metrics\n\n")
            non_empty_percent = 100 * (total_repos - total_empty_repos) / total_repos if total_repos > 0 else 0
            f.write(f"- **Non-Empty Repositories:** {non_empty_count} ({non_empty_percent:.1f}%)\n")
            if non_empty_count > 0:
                f.write(f"- **Repositories with Documentation:** {repos_with_docs} ({repos_with_docs/non_empty_count*100:.1f}% of non-empty)\n")
                # Add documentation quality breakdown
                docs_size_categories = Counter(s.docs_size_category for s in non_empty_repos if s.has_docs)
                if docs_size_categories:
                    f.write("  - **Documentation Size Categories:**\n")
                    for category, count in sorted(docs_size_categories.items(), key=lambda x: ["None", "Small", "Intermediate", "Big"].index(x[0])):
                        percentage = count / repos_with_docs * 100 if repos_with_docs > 0 else 0
                        f.write(f"    - {category}: {count} repos ({percentage:.1f}% of documented repos)\n")
                
                # Add README quality breakdown
                repos_with_readme = sum(1 for s in non_empty_repos if s.has_readme)
                f.write(f"- **Repositories with README:** {repos_with_readme} ({repos_with_readme/non_empty_count*100:.1f}% of non-empty)\n")
                readme_categories = Counter(s.readme_comprehensiveness for s in non_empty_repos if s.has_readme)
                if readme_categories:
                    f.write("  - **README Quality Categories:**\n")
                    for category, count in sorted(readme_categories.items(), key=lambda x: ["None", "Small", "Good", "Comprehensive"].index(x[0])):
                        percentage = count / repos_with_readme * 100 if repos_with_readme > 0 else 0
                        f.write(f"    - {category}: {count} repos ({percentage:.1f}% of repos with README)\n")
                
                f.write(f"- **Repositories with Tests:** {repos_with_tests} ({repos_with_tests/non_empty_count*100:.1f}% of non-empty)\n")
                
                # Package management stats
                repos_with_packages = sum(1 for s in non_empty_repos if s.has_packages)
                f.write(f"- **Repositories with Package Management:** {repos_with_packages} ({repos_with_packages/non_empty_count*100:.1f}% of non-empty)\n")
                
                # Deployment configuration stats
                repos_with_deployments = sum(1 for s in non_empty_repos if s.has_deployments)
                f.write(f"- **Repositories with Deployment Configuration:** {repos_with_deployments} ({repos_with_deployments/non_empty_count*100:.1f}% of non-empty)\n")
                
                # Release stats
                repos_with_releases = sum(1 for s in non_empty_repos if s.has_releases)
                f.write(f"- **Repositories with Releases:** {repos_with_releases} ({repos_with_releases/non_empty_count*100:.1f}% of non-empty)\n")
                if repos_with_releases > 0:
                    total_releases = sum(s.release_count for s in non_empty_repos if s.has_releases)
                    avg_releases = total_releases / repos_with_releases
                    f.write(f"  - **Total Releases:** {total_releases}\n")
                    f.write(f"  - **Average Releases per Repository:** {avg_releases:.1f} (repos with releases only)\n")
            else:
                f.write(f"- **Repositories with Documentation:** 0 (0.0% of non-empty)\n")
                f.write(f"- **Repositories with README:** 0 (0.0% of non-empty)\n")
                f.write(f"- **Repositories with Tests:** 0 (0.0% of non-empty)\n")
                f.write(f"- **Repositories with Package Management:** 0 (0.0% of non-empty)\n")
                f.write(f"- **Repositories with Deployment Configuration:** 0 (0.0% of non-empty)\n")
                f.write(f"- **Repositories with Releases:** 0 (0.0% of non-empty)\n")
            
            # Test coverage information
            repos_with_coverage = [s for s in non_empty_repos if s.quality.test_coverage_percentage is not None]
            if repos_with_coverage:
                avg_test_coverage = sum(s.quality.test_coverage_percentage for s in repos_with_coverage) / len(repos_with_coverage)
                f.write(f"  - **Average Test Coverage:** {avg_test_coverage:.1f}% (estimated)\n")
                
                # Coverage distribution
                high_coverage = sum(1 for s in repos_with_coverage if s.quality.test_coverage_percentage > 70)
                med_coverage = sum(1 for s in repos_with_coverage if 30 < s.quality.test_coverage_percentage <= 70)
                low_coverage = sum(1 for s in repos_with_coverage if s.quality.test_coverage_percentage <= 30)
                
                repos_with_coverage_len = len(repos_with_coverage)
                if repos_with_coverage_len > 0:
                    f.write(f"  - **High Coverage (>70%):** {high_coverage} repos ({high_coverage/repos_with_coverage_len*100:.1f}% of tested)\n")
                    f.write(f"  - **Medium Coverage (30-70%):** {med_coverage} repos ({med_coverage/repos_with_coverage_len*100:.1f}% of tested)\n")
                    f.write(f"  - **Low Coverage (<30%):** {low_coverage} repos ({low_coverage/repos_with_coverage_len*100:.1f}% of tested)\n")
            
            if non_empty_count > 0:
                f.write(f"- **Active Repositories:** {active_repos} ({active_repos/non_empty_count*100:.1f}% of non-empty)\n")
            else:
                f.write(f"- **Active Repositories:** 0 (0.0% of non-empty)\n")
            
            if total_repos > 0:
                f.write(f"- **Repositories with License:** {len(license_counts)} ({len(license_counts)/total_repos*100:.1f}% of total)\n")
            else:
                f.write(f"- **Repositories with License:** 0 (0.0% of total)\n")
            f.write("\n")
            
            # Add excluded content information
            if total_excluded_files > 0:
                f.write("## 📁 Files & Directories Exclusion\n\n")
                f.write("For accuracy, the following content was excluded from LOC analysis:\n\n")
                f.write("- **Build artifacts:** bin, obj, build, dist, target, Debug, Release, x64, etc.\n")
                f.write("- **Package directories:** node_modules, vendor, venv, .gradle, etc.\n")
                f.write("- **IDE settings:** .vs, .vscode, .idea, __pycache__, etc.\n") 
                f.write("- **Generated files:** Binary files, compiled outputs, etc.\n")
                f.write("\nThis exclusion provides more accurate source code metrics by focusing on developer-written code rather than including auto-generated files, binary artifacts, or third-party dependencies.\n\n")
            
            # License distribution
            if license_counts:
                f.write("## ⚖️ License Distribution\n\n")
                f.write("| License | Count | Percentage |\n")
                f.write("|---------|-------|------------|\n")
                for license_name, count in license_counts.most_common(10):
                    if total_repos > 0:
                        percentage = (count / total_repos * 100)
                        f.write(f"| {license_name} | {count} | {percentage:.1f}% |\n")
                    else:
                        f.write(f"| {license_name} | {count} | N/A% |\n")
                f.write("\n")
            
            # Repository rankings (excluding empty repositories)
            f.write("## 🏆 Repository Rankings\n\n")
            
            # Top repositories by LOC
            f.write("### 📏 Top 10 Largest Repositories (by LOC)\n\n")
            top_by_loc = sorted(non_empty_repos, key=lambda x: x.total_loc, reverse=True)[:10]
            for i, stats in enumerate(top_by_loc, 1):
                f.write(f"{i}. **{stats.name}** - {stats.total_loc:,} LOC\n")
            f.write("\n")
            
            # Top repositories by stars
            f.write("### ⭐ Top 10 Most Starred Repositories\n\n")
            top_by_stars = sorted(all_stats, key=lambda x: x.stars, reverse=True)[:10]
            for i, stats in enumerate(top_by_stars, 1):
                empty_tag = " (empty)" if "Empty repository with no files" in stats.anomalies else ""
                f.write(f"{i}. **{stats.name}** - {stats.stars:,} stars{empty_tag}\n")
            f.write("\n")
            
            # Top repositories by code quality
            if non_empty_repos:
                f.write("### 💯 Top 10 Highest Quality Repositories\n\n")
                top_by_quality = sorted(non_empty_repos, key=lambda x: x.code_quality_score, reverse=True)[:10]
                for i, stats in enumerate(top_by_quality, 1):
                    f.write(f"{i}. **{stats.name}** - Quality Score: {stats.code_quality_score:.1f}/100\n")
                f.write("\n")
            
            # Top repositories by activity
            if non_empty_repos:
                f.write("### 🔥 Top 10 Most Active Repositories\n\n")
                top_by_activity = sorted(non_empty_repos, key=lambda x: x.commits_last_month, reverse=True)[:10]
                for i, stats in enumerate(top_by_activity, 1):
                    f.write(f"{i}. **{stats.name}** - {stats.commits_last_month} commits last month\n")
                f.write("\n")
            
            # Primary language distribution
            if non_empty_repos:
                primary_languages = Counter(stats.primary_language for stats in non_empty_repos if stats.primary_language)
                if primary_languages:
                    f.write("## 📊 Primary Language Distribution\n\n")
                    f.write("| Language | Repositories | Percentage |\n")
                    f.write("|----------|--------------|------------|\n")
                    for lang, count in primary_languages.most_common(10):
                        if non_empty_count > 0:
                            percentage = (count / non_empty_count * 100)
                            f.write(f"| {lang} | {count} | {percentage:.1f}% |\n")
                        else:
                            f.write(f"| {lang} | {count} | N/A% |\n")
                    f.write("\n")
            
            # Average quality scores
            if non_empty_repos:
                f.write("## 📈 Average Quality Scores\n\n")
                if non_empty_count > 0:
                    avg_code_quality = sum(stats.code_quality_score for stats in non_empty_repos) / non_empty_count
                    avg_docs_quality = sum(stats.documentation_score for stats in non_empty_repos) / non_empty_count
                    avg_popularity = sum(stats.popularity_score for stats in non_empty_repos) / non_empty_count
                    
                    f.write(f"- **Average Maintenance Score:** {avg_maintenance_score:.1f}/100\n")
                    f.write(f"- **Average Code Quality Score:** {avg_code_quality:.1f}/100\n")
                    f.write(f"- **Average Documentation Score:** {avg_docs_quality:.1f}/100\n")
                    f.write(f"- **Average Popularity Score:** {avg_popularity:.1f}/100\n")
                else:
                    f.write(f"- **Average Maintenance Score:** 0.0/100\n")
                    f.write(f"- **Average Code Quality Score:** 0.0/100\n")
                    f.write(f"- **Average Documentation Score:** 0.0/100\n")
                    f.write(f"- **Average Popularity Score:** 0.0/100\n")
                f.write("\n")
            
            # Monorepo statistics
            monorepos = [s for s in non_empty_repos if s.is_monorepo]
            if monorepos:
                if non_empty_count > 0:
                    monorepo_percentage = (len(monorepos) / non_empty_count * 100)
                    f.write(f"## 📦 Monorepo Analysis\n\n")
                    f.write(f"- **Monorepos Detected:** {len(monorepos)} ({monorepo_percentage:.1f}% of non-empty repos)\n")
                else:
                    f.write(f"## 📦 Monorepo Analysis\n\n")
                    f.write(f"- **Monorepos Detected:** {len(monorepos)} (N/A% of non-empty repos)\n")
                    
                f.write(f"- **Average LOC in Monorepos:** {sum(s.total_loc for s in monorepos) / len(monorepos):,.0f}\n")
                f.write("\n")
                
                # Top monorepos
                f.write("### Largest Monorepos\n\n")
                top_monorepos = sorted(monorepos, key=lambda x: x.total_loc, reverse=True)[:5]
                for i, stats in enumerate(top_monorepos, 1):
                    f.write(f"{i}. **{stats.name}** - {stats.total_loc:,} LOC\n")
                f.write("\n")
            
            # Commit activity summary
            if non_empty_repos:
                total_commits_last_month = sum(stats.commits_last_month for stats in non_empty_repos)
                total_commits_last_year = sum(stats.commits_last_year for stats in non_empty_repos)
                
                f.write("## 📅 Commit Activity Summary\n\n")
                f.write(f"- **Total Commits (Last Month):** {total_commits_last_month:,}\n")
                f.write(f"- **Total Commits (Last Year):** {total_commits_last_year:,}\n")
                if active_repos > 0:
                    f.write(f"- **Average Monthly Commits per Active Repo:** {total_commits_last_month / active_repos:.1f} (active repos only)\n")
                else:
                    f.write(f"- **Average Monthly Commits per Active Repo:** 0.0 (no active repos found)\n")
                f.write("\n")
        
        logger.info(f"Aggregated report saved to {report_path}")