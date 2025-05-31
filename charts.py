from asyncio.log import logger
from zipfile import Path
from models import RepoStats
from utilities import ensure_utc
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import List, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
from wordcloud import WordCloud
from config import ThemeConfig


class InfrastructureQualityMetricsCreator:
    """Class responsible for creating detailed charts for repository analysis"""
    
    def __init__(self, non_empty_repos: List[RepoStats], chart_colors: List[str], 
                 reports_dir: Path, all_stats: Optional[List[RepoStats]] = None):
        self.non_empty_repos = non_empty_repos
        self.chart_colors = chart_colors
        self.reports_dir = reports_dir
        self.all_stats = all_stats
    
    def create_infrastructure_quality_chart(self) -> None:
        """Create grouped bar chart showing infrastructure quality metrics"""
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Calculate percentages for each metric
        total = len(self.non_empty_repos)
        with_packages = sum(1 for r in self.non_empty_repos if r.has_packages)
        with_deployments = sum(1 for r in self.non_empty_repos if r.has_deployments)
        with_releases = sum(1 for r in self.non_empty_repos if r.has_releases)
        with_cicd = sum(1 for r in self.non_empty_repos if r.has_cicd)
        
        # Create data for grouped bar chart
        categories = ['Package Management', 'Deployment Config', 'Releases', 'CI/CD']
        yes_counts = [with_packages, with_deployments, with_releases, with_cicd]
        no_counts = [total - count for count in yes_counts]
        
        # Plot the data
        x = np.arange(len(categories))
        width = 0.35
        
        # Plot "Yes" bars
        yes_bars = ax.bar(x - width/2, yes_counts, width, label='Yes', color=self.chart_colors[0])
        # Plot "No" bars
        no_bars = ax.bar(x + width/2, no_counts, width, label='No', color=self.chart_colors[1])
        
        # Add counts and percentages
        for i, bars in enumerate([yes_bars, no_bars]):
            _ = "Yes" if i == 0 else "No"
            for _, bar in enumerate(bars):
                height = bar.get_height()
                percentage = (height / total) * 100
                ax.text(bar.get_x() + bar.get_width()/2, height + 0.5,
                       f"{int(height)}\n({percentage:.1f}%)",
                       ha='center', va='bottom', fontsize=9)
        
        # Add labels and title
        ax.set_ylabel('Number of Repositories')
        ax.set_title('Infrastructure Quality Metrics')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        
        # Set y-axis to start at 0
        ax.set_ylim(0, max(yes_counts + no_counts) * 1.15)  # Add 15% padding
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'infrastructure_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_commit_activity_heatmap(self) -> None:
        """Create a heatmap showing commit activity by month and year"""
        # Extract monthly commit data from non-empty repos
        # Group by month and year
        commit_data = defaultdict(int)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for stats in self.non_empty_repos:
            if stats.last_commit_date:
                month = stats.last_commit_date.month - 1  # 0-indexed
                year = stats.last_commit_date.year
                commit_data[(year, month)] += 1
        
        if commit_data:
            # Create data for heatmap
            years = sorted(set(year for year, _ in commit_data.keys()))
            
            if len(years) > 0:
                activity_matrix = []
                for year in years:
                    row = [commit_data.get((year, month), 0) for month in range(12)]
                    activity_matrix.append(row)
                
                _, ax = plt.subplots(figsize=(12, len(years) * 0.8 + 2))
                
                # Create heatmap
                sns.heatmap(activity_matrix, 
                          xticklabels=month_names,
                          yticklabels=years,
                          cmap='YlGnBu',
                          annot=True,
                          fmt='d',
                          cbar_kws={'label': 'Commit Count'})
                
                ax.set_title('Repository Commit Activity by Month')
                ax.set_xlabel('Month')
                ax.set_ylabel('Year')
                
                plt.tight_layout()
                plt.savefig(self.reports_dir / 'commit_activity_heatmap.png', dpi=300, bbox_inches='tight')
                plt.close()
    
    def create_top_repos_by_metrics(self) -> None:
        """Create charts showing top 10 repositories by various metrics"""
        if len(self.non_empty_repos) > 0:
            _, axs = plt.subplots(2, 2, figsize=(16, 12))
            axs = axs.flatten()
            
            # Top 10 by Size (LOC)
            top_by_loc = sorted(self.non_empty_repos, key=lambda x: x.total_loc, reverse=True)[:10]
            names_loc = [r.name for r in top_by_loc]
            locs = [r.total_loc for r in top_by_loc]
            
            axs[0].barh(names_loc, locs, color=self.chart_colors[0])
            axs[0].set_title('Top 10 Repositories by Size (LOC)')
            axs[0].set_xlabel('Lines of Code')
            # Format x-axis labels with commas for thousands
            axs[0].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
            
            # Top 10 by Stars
            top_by_stars = sorted(self.non_empty_repos, key=lambda x: x.stars, reverse=True)[:10]
            names_stars = [r.name for r in top_by_stars]
            stars = [r.stars for r in top_by_stars]
            
            axs[1].barh(names_stars, stars, color=self.chart_colors[1])
            axs[1].set_title('Top 10 Repositories by Stars')
            axs[1].set_xlabel('Stars')
            
            # Top 10 by Maintenance Score
            top_by_maint = sorted(self.non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:10]
            names_maint = [r.name for r in top_by_maint]
            maint_scores = [r.maintenance_score for r in top_by_maint]
            
            axs[2].barh(names_maint, maint_scores, color=self.chart_colors[2])
            axs[2].set_title('Top 10 Repositories by Maintenance Score')
            axs[2].set_xlabel('Maintenance Score')
            
            # Top 10 by Contributors
            top_by_contrib = sorted(self.non_empty_repos, key=lambda x: x.contributors_count, reverse=True)[:10]
            names_contrib = [r.name for r in top_by_contrib]
            contribs = [r.contributors_count for r in top_by_contrib]
            
            axs[3].barh(names_contrib, contribs, color=self.chart_colors[3])
            axs[3].set_title('Top 10 Repositories by Contributors')
            axs[3].set_xlabel('Contributors Count')
            
            plt.tight_layout()
            plt.savefig(self.reports_dir / 'top_repos_metrics.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    def create_metrics_correlation_matrix(self) -> None:
        """Create a correlation matrix heatmap between different repository metrics"""
        if len(self.non_empty_repos) > 5:  # Only do this if we have enough repos for meaningful correlations
            # Extract scores
            maintenance_scores = [r.maintenance_score for r in self.non_empty_repos]
            code_quality_scores = [r.code_quality_score for r in self.non_empty_repos]
            popularity_scores = [r.popularity_score for r in self.non_empty_repos]
            documentation_scores = [r.documentation_score for r in self.non_empty_repos]
            contributor_counts = [r.contributors_count for r in self.non_empty_repos]
            stars_counts = [r.stars for r in self.non_empty_repos]
            issues_counts = [r.open_issues for r in self.non_empty_repos]
            
            # Create correlation dataframe
            import pandas as pd
            corr_data = pd.DataFrame({
                'Maintenance': maintenance_scores,
                'Code Quality': code_quality_scores,
                'Popularity': popularity_scores,
                'Documentation': documentation_scores,
                'Contributors': contributor_counts,
                'Stars': stars_counts,
                'Open Issues': issues_counts
            })
            
            # Calculate correlation
            corr_matrix = corr_data.corr()
            
            # Plot correlation heatmap
            fig, ax = plt.subplots(figsize=(10, 8))
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
            
            sns.heatmap(corr_matrix, mask=mask, cmap='coolwarm', annot=True, 
                      vmin=-1, vmax=1, center=0, square=True, linewidths=.5)
            
            ax.set_title('Correlation Between Repository Metrics')
            
            plt.tight_layout()
            plt.savefig(self.reports_dir / 'metrics_correlation.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    def create_topics_wordcloud(self) -> None:
        """Create a word cloud visualization of repository topics"""
        # Collect all topics
        all_topics = []
        for repo in self.non_empty_repos:
            all_topics.extend(repo.topics)
        
        if all_topics:
            # Create word cloud
            wordcloud = WordCloud(
                width=800, 
                height=400, 
                background_color='white',
                colormap='viridis',
                max_words=100,
                min_font_size=10
            ).generate(' '.join(all_topics))
            
            _, ax = plt.subplots(figsize=(12, 6))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            ax.set_title('Repository Topics WordCloud')
            
            plt.tight_layout()
            plt.savefig(self.reports_dir / 'topics_wordcloud.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    def create_active_inactive_age_distribution(self) -> None:
        """Create histogram comparing age distribution of active vs inactive repositories"""
        _, ax = plt.subplots(figsize=(12, 7))
        
        # Separate active and inactive repos
        active_repos = [r for r in self.non_empty_repos if r.is_active]
        inactive_repos = [r for r in self.non_empty_repos if not r.is_active]
        
        # Calculate ages in years
        active_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in active_repos]
        inactive_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in inactive_repos]
        
        # Create histogram
        if active_ages:
            ax.hist(active_ages, bins=15, alpha=0.7, label='Active', color=self.chart_colors[0])
        if inactive_ages:
            ax.hist(inactive_ages, bins=15, alpha=0.7, label='Inactive', color=self.chart_colors[1])
        
        ax.set_xlabel('Repository Age (Years)')
        ax.set_ylabel('Count')
        ax.set_title('Age Distribution: Active vs Inactive Repositories')
        ax.legend()
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'active_inactive_age.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_stars_vs_issues_scatter(self) -> None:
        """Create scatter plot of repository stars vs open issues"""
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Extract data
        stars = [r.stars for r in self.non_empty_repos]
        issues = [r.open_issues for r in self.non_empty_repos]
        names = [r.name for r in self.non_empty_repos]
        
        # Create scatter plot
        _ = ax.scatter(stars, issues, 
                   c=[self.chart_colors[0] if r.is_active else self.chart_colors[1] for r in self.non_empty_repos],
                   alpha=0.7, s=100)
        
        # Add annotations for repos with many stars or issues
        threshold_stars = np.percentile(stars, 90) if len(stars) > 10 else 0
        threshold_issues = np.percentile(issues, 90) if len(issues) > 10 else 0
        
        for i, (name, s, iss) in enumerate(zip(names, stars, issues)):
            if s > threshold_stars or iss > threshold_issues:
                ax.annotate(name, (s, iss), fontsize=8,
                          xytext=(5, 5), textcoords='offset points')
        
        ax.set_xlabel('Stars')
        ax.set_ylabel('Open Issues')
        ax.set_title('Repository Popularity vs. Maintenance Burden')
        ax.grid(alpha=0.3)
        
        # Add logarithmic scales if the data spans multiple orders of magnitude
        if max(stars) > 100 * min([s for s in stars if s > 0] or [1]):
            ax.set_xscale('log')
        if max(issues) > 100 * min([i for i in issues if i > 0] or [1]):
            ax.set_yscale('log')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'stars_vs_issues.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_repository_creation_timeline(self) -> None:
        """Create timeline showing repository creation over time"""
        if self.all_stats:
            fig, ax = plt.subplots(figsize=(15, 6))
            
            # Extract creation dates
            creation_dates = [ensure_utc(r.created_at) for r in self.all_stats]
            
            # Create histogram by year and month
            years_months = [(d.year, d.month) for d in creation_dates]
            unique_years_months = sorted(set(years_months))
            
            if unique_years_months:
                # Convert to datetime for better plotting
                plot_dates = [datetime(year=ym[0], month=ym[1], day=15) for ym in unique_years_months]
                counts = [years_months.count(ym) for ym in unique_years_months]
                
                # Plot
                ax.bar(plot_dates, counts, width=25, color=self.chart_colors[0], alpha=0.8)
                
                ax.set_xlabel('Date')
                ax.set_ylabel('New Repositories')
                ax.set_title('Repository Creation Timeline')
                
                # Format x-axis as dates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
                ax.xaxis.set_major_locator(mdates.YearLocator())
                plt.xticks(rotation=45)
                
                # Add trend line (moving average)
                if len(counts) > 3:
                    from scipy.ndimage import gaussian_filter1d
                    smoothed = gaussian_filter1d(counts, sigma=1.5)
                    ax.plot(plot_dates, smoothed, 'r-', linewidth=2, alpha=0.7)
                
                ax.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(self.reports_dir / 'repo_creation_timeline.png', dpi=300, bbox_inches='tight')
                plt.close()
    
    def create_documentation_quality_distribution(self) -> None:
        """Create charts showing distribution of documentation and README quality"""
        _, axs = plt.subplots(1, 2, figsize=(16, 7))
        
        # Documentation Size Distribution
        docs_categories = Counter(r.docs_size_category for r in self.non_empty_repos)
        # Sort categories in logical order
        category_order = ["None", "Small", "Intermediate", "Big"]
        docs_data = [docs_categories.get(cat, 0) for cat in category_order]
        
        axs[0].bar(category_order, docs_data, color=self.chart_colors[:len(category_order)])
        axs[0].set_title('Documentation Size Distribution')
        axs[0].set_ylabel('Number of Repositories')
        
        # Add count labels above bars
        for i, count in enumerate(docs_data):
            if count > 0:
                axs[0].text(i, count + 0.5, str(count), ha='center')
        
        # README Comprehensiveness Distribution
        readme_categories = Counter(r.readme_comprehensiveness for r in self.non_empty_repos)
        # Sort categories in logical order
        readme_order = ["None", "Small", "Good", "Comprehensive"]
        readme_data = [readme_categories.get(cat, 0) for cat in readme_order]
        
        axs[1].bar(readme_order, readme_data, color=self.chart_colors[3:3+len(readme_order)])
        axs[1].set_title('README Comprehensiveness Distribution')
        axs[1].set_ylabel('Number of Repositories')
        
        # Add count labels above bars
        for i, count in enumerate(readme_data):
            if count > 0:
                axs[1].text(i, count + 0.5, str(count), ha='center')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'documentation_quality.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_infrastructure_metrics(self) -> None:
        """Create charts showing infrastructure quality metrics"""
        # This is a duplicate of create_infrastructure_quality_chart
        # Keeping it for backward compatibility
        self.create_infrastructure_quality_chart()
    
    def create_release_counts_chart(self) -> None:
        """Create bar chart showing repositories with most releases"""
        repos_with_releases = [r for r in self.non_empty_repos if r.has_releases and r.release_count > 0]
        if len(repos_with_releases) >= 3:  # Only create if we have at least 3 repos with releases
            # Sort by release count
            top_by_releases = sorted(repos_with_releases, key=lambda x: x.release_count, reverse=True)[:15]
            
            # Create horizontal bar chart
            _, ax = plt.subplots(figsize=(12, max(6, len(top_by_releases) * 0.4)))
            
            names = [r.name for r in top_by_releases]
            release_counts = [r.release_count for r in top_by_releases]
            
            # Create horizontal bar chart
            bars = ax.barh(names, release_counts, color=self.chart_colors[2])
            
            # Add count labels
            for bar in bars:
                width = bar.get_width()
                ax.text(width + 0.5, bar.get_y() + bar.get_height()/2,
                       f"{int(width)}", ha='left', va='center')
            
            ax.set_xlabel('Number of Releases')
            ax.set_title('Repositories with Most Releases')
            
            # Adjust layout to fit all repo names
            plt.tight_layout()
            plt.savefig(self.reports_dir / 'release_counts.png', dpi=300, bbox_inches='tight')
            plt.close()


class CreateDetailedCharts:
    """Class responsible for creating detailed charts for the visualization dashboard"""
    
    def __init__(self, all_stats: List[RepoStats], theme: ThemeConfig):
        """Initialize the detailed charts with all repository statistics"""
        self.all_stats = all_stats
        self.theme = theme

    def create(self) -> None:
        """Create additional detailed charts"""
        logger.info("Creating detailed charts")
        
        # Filter out empty repositories for most charts
        empty_repos = [s for s in self.all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in self.all_stats if "Empty repository with no files" not in s.anomalies]
        
        # Use theme colors for consistency
        chart_colors = self.theme["chart_palette"]
        
        # Create all charts
        self._create_repository_timeline()
        self._create_language_evolution(non_empty_repos)
        self._create_maintenance_quality_heatmap(non_empty_repos)
        self._create_empty_vs_nonempty_pie(empty_repos, non_empty_repos)
        self._create_repository_types_distribution()
        self._create_commit_activity_heatmap(non_empty_repos)
        self._create_top_repositories_by_metrics(non_empty_repos, chart_colors)
        self._create_score_correlation_matrix(non_empty_repos)
        self._create_topics_wordcloud(non_empty_repos)
        self._create_active_inactive_age_distribution(non_empty_repos, chart_colors)
        self._create_stars_vs_issues_scatter(non_empty_repos, chart_colors)
        self._create_repository_creation_timeline(chart_colors)
        self._create_documentation_quality_distribution(non_empty_repos, chart_colors)
        self._create_infrastructure_quality_metrics(non_empty_repos, chart_colors)
        self._create_release_counts(non_empty_repos, chart_colors)
        
        logger.info("Detailed charts saved to reports directory")
    
    def _create_repository_timeline(self) -> None:
        """Create repository timeline chart showing creation and last commit dates"""
        _, ax = plt.subplots(figsize=(15, 8))
        
        # Prepare data for timeline
        repo_data = []
        for stats in self.all_stats:  # Include all repos, even empty ones
            # Ensure dates are timezone-aware
            created = ensure_utc(stats.created_at)
            last_commit = ensure_utc(stats.last_commit_date or stats.last_pushed)
            
            # Mark empty repositories differently
            is_empty = "Empty repository with no files" in stats.anomalies
                
            repo_data.append({
                'name': stats.name,
                'created': created,
                'last_commit': last_commit,
                'loc': stats.total_loc,
                'stars': stats.stars,
                'is_active': stats.is_active,
                'is_empty': is_empty
            })
        
        # Sort by creation date
        repo_data.sort(key=lambda x: x['created'])
        
        # Create timeline
        for i, repo in enumerate(repo_data):
            # Use different color/style for empty repositories
            if repo['is_empty']:
                color = 'red'
                alpha = 0.3
                marker = 'x'
            else:
                color = 'green' if repo['is_active'] else 'gray'
                alpha = 0.7 if repo['is_active'] else 0.3
                marker = 'o'
            
            # Plot line from creation to last commit
            ax.plot([repo['created'], repo['last_commit']], [i, i], 
                   color=color, alpha=alpha, linewidth=2)
            
            # Add markers
            ax.scatter(repo['created'], i, color='blue', s=50, alpha=0.7, marker=marker, label='Created' if i == 0 else "")
            ax.scatter(repo['last_commit'], i, color=color, s=repo['stars']*2+20, alpha=alpha, marker=marker)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Repository')
        ax.set_title('Repository Timeline (Creation → Last Commit)')
        ax.grid(True, alpha=0.3)
        
        # Format dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'repository_timeline.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_language_evolution(self, non_empty_repos: List[RepoStats]) -> None:
        """Create language evolution chart showing how language usage has changed over time"""
        if len(non_empty_repos) <= 1:
            return
            
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Group repositories by creation year and analyze language usage
        yearly_languages = defaultdict(lambda: defaultdict(int))
        
        for stats in non_empty_repos:
            # Ensure date is timezone-aware
            created_at = ensure_utc(stats.created_at)
                
            year = created_at.year
            for lang, loc in stats.languages.items():
                yearly_languages[year][lang] += loc
        
        # Get top 5 languages overall
        all_lang_totals = defaultdict(int)
        for year_data in yearly_languages.values():
            for lang, loc in year_data.items():
                all_lang_totals[lang] += loc
        
        top_languages = sorted(all_lang_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        top_lang_names = [lang for lang, _ in top_languages]
        
        # Create stacked area chart
        years = sorted(yearly_languages.keys())
        lang_data = {lang: [] for lang in top_lang_names}
        
        for year in years:
            year_total = sum(yearly_languages[year].values()) or 1
            for lang in top_lang_names:
                percentage = (yearly_languages[year][lang] / year_total) * 100
                lang_data[lang].append(percentage)
        
        # Plot stacked area
        ax.stackplot(years, *[lang_data[lang] for lang in top_lang_names], 
                    labels=top_lang_names, alpha=0.7)
        
        ax.set_xlabel('Year')
        ax.set_ylabel('Percentage of Code (%)')
        ax.set_title('Language Usage Evolution Over Time')
        ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'language_evolution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_maintenance_quality_heatmap(self, non_empty_repos: List[RepoStats]) -> None:
        """Create heatmap showing maintenance quality factors for top repositories"""
        if not non_empty_repos:
            return
            
        _, ax = plt.subplots(figsize=(14, 10))
        
        # Create matrix for heatmap
        quality_factors = ['Has Docs', 'Has Tests', 'Is Active', 'Has License', 'Low Issues']
        
        # Select top repos by maintenance score (non-empty only)
        top_repos = sorted(non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:20]
        repo_names = [stats.name[:20] for stats in top_repos]  # Top 20 repos
        
        quality_matrix = []
        for stats in top_repos:
            row = [
                1 if stats.has_docs else 0,
                1 if stats.has_tests else 0,
                1 if stats.is_active else 0,
                1 if stats.license_name else 0,
                1 if stats.open_issues < 5 else 0
            ]
            quality_matrix.append(row)
        
        if quality_matrix:  # Only create heatmap if we have non-empty repos
            # Create heatmap
            sns.heatmap(quality_matrix, 
                      xticklabels=quality_factors,
                      yticklabels=repo_names,
                      cmap='RdYlGn',
                      annot=True,
                      fmt='d',
                      cbar_kws={'label': 'Quality Score'})
            
            ax.set_title('Repository Maintenance Quality Matrix')
            ax.set_xlabel('Quality Factors')
            ax.set_ylabel('Repositories')
            
            plt.tight_layout()
            plt.savefig(self.reports_dir / 'quality_heatmap.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    def _create_empty_vs_nonempty_pie(self, empty_repos: List[RepoStats], non_empty_repos: List[RepoStats]) -> None:
        """Create pie chart showing empty vs non-empty repository distribution"""
        if not empty_repos:
            return
            
        fig, ax = plt.subplots(figsize=(10, 10))
        labels = ['Non-Empty Repositories', 'Empty Repositories']
        sizes = [len(non_empty_repos), len(empty_repos)]
        colors = ['#66b3ff', '#ff9999']
        
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', 
              startangle=90, shadow=True)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        
        plt.title('Empty vs Non-Empty Repositories')
        plt.savefig(self.reports_dir / 'empty_repos_chart.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_repository_types_distribution(self) -> None:
        """Create chart showing distribution of repository types"""
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Count different repository types
        repo_types = {
            'Regular': sum(1 for s in self.all_stats if not (s.is_fork or s.is_archived or s.is_template)),
            'Forks': sum(1 for s in self.all_stats if s.is_fork),
            'Archived': sum(1 for s in self.all_stats if s.is_archived),
            'Templates': sum(1 for s in self.all_stats if s.is_template),
            'Private': sum(1 for s in self.all_stats if s.is_private),
            'Public': sum(1 for s in self.all_stats if not s.is_private)
        }
        
        # Create bar chart
        bars = ax.bar(repo_types.keys(), repo_types.values(), color=self.theme["chart_palette"][:len(repo_types)])
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}',
                      xy=(bar.get_x() + bar.get_width() / 2, height),
                      xytext=(0, 3),  # 3 points vertical offset
                      textcoords="offset points",
                      ha='center', va='bottom')
        
        ax.set_title('Repository Types Distribution')
        ax.set_ylabel('Count')
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'repo_types_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_commit_activity_heatmap(self, non_empty_repos: List[RepoStats]) -> None:
        """Create heatmap showing commit activity by month and year"""
        if not non_empty_repos:
            return
            
        # Extract monthly commit data from non-empty repos
        # Group by month and year
        commit_data = defaultdict(int)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for stats in non_empty_repos:
            if stats.last_commit_date:
                month = stats.last_commit_date.month - 1  # 0-indexed
                year = stats.last_commit_date.year
                commit_data[(year, month)] += 1
        
        if not commit_data:
            return
            
        # Create data for heatmap
        years = sorted(set(year for year, _ in commit_data.keys()))
        
        if not years:
            return
            
        activity_matrix = []
        for year in years:
            row = [commit_data.get((year, month), 0) for month in range(12)]
            activity_matrix.append(row)
        
        _, ax = plt.subplots(figsize=(12, len(years) * 0.8 + 2))
        
        # Create heatmap
        sns.heatmap(activity_matrix, 
                  xticklabels=month_names,
                  yticklabels=years,
                  cmap='YlGnBu',
                  annot=True,
                  fmt='d',
                  cbar_kws={'label': 'Commit Count'})
        
        ax.set_title('Repository Commit Activity by Month')
        ax.set_xlabel('Month')
        ax.set_ylabel('Year')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'commit_activity_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_top_repositories_by_metrics(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create charts showing top repositories by various metrics"""
        if not non_empty_repos:
            return
            
        _, axs = plt.subplots(2, 2, figsize=(16, 12))
        axs = axs.flatten()
        
        # Top 10 by Size (LOC)
        top_by_loc = sorted(non_empty_repos, key=lambda x: x.total_loc, reverse=True)[:10]
        names_loc = [r.name for r in top_by_loc]
        locs = [r.total_loc for r in top_by_loc]
        
        axs[0].barh(names_loc, locs, color=chart_colors[0])
        axs[0].set_title('Top 10 Repositories by Size (LOC)')
        axs[0].set_xlabel('Lines of Code')
        # Format x-axis labels with commas for thousands
        axs[0].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))
        
        # Top 10 by Stars
        top_by_stars = sorted(non_empty_repos, key=lambda x: x.stars, reverse=True)[:10]
        names_stars = [r.name for r in top_by_stars]
        stars = [r.stars for r in top_by_stars]
        
        axs[1].barh(names_stars, stars, color=chart_colors[1])
        axs[1].set_title('Top 10 Repositories by Stars')
        axs[1].set_xlabel('Stars')
        
        # Top 10 by Maintenance Score
        top_by_maint = sorted(non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:10]
        names_maint = [r.name for r in top_by_maint]
        maint_scores = [r.maintenance_score for r in top_by_maint]
        
        axs[2].barh(names_maint, maint_scores, color=chart_colors[2])
        axs[2].set_title('Top 10 Repositories by Maintenance Score')
        axs[2].set_xlabel('Maintenance Score')
        
        # Top 10 by Contributors
        top_by_contrib = sorted(non_empty_repos, key=lambda x: x.contributors_count, reverse=True)[:10]
        names_contrib = [r.name for r in top_by_contrib]
        contribs = [r.contributors_count for r in top_by_contrib]
        
        axs[3].barh(names_contrib, contribs, color=chart_colors[3])
        axs[3].set_title('Top 10 Repositories by Contributors')
        axs[3].set_xlabel('Contributors Count')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'top_repos_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_score_correlation_matrix(self, non_empty_repos: List[RepoStats]) -> None:
        """Create correlation matrix showing relationships between repository metrics"""
        if len(non_empty_repos) <= 5:  # Only do this if we have enough repos for meaningful correlations
            return
            
        # Extract scores
        maintenance_scores = [r.maintenance_score for r in non_empty_repos]
        code_quality_scores = [r.code_quality_score for r in non_empty_repos]
        popularity_scores = [r.popularity_score for r in non_empty_repos]
        documentation_scores = [r.documentation_score for r in non_empty_repos]
        contributor_counts = [r.contributors_count for r in non_empty_repos]
        stars_counts = [r.stars for r in non_empty_repos]
        issues_counts = [r.open_issues for r in non_empty_repos]
        
        # Create correlation dataframe
        import pandas as pd
        corr_data = pd.DataFrame({
            'Maintenance': maintenance_scores,
            'Code Quality': code_quality_scores,
            'Popularity': popularity_scores,
            'Documentation': documentation_scores,
            'Contributors': contributor_counts,
            'Stars': stars_counts,
            'Open Issues': issues_counts
        })
        
        # Calculate correlation
        corr_matrix = corr_data.corr()
        
        # Plot correlation heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        
        sns.heatmap(corr_matrix, mask=mask, cmap='coolwarm', annot=True, 
                  vmin=-1, vmax=1, center=0, square=True, linewidths=.5)
        
        ax.set_title('Correlation Between Repository Metrics')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'metrics_correlation.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_topics_wordcloud(self, non_empty_repos: List[RepoStats]) -> None:
        """Create word cloud visualization of repository topics"""
        if not non_empty_repos:
            return
            
        # Collect all topics
        all_topics = []
        for repo in non_empty_repos:
            all_topics.extend(repo.topics)
        
        if not all_topics:
            return
            
        # Create word cloud
        wordcloud = WordCloud(
            width=800, 
            height=400, 
            background_color='white',
            colormap='viridis',
            max_words=100,
            min_font_size=10
        ).generate(' '.join(all_topics))
        
        _, ax = plt.subplots(figsize=(12, 6))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        ax.set_title('Repository Topics WordCloud')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'topics_wordcloud.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_active_inactive_age_distribution(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create histogram showing age distribution of active vs inactive repositories"""
        if not non_empty_repos:
            return
            
        _, ax = plt.subplots(figsize=(12, 7))
        
        # Separate active and inactive repos
        active_repos = [r for r in non_empty_repos if r.is_active]
        inactive_repos = [r for r in non_empty_repos if not r.is_active]
        
        # Calculate ages in years
        active_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in active_repos]
        inactive_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in inactive_repos]
        
        # Create histogram
        if active_ages:
            ax.hist(active_ages, bins=15, alpha=0.7, label='Active', color=chart_colors[0])
        if inactive_ages:
            ax.hist(inactive_ages, bins=15, alpha=0.7, label='Inactive', color=chart_colors[1])
        
        ax.set_xlabel('Repository Age (Years)')
        ax.set_ylabel('Count')
        ax.set_title('Age Distribution: Active vs Inactive Repositories')
        ax.legend()
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'active_inactive_age.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_stars_vs_issues_scatter(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create scatter plot showing relationship between stars and open issues"""
        if not non_empty_repos:
            return
            
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Extract data
        stars = [r.stars for r in non_empty_repos]
        issues = [r.open_issues for r in non_empty_repos]
        names = [r.name for r in non_empty_repos]
        
        # Create scatter plot
        _ = ax.scatter(stars, issues, 
                   c=[chart_colors[0] if r.is_active else chart_colors[1] for r in non_empty_repos],
                   alpha=0.7, s=100)
        
        # Add annotations for repos with many stars or issues
        threshold_stars = np.percentile(stars, 90) if len(stars) > 10 else 0
        threshold_issues = np.percentile(issues, 90) if len(issues) > 10 else 0
        
        for i, (name, s, iss) in enumerate(zip(names, stars, issues)):
            if s > threshold_stars or iss > threshold_issues:
                ax.annotate(name, (s, iss), fontsize=8,
                          xytext=(5, 5), textcoords='offset points')
        
        ax.set_xlabel('Stars')
        ax.set_ylabel('Open Issues')
        ax.set_title('Repository Popularity vs. Maintenance Burden')
        ax.grid(alpha=0.3)
        
        # Add logarithmic scales if the data spans multiple orders of magnitude
        if max(stars) > 100 * min([s for s in stars if s > 0] or [1]):
            ax.set_xscale('log')
        if max(issues) > 100 * min([i for i in issues if i > 0] or [1]):
            ax.set_yscale('log')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'stars_vs_issues.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_repository_creation_timeline(self, chart_colors: List[str]) -> None:
        """Create timeline showing repository creation over time"""
        if not self.all_stats:
            return
            
        fig, ax = plt.subplots(figsize=(15, 6))
        
        # Extract creation dates
        creation_dates = [ensure_utc(r.created_at) for r in self.all_stats]
        
        # Create histogram by year and month
        years_months = [(d.year, d.month) for d in creation_dates]
        unique_years_months = sorted(set(years_months))
        
        if not unique_years_months:
            return
            
        # Convert to datetime for better plotting
        plot_dates = [datetime(year=ym[0], month=ym[1], day=15) for ym in unique_years_months]
        counts = [years_months.count(ym) for ym in unique_years_months]
        
        # Plot
        ax.bar(plot_dates, counts, width=25, color=chart_colors[0], alpha=0.8)
        
        ax.set_xlabel('Date')
        ax.set_ylabel('New Repositories')
        ax.set_title('Repository Creation Timeline')
        
        # Format x-axis as dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        # Add trend line (moving average)
        if len(counts) > 3:
            from scipy.ndimage import gaussian_filter1d
            smoothed = gaussian_filter1d(counts, sigma=1.5)
            ax.plot(plot_dates, smoothed, 'r-', linewidth=2, alpha=0.7)
        
        ax.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'repo_creation_timeline.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_documentation_quality_distribution(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create charts showing distribution of documentation and README quality"""
        if not non_empty_repos:
            return
            
        _, axs = plt.subplots(1, 2, figsize=(16, 7))
        
        # Documentation Size Distribution
        docs_categories = Counter(r.docs_size_category for r in non_empty_repos)
        # Sort categories in logical order
        category_order = ["None", "Small", "Intermediate", "Big"]
        docs_data = [docs_categories.get(cat, 0) for cat in category_order]
        
        axs[0].bar(category_order, docs_data, color=chart_colors[:len(category_order)])
        axs[0].set_title('Documentation Size Distribution')
        axs[0].set_ylabel('Number of Repositories')
        
        # Add count labels above bars
        for i, count in enumerate(docs_data):
            if count > 0:
                axs[0].text(i, count + 0.5, str(count), ha='center')
        
        # README Comprehensiveness Distribution
        readme_categories = Counter(r.readme_comprehensiveness for r in non_empty_repos)
        # Sort categories in logical order
        readme_order = ["None", "Small", "Good", "Comprehensive"]
        readme_data = [readme_categories.get(cat, 0) for cat in readme_order]
        
        axs[1].bar(readme_order, readme_data, color=chart_colors[3:3+len(readme_order)])
        axs[1].set_title('README Comprehensiveness Distribution')
        axs[1].set_ylabel('Number of Repositories')
        
        # Add count labels above bars
        for i, count in enumerate(readme_data):
            if count > 0:
                axs[1].text(i, count + 0.5, str(count), ha='center')
        
        plt.tight_layout()
        plt.savefig(self.reports_dir / 'documentation_quality.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_infrastructure_quality_metrics(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create charts for infrastructure quality and other detailed metrics"""
        if not non_empty_repos:
            return
            
        # Create individual metric charts using the DetailedChartCreator class
        chart_creator = InfrastructureQualityMetricsCreator(non_empty_repos, chart_colors, self.reports_dir, self.all_stats)
        
        # Generate all the detailed charts
        chart_creator.create_infrastructure_quality_chart()
        chart_creator.create_commit_activity_heatmap()
        chart_creator.create_top_repos_by_metrics()
        chart_creator.create_metrics_correlation_matrix()
        chart_creator.create_topics_wordcloud()
        chart_creator.create_active_inactive_age_distribution()
        chart_creator.create_stars_vs_issues_scatter()
        chart_creator.create_repository_creation_timeline()
        chart_creator.create_documentation_quality_distribution()
        chart_creator.create_infrastructure_metrics()
        chart_creator.create_release_counts_chart()
        
        logger.info("Detailed charts saved to reports directory")
                        
        
