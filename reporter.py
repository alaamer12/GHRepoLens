from asyncio.log import logger
from zipfile import Path
from models import RepoStats
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import List


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
            active_repos_sorted = sorted([s for s in all_stats if s.is_active and "Empty repository with no files" not in s.anomalies], 
                                       key=lambda x: x.last_commit_date, reverse=True)[:10]
            for i, stats in enumerate(active_repos_sorted, 1):
                f.write(f"{i}. **{stats.name}** - Last commit: {stats.last_commit_date.strftime('%Y-%m-%d')}\n")
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
                f.write(f"- **Has Tests:** {'✅ Yes' if stats.has_tests else '❌ No'}\n")
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
                f.write("\n")
                
                f.write("---\n\n")
        
        logger.info(f"Detailed report saved to {report_path}")

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
        
        # Language statistics
        all_languages = defaultdict(int)
        for stats in non_empty_repos:
            for lang, loc in stats.languages.items():
                all_languages[lang] += loc
        
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
            if all_languages:
                sorted_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)
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
            f.write(f"- **Repositories with Documentation:** {repos_with_docs} ({repos_with_docs/non_empty_count*100:.1f}% of non-empty)\n")
            f.write(f"- **Repositories with Tests:** {repos_with_tests} ({repos_with_tests/non_empty_count*100:.1f}% of non-empty)\n")
            f.write(f"- **Active Repositories:** {active_repos} ({active_repos/non_empty_count*100:.1f}% of non-empty)\n")
            f.write(f"- **Repositories with License:** {len(license_counts)} ({len(license_counts)/total_repos*100:.1f}%)\n")
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
                    percentage = (count / total_repos * 100)
                    f.write(f"| {license_name} | {count} | {percentage:.1f}% |\n")
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
        
        logger.info(f"Aggregated report saved to {report_path}")