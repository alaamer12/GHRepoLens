from asyncio.log import logger
from urllib import request
from zipfile import Path

from main import BINARY_EXTENSIONS, CICD_FILES, CONFIG_FILES, DEFAULT_CONFIG, EXCLUDED_DIRECTORIES, LANGUAGE_EXTENSIONS
from models import RepoStats
from utilities import Checkpoint, GitHubRateDisplay, ensure_utc
import json
import time
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from typing import Dict, List, Any
import concurrent.futures

from github import Github
from github.Repository import Repository
from github.GithubException import GithubException, RateLimitExceededException
from tqdm.auto import tqdm
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class GithubVisualizer:
    """Class responsible for creating visualizations from GitHub repository data"""
    
    def __init__(self, username: str, reports_dir: Path):
        """Initialize the visualizer with username and reports directory"""
        self.username = username
        self.reports_dir = reports_dir
    
    def create_visualizations(self, all_stats: List[RepoStats]) -> None:
        """Generate visual reports with charts and graphs"""
        logger.info("Generating visual report")
        
        # Filter out empty repositories for most visualizations
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
        
        # Set style for matplotlib
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Create subplots for different visualizations
        fig = make_subplots(
            rows=4, cols=2,
            subplot_titles=[
                'Top 10 Languages by LOC',
                'Repository Size Distribution',
                'File Type Distribution',
                'Activity Timeline',
                'Stars vs LOC Correlation',
                'Maintenance Score Distribution',
                'Repository Age Distribution',
                'Quality Metrics Overview'
            ],
            specs=[
                [{"type": "bar"}, {"type": "histogram"}],
                [{"type": "pie"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "histogram"}],
                [{"type": "bar"}, {"type": "bar"}]
            ]
        )
        
        # 1. Top 10 Languages by LOC
        all_languages = defaultdict(int)
        for stats in non_empty_repos:
            for lang, loc in stats.languages.items():
                all_languages[lang] += loc
        
        if all_languages:
            top_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)[:10]
            langs, locs = zip(*top_languages)
            
            fig.add_trace(
                go.Bar(x=list(langs), y=list(locs), name="Languages"),
                row=1, col=1
            )
        
        # 2. Repository Size Distribution
        repo_sizes = [stats.total_loc for stats in non_empty_repos if stats.total_loc > 0]
        if repo_sizes:
            fig.add_trace(
                go.Histogram(x=repo_sizes, nbinsx=20, name="Repo Sizes"),
                row=1, col=2
            )
        
        # 3. File Type Distribution (Top 10)
        all_file_types = defaultdict(int)
        for stats in non_empty_repos:
            for file_type, count in stats.file_types.items():
                all_file_types[file_type] += count
        
        if all_file_types:
            top_file_types = sorted(all_file_types.items(), key=lambda x: x[1], reverse=True)[:10]
            types, counts = zip(*top_file_types)
            
            fig.add_trace(
                go.Pie(labels=list(types), values=list(counts), name="File Types"),
                row=2, col=1
            )
        
        # 4. Activity Timeline (commits per month)
        commit_dates = [stats.last_commit_date for stats in non_empty_repos if stats.last_commit_date]
        if commit_dates:
            # Group by month
            monthly_commits = defaultdict(int)
            for date in commit_dates:
                month_key = date.strftime('%Y-%m')
                monthly_commits[month_key] += 1
            
            # Get last 12 months
            sorted_months = sorted(monthly_commits.items())[-12:]
            if sorted_months:
                months, commit_counts = zip(*sorted_months)
                
                fig.add_trace(
                    go.Scatter(x=list(months), y=list(commit_counts), 
                             mode='lines+markers', name="Activity"),
                    row=2, col=2
                )
        
        # 5. Stars vs LOC Correlation
        stars = [stats.stars for stats in non_empty_repos]
        locs = [stats.total_loc for stats in non_empty_repos]
        names = [stats.name for stats in non_empty_repos]
        
        fig.add_trace(
            go.Scatter(x=locs, y=stars, mode='markers',
                      text=names, name="Repos",
                      hovertemplate='<b>%{text}</b><br>LOC: %{x}<br>Stars: %{y}'),
            row=3, col=1
        )
        
        # 6. Maintenance Score Distribution
        maintenance_scores = [stats.maintenance_score for stats in non_empty_repos]
        if maintenance_scores:
            fig.add_trace(
                go.Histogram(x=maintenance_scores, nbinsx=20, name="Maintenance Scores"),
                row=3, col=2
            )
        
        # 7. Repository Age Distribution
        ages = [(datetime.now().replace(tzinfo=timezone.utc) - stats.created_at).days / 365.25 for stats in non_empty_repos]
        if ages:
            fig.add_trace(
                go.Histogram(x=ages, nbinsx=15, name="Repository Ages (Years)"),
                row=4, col=1
            )
        
        # 8. Quality Metrics Overview
        quality_metrics = {
            'Has Documentation': sum(1 for s in non_empty_repos if s.has_docs),
            'Has Tests': sum(1 for s in non_empty_repos if s.has_tests),
            'Is Active': sum(1 for s in non_empty_repos if s.is_active),
            'Has License': sum(1 for s in non_empty_repos if s.license_name),
        }
        
        fig.add_trace(
            go.Bar(x=list(quality_metrics.keys()), y=list(quality_metrics.values()),
                   name="Quality Metrics"),
            row=4, col=2
        )
        
        # Update layout
        fig.update_layout(
            height=2000,
            title_text=f"📊 GitHub Repository Analysis Dashboard - {self.username}",
            title_x=0.5,
            showlegend=False,
            template="plotly_white"
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Language", row=1, col=1)
        fig.update_yaxes(title_text="Lines of Code", row=1, col=1)
        
        fig.update_xaxes(title_text="Lines of Code", row=1, col=2)
        fig.update_yaxes(title_text="Count", row=1, col=2)
        
        fig.update_xaxes(title_text="Month", row=2, col=2)
        fig.update_yaxes(title_text="Commits", row=2, col=2)
        
        fig.update_xaxes(title_text="Lines of Code", row=3, col=1)
        fig.update_yaxes(title_text="Stars", row=3, col=1)
        
        fig.update_xaxes(title_text="Maintenance Score", row=3, col=2)
        fig.update_yaxes(title_text="Count", row=3, col=2)
        
        fig.update_xaxes(title_text="Age (Years)", row=4, col=1)
        fig.update_yaxes(title_text="Count", row=4, col=1)
        
        fig.update_xaxes(title_text="Quality Metric", row=4, col=2)
        fig.update_yaxes(title_text="Count", row=4, col=2)
        
        # Save as interactive HTML
        report_path = self.reports_dir / "visual_report.html"
        
        # Create HTML with custom styling and interactivity
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GitHub Repository Analysis Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.5em;
                    font-weight: 300;
                }}
                .header p {{
                    margin: 10px 0 0 0;
                    opacity: 0.9;
                    font-size: 1.1em;
                }}
                .content {{
                    padding: 30px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    border-left: 4px solid #667eea;
                }}
                .stat-number {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 5px;
                }}
                .stat-label {{
                    color: #666;
                    font-size: 0.9em;
                }}
                .chart-container {{
                    margin: 20px 0;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 10px;
                }}
                .theme-toggle {{
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: rgba(255,255,255,0.2);
                    color: white;
                    border: 2px solid rgba(255,255,255,0.3);
                    padding: 10px 15px;
                    border-radius: 25px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                .theme-toggle:hover {{
                    background: rgba(255,255,255,0.3);
                }}
                @media (prefers-color-scheme: dark) {{
                    .dark-theme .container {{
                        background: #1a1a1a;
                        color: white;
                    }}
                    .dark-theme .stat-card,
                    .dark-theme .chart-container {{
                        background: #2d2d2d;
                        color: white;
                    }}
                }}
            </style>
        </head>
        <body>
            <button class="theme-toggle" onclick="toggleTheme()">🌙 Dark Mode</button>
            <div class="container">
                <div class="header">
                    <h1>📊 GitHub Repository Analysis</h1>
                    <p>User: {self.username} | Generated: {datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                <div class="content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">{len(non_empty_repos)}</div>
                            <div class="stat-label">Total Repositories</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(s.total_loc for s in non_empty_repos):,}</div>
                            <div class="stat-label">Total Lines of Code</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(s.stars for s in non_empty_repos):,}</div>
                            <div class="stat-label">Total Stars</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(1 for s in non_empty_repos if s.is_active)}</div>
                            <div class="stat-label">Active Repositories</div>
                        </div>
                    </div>
                    <div class="chart-container">
                        <div id="main-dashboard"></div>
                    </div>
                </div>
            </div>
            
            <script>
                // Plot the main dashboard
                var plotData = {fig.to_json()};
                Plotly.newPlot('main-dashboard', plotData.data, plotData.layout, {{responsive: true}});
                
                // Theme toggle functionality
                function toggleTheme() {{
                    document.body.classList.toggle('dark-theme');
                    const button = document.querySelector('.theme-toggle');
                    if (document.body.classList.contains('dark-theme')) {{
                        button.innerHTML = '☀️ Light Mode';
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': '#1a1a1a',
                            'plot_bgcolor': '#1a1a1a',
                            'font.color': 'white'
                        }});
                    }} else {{
                        button.innerHTML = '🌙 Dark Mode';
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': 'white',
                            'plot_bgcolor': 'white',
                            'font.color': 'black'
                        }});
                    }}
                }}
                
                // Add hover effects and animations
                document.querySelectorAll('.stat-card').forEach(card => {{
                    card.addEventListener('mouseenter', function() {{
                        this.style.transform = 'translateY(-5px)';
                        this.style.boxShadow = '0 10px 20px rgba(0,0,0,0.1)';
                        this.style.transition = 'all 0.3s ease';
                    }});
                    
                    card.addEventListener('mouseleave', function() {{
                        this.style.transform = 'translateY(0)';
                        this.style.boxShadow = 'none';
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Visual report saved to {report_path}")
        
        # Also create individual static charts for detailed analysis
        self.create_detailed_charts(all_stats)

    def create_detailed_charts(self, all_stats: List[RepoStats]) -> None:
        """Create additional detailed charts"""
        logger.info("Creating detailed charts")
        
        # Filter out empty repositories for most charts
        empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
        
        # 1. Repository Timeline Chart
        fig, ax = plt.subplots(figsize=(15, 8))
        
        # Prepare data for timeline
        repo_data = []
        for stats in all_stats:  # Include all repos, even empty ones
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
        
        # 2. Language Evolution Chart
        if len(non_empty_repos) > 1:
            fig, ax = plt.subplots(figsize=(12, 8))
            
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
        
        # 3. Maintenance Quality Heatmap (only for non-empty repos)
        fig, ax = plt.subplots(figsize=(14, 10))
        
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
        
        # 4. Empty vs Non-Empty Repository Pie Chart
        if len(empty_repos) > 0:
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
        
        logger.info("Detailed charts saved to reports directory")


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


class GithubLens:
    """Main analyzer class for GitHub repositories with comprehensive analysis capabilities"""
    
    def __init__(self, token: str, username: str, config: Dict[str, Any] = None):
        """Initialize the analyzer with GitHub token and configuration"""
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
            
        # Configure custom GitHub client with backoff visualization
        self.setup_github_client(token)
        self.username = username
        self.user = None
        self.session = request.Session()
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
        self.analyzed_repos = []
        
        # Initialize rate display for interactive display
        self.rate_display = GitHubRateDisplay()
        
        # Create analyzer instance
        self.analyzer = GithubAnalyzer(self.github, username, self.config)
        # Set rate display for analyzer
        self.analyzer.rate_display = self.rate_display
        self.analyzer.checkpoint = self.checkpoint
        
        logger.info(f"Initialized analyzer for user: {username}")
        
    def start_monitoring(self, update_interval=30):
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
            
    def stop_monitoring(self):
        """Stop continuous rate monitoring"""
        try:
            self.rate_display.stop()
            logger.info("Stopped continuous rate monitoring")
            return True
        except Exception as e:
            logger.error(f"Error stopping continuous rate monitoring: {e}")
            return False

    def setup_github_client(self, token: str):
        """Set up GitHub client with custom backoff handling to show progress bars"""
        try:
            self.github = Github(token)
        except Exception as e:
            logger.error(f"Error setting up GitHub client: {e}")
            raise

    def analyze_single_repository(self, repo: Repository) -> RepoStats:
        """Analyze a single repository using the GithubAnalyzer"""
        # Pass to the analyzer instance
        return self.analyzer.analyze_single_repository(repo)

    def analyze_all_repositories(self) -> List[RepoStats]:
        """Analyze all repositories for the user"""
        # Delegate to the analyzer instance
        return self.analyzer.analyze_all_repositories()

    def generate_detailed_report(self, all_stats: List[RepoStats]) -> None:
        """Generate detailed per-repository report"""
        reporter = GithubReporter(self.username, self.reports_dir)
        reporter.generate_detailed_report(all_stats)

    def generate_aggregated_report(self, all_stats: List[RepoStats]) -> None:
        """Generate aggregated statistics report"""
        reporter = GithubReporter(self.username, self.reports_dir)
        reporter.generate_aggregated_report(all_stats)
        
    def create_visualizations(self, all_stats: List[RepoStats]) -> None:
        """Generate visual reports with charts and graphs"""
        logger.info("Generating visual report")
        visualizer = GithubVisualizer(self.username, self.reports_dir)
        visualizer.create_visualizations(all_stats)

    def save_json_report(self, all_stats: List[RepoStats]) -> None:
        """Save data as JSON for programmatic consumption"""
        exporter = GithubExporter(self.username, self.reports_dir)
        exporter.save_json_report(all_stats)


class GithubExporter:
    """Class responsible for exporting GitHub repository data to various formats"""
    
    def __init__(self, username: str, reports_dir: Path):
        """Initialize the exporter with username and reports directory"""
        self.username = username
        self.reports_dir = reports_dir
    
    def save_json_report(self, all_stats: List[RepoStats]) -> None:
        """Save data as JSON for programmatic consumption"""
        logger.info("Saving JSON report")
        
        # Count empty repositories
        empty_repos = [s for s in all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in all_stats if "Empty repository with no files" not in s.anomalies]
        
        # Custom JSON encoder for datetime objects
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    # Ensure the datetime has timezone info before serialization
                    if obj.tzinfo is None:
                        obj = obj.replace(tzinfo=timezone.utc)
                    return obj.isoformat()
                return super().default(obj)
        
        # Convert RepoStats to dictionaries with field-by-field error handling
        repo_dicts = []
        for stats in all_stats:
            try:
                # Manual conversion instead of using asdict to avoid serialization issues
                repo_dict = {}
                
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


class GithubAnalyzer:
    """Class responsible for analyzing GitHub repositories"""
    
    def __init__(self, github, username: str, config: Dict[str, Any] = None):
        """Initialize the analyzer with GitHub client, username and configuration"""
        self.github = github
        self.username = username
        self.config = config
        self.rate_display = None
        self.session = None
        self.user = None
        self.checkpoint = None
        self.max_workers = self.config.get("MAX_WORKERS", 1) if self.config else 1

    def check_rate_limit(self) -> None:
        """Check GitHub API rate limit and wait if necessary"""
        try:
            # Get rate data from API
            rate_limit = self.github.get_rate_limit()
            remaining = rate_limit.core.remaining
            reset_time = rate_limit.core.reset
            
            if remaining < 100:  # Low on remaining requests
                # Check if we need to wait
                wait_time = (reset_time - datetime.now().replace(tzinfo=timezone.utc)).total_seconds()
                if wait_time > 0:
                    logger.warning(f"GitHub API rate limit low ({remaining} left). Waiting {wait_time:.1f}s until reset.")
                    self._visualize_wait(wait_time, "Rate limit cooldown")
        except Exception as e:
            logger.warning(f"Could not check rate limit: {e}")
            
    def _visualize_wait(self, wait_time: float, desc: str):
        """Display a progress bar for wait periods"""
        # Cap very long waits to show reasonable progress
        if wait_time > 3600:  # If more than an hour
            logger.warning(f"Long wait time detected ({wait_time:.1f}s). Showing progress for first hour.")
            print(f"⚠️ GitHub API requires a long cooldown period ({wait_time/60:.1f} minutes)")
            print(f"The script will automatically continue after the wait period.")
            wait_time = 3600  # Cap to 1 hour for the progress bar
        
        # Show progress bar for the wait
        wait_seconds = int(wait_time)
        for _ in tqdm(range(wait_seconds), desc=desc, colour="yellow", leave=True):
            time.sleep(1)

    def analyze_all_repositories(self) -> List[RepoStats]:
        """Analyze all repositories for the user"""
        logger.info(f"Starting analysis of all repositories for {self.username}")
        
        all_stats = []
        analyzed_repo_names = []
        repos_to_analyze = []
        last_rate_display = 0  # Track when we last displayed the rate usage
        
        try:
            # Check for existing checkpoint
            checkpoint_data = self.load_checkpoint()
            
            # If checkpoint exists and resume is enabled, load the checkpoint data
            if checkpoint_data:
                all_stats = checkpoint_data.get('all_stats', [])
                analyzed_repo_names = checkpoint_data.get('analyzed_repos', [])
                logger.info(f"Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
                print(f"📋 Resuming analysis from checkpoint with {len(all_stats)} already analyzed repositories")
            
            # Initialize GitHub user with rate limit check
            self.check_rate_limit()
            self.user = self.github.get_user(self.username)
            
            # Get all repositories
            all_repos = list(self.user.get_repos())
            
            # Apply filters based on configuration
            for repo in all_repos:
                # Skip already analyzed repos from checkpoint
                if repo.name in analyzed_repo_names:
                    logger.debug(f"Skipping previously analyzed repo from checkpoint: {repo.name}")
                    continue
                    
                # Apply filters
                if self.config["SKIP_FORKS"] and repo.fork:
                    logger.info(f"Skipping fork: {repo.name}")
                    continue
                    
                if self.config["SKIP_ARCHIVED"] and repo.archived:
                    logger.info(f"Skipping archived repo: {repo.name}")
                    continue
                    
                if not self.config["INCLUDE_PRIVATE"] and repo.private:
                    logger.info(f"Skipping private repo: {repo.name}")
                    continue
                    
                repos_to_analyze.append(repo)
            
            # Report on repos    
            logger.info(f"Found {len(repos_to_analyze)} repositories to analyze after filtering")
            if analyzed_repo_names:
                logger.info(f"Skipping {len(analyzed_repo_names)} already analyzed repositories from checkpoint")
            
            if not repos_to_analyze and not all_stats:
                logger.warning("No repositories found matching the criteria")
                return []
                
            if not repos_to_analyze and all_stats:
                logger.info("All repositories have already been analyzed according to checkpoint")
                return all_stats
                
            # Track newly analyzed repositories in this session
            newly_analyzed_repos = []
            
            # For progress bar display, accurate counts including checkpoint
            total_repos = len(repos_to_analyze) + len(all_stats)
            
            # Display initial rate limit usage before starting
            print("\n--- Initial API Rate Status ---")
            self.rate_display.display_once()  # Use our interactive display
            print("-------------------------------")
            
            # Use parallel processing if configured with multiple workers
            if self.max_workers > 1 and len(repos_to_analyze) > 1:
                logger.info(f"Using parallel processing with {self.max_workers} workers")
                
                with tqdm(total=total_repos, initial=len(all_stats),
                        desc="Analyzing repositories", leave=True, colour='green') as pbar:
                    
                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")
                        
                    # Process repos in smaller batches to allow for checkpointing
                    remaining_repos = repos_to_analyze.copy()
                    batch_size = min(20, len(remaining_repos))  # Process in batches of 20 or fewer
                    repo_counter = 0  # Counter to track repository processing
                    
                    while remaining_repos:
                        repo_counter += 1
                        # Take the next batch
                        batch = remaining_repos[:batch_size]
                        remaining_repos = remaining_repos[batch_size:]
                        
                        # Periodically show rate limit status (every 5 repos or after a batch)
                        if repo_counter % 5 == 0 or repo_counter == 1 or len(batch) == batch_size:
                            print("\n--- Current API Rate Status ---")
                            self.rate_display.display_once()  # Use our interactive display
                            print("-------------------------------")
                        
                        # Check if we need to checkpoint before processing this batch
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in newly_analyzed_repos], 
                                                            remaining_repos + batch):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                            # Submit all tasks for this batch
                            future_to_repo = {
                                executor.submit(self.analyze_single_repository, repo): repo 
                                for repo in batch
                            }
                            
                            # Process results
                            for future in concurrent.futures.as_completed(future_to_repo):
                                repo = future_to_repo[future]
                                try:
                                    stats = future.result()
                                    all_stats.append(stats)
                                    newly_analyzed_repos.append(repo)
                                    analyzed_repo_names.append(repo.name)
                                    pbar.update(1)
                                except Exception as e:
                                    logger.error(f"Failed to analyze {repo.name}: {e}")
            else:
                # Sequential processing with progress bar
                with tqdm(total=total_repos, initial=len(all_stats),
                        desc="Analyzing repositories", leave=True, colour='green') as pbar:
                    
                    # Update progress bar for already analyzed repos from checkpoint
                    if all_stats:
                        pbar.set_description(f"Analyzing repositories (resumed from checkpoint)")
                    
                    # Process remaining repositories
                    remaining_repos = repos_to_analyze.copy()
                    repo_counter = 0  # Counter to track repository processing
                    
                    while remaining_repos:
                        repo_counter += 1
                        repo = remaining_repos.pop(0)
                        
                        # Periodically show rate limit status (every 5 repos)
                        if repo_counter % 5 == 0 or repo_counter == 1:
                            print("\n--- Current API Rate Status ---")
                            self.rate_display.display_once()  # Use our interactive display
                            print("-------------------------------")
                        
                        # Check if we need to checkpoint
                        if self.check_rate_limit_and_checkpoint(all_stats, analyzed_repo_names + [r.name for r in newly_analyzed_repos], 
                                                            remaining_repos + [repo]):
                            logger.info("Stopping analysis due to approaching API rate limit")
                            return all_stats
                        
                        try:
                            stats = self.analyze_single_repository(repo)
                            all_stats.append(stats)
                            newly_analyzed_repos.append(repo)
                            analyzed_repo_names.append(repo.name)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Failed to analyze {repo.name}: {e}")
                            continue
            
            # Analysis completed successfully - display final rate usage
            print("\n--- Final API Rate Status ---")
            self.rate_display.display_once()  # Use our interactive display
            print("----------------------------")
            
            # Save final checkpoint with empty remaining repos
            if self.config["ENABLE_CHECKPOINTING"]:
                self.save_checkpoint(all_stats, analyzed_repo_names, [])
                # Option to remove checkpoint file upon successful completion
                # if self.checkpoint_path.exists():
                #     self.checkpoint_path.unlink()
                #     logger.info("Removed checkpoint file after successful completion")
            
            logger.info(f"Successfully analyzed {len(all_stats)} repositories")
            return all_stats
            
        except RateLimitExceededException:
            logger.error("GitHub API rate limit exceeded during repository listing")
            # Create checkpoint before exiting due to rate limit
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            # Create checkpoint before exiting due to error
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            # Create checkpoint before exiting due to error
            if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                self.save_checkpoint(all_stats, analyzed_repo_names, repos_to_analyze)
            raise

    def check_rate_limit_and_checkpoint(self, all_stats, analyzed_repo_names, remaining_repos):
        """
        Check if the rate limit is approaching threshold and create a checkpoint if needed.
        
        Args:
            all_stats: List of RepoStats objects analyzed so far
            analyzed_repo_names: List of repository names already analyzed
            remaining_repos: List of Repository objects still to analyze
            
        Returns:
            Boolean: True if should stop processing, False if can continue
        """
        try:
            # Update rate data from API
            self.rate_display.update_from_api(self.github)
            remaining = self.rate_display.rate_data["remaining"]
            limit = self.rate_display.rate_data["limit"]
            
            # Check if below checkpoint threshold
            if remaining <= self.config["CHECKPOINT_THRESHOLD"]:
                logger.warning(f"Rate limit low: {remaining} of {limit} remaining")
                
                # Display rate usage
                self.rate_display.display_once()
                
                # Create checkpoint
                if self.config["ENABLE_CHECKPOINTING"] and all_stats:
                    self.save_checkpoint(all_stats, analyzed_repo_names, remaining_repos)
                    
                # Return True to indicate should stop processing
                return True
                
            # Still have enough requests
            return False
                
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    def save_checkpoint(self, all_stats: List[RepoStats], analyzed_repo_names: List[str], remaining_repos: List[Repository]) -> None:
        """Save checkpoint data during analysis"""
        self.checkpoint.save(all_stats, analyzed_repo_names, remaining_repos)
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint data from previous analysis"""
        return self.checkpoint.load()

    def get_file_language(self, file_path: str) -> str:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_EXTENSIONS.get(ext, 'Other')

    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary"""
        ext = Path(file_path).suffix.lower()
        return ext in BINARY_EXTENSIONS

    def is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file"""
        filename = Path(file_path).name.lower()
        return filename in CONFIG_FILES
        
    def is_cicd_file(self, file_path: str) -> bool:
        """Check if file is related to CI/CD configuration"""
        for pattern in CICD_FILES:
            if pattern in file_path.lower():
                return True
        return False
        
    def is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file"""
        file_path_lower = file_path.lower()
        filename = Path(file_path).name.lower()
        
        # Check various test file patterns
        test_patterns = [
            '/test/', '/tests/', '/spec/', '/specs/',
            'test_', '_test.', '.test.', '.spec.',
            'test.', 'spec.', 'tests.', 'specs.'
        ]
        
        return any(pattern in file_path_lower or filename.startswith(pattern) or filename.endswith(pattern) 
                 for pattern in test_patterns)

    def count_lines_of_code(self, content: str, file_path: str) -> int:
        """Count lines of code, excluding empty lines and comments"""
        if not content:
            return 0
        
        # Get file extension to determine comment syntax
        ext = Path(file_path).suffix.lower()
        
        lines = content.split('\n')
        loc = 0
        in_block_comment = False
        
        # Define comment patterns based on language
        if ext in ['.py', '.rb']:
            line_comment = '#'
            block_start = '"""'
            block_end = '"""'
        elif ext in ['.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cs', '.go', '.swift', '.kt']:
            line_comment = '//'
            block_start = '/*'
            block_end = '*/'
        elif ext in ['.html', '.xml']:
            line_comment = None  # HTML doesn't have line comments
            block_start = '<!--'
            block_end = '-->'
        elif ext in ['.sql']:
            line_comment = '--'
            block_start = '/*'
            block_end = '*/'
        else:
            # Default comment syntax
            line_comment = '#'
            block_start = '/*'
            block_end = '*/'
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Handle block comments
            if block_start and block_end:
                if in_block_comment:
                    if block_end in line:
                        in_block_comment = False
                    continue
                elif block_start in line:
                    if block_end not in line[line.find(block_start) + len(block_start):]:
                        in_block_comment = True
                    continue
            
            # Handle line comments
            if line_comment and line.startswith(line_comment):
                continue
                
            # Count non-comment lines
            loc += 1
        
        return loc

    def analyze_repository_files(self, repo: Repository) -> Dict[str, Any]:
        """Analyze files in a repository with improved detection capabilities"""
        stats = {
            'total_files': 0,
            'total_loc': 0,
            'languages': defaultdict(int),
            'file_types': defaultdict(int),
            'has_docs': False,
            'has_readme': False,
            'has_tests': False,
            'test_files_count': 0,
            'has_cicd': False,
            'cicd_files': [],
            'dependency_files': [],
            'project_structure': defaultdict(int),
            'is_empty': False,  # New flag to track empty repositories
            'skipped_directories': set(),  # Track which directories were skipped
            'excluded_file_count': 0  # Count of excluded files
        }
        
        try:
            # Check for rate limits before making API calls
            self.check_rate_limit()
            
            # Get repository contents recursively
            contents = repo.get_contents("")
            files_to_process = []
            
            # Collect all files
            directories_seen = set()
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    try:
                        # Check if directory should be excluded
                        if self.is_excluded_path(file_content.path):
                            stats['skipped_directories'].add(file_content.path)
                            logger.debug(f"Skipping excluded directory: {file_content.path}")
                            continue
                        
                        if file_content.path not in directories_seen:
                            directories_seen.add(file_content.path)
                            contents.extend(repo.get_contents(file_content.path))
                            
                            # Update project structure statistics
                            path_parts = file_content.path.split('/')
                            if len(path_parts) == 1:  # Top-level directory
                                stats['project_structure'][path_parts[0]] += 1
                    except Exception as e:
                        logger.warning(f"Could not access directory {file_content.path}: {e}")
                        continue
                else:
                    # Skip files in excluded directories
                    if self.is_excluded_path(file_content.path):
                        stats['excluded_file_count'] += 1
                        logger.debug(f"Skipping file in excluded path: {file_content.path}")
                        continue
                        
                    files_to_process.append(file_content)
            
            # Process files with progress bar
            for file_content in tqdm(files_to_process, 
                                   desc=f"Analyzing {repo.name} files", 
                                   leave=False, 
                                   colour='cyan'):
                try:
                    file_path = file_content.path
                    stats['total_files'] += 1
                    
                    # Check for documentation
                    if ('readme' in file_path.lower() or 
                        file_path.lower().startswith('docs/') or
                        '/docs/' in file_path.lower() or
                        file_path.lower().endswith('.md')):
                        stats['has_docs'] = True
                        
                    # Specific check for README
                    if 'readme' in file_path.lower():
                        stats['has_readme'] = True
                    
                    # Check for tests
                    if self.is_test_file(file_path):
                        stats['has_tests'] = True
                        stats['test_files_count'] += 1
                    
                    # Check for CI/CD configuration
                    if self.is_cicd_file(file_path):
                        stats['has_cicd'] = True
                        stats['cicd_files'].append(file_path)
                    
                    # Check for dependency files
                    if self.is_config_file(file_path):
                        stats['dependency_files'].append(file_path)
                    
                    # Skip binary files for LOC counting
                    if self.is_binary_file(file_path):
                        stats['file_types']['Binary'] += 1
                        continue
                    
                    # Determine language and file type
                    language = self.get_file_language(file_path)
                    ext = Path(file_path).suffix.lower() or 'no_extension'
                    stats['file_types'][ext] += 1
                    
                    # Get file content for LOC counting
                    if file_content.size < 1024 * 1024:  # Skip files larger than 1MB
                        try:
                            content = file_content.decoded_content.decode('utf-8', errors='ignore')
                            loc = self.count_lines_of_code(content, file_path)
                            stats['total_loc'] += loc
                            stats['languages'][language] += loc
                        except Exception as e:
                            logger.debug(f"Could not decode {file_path}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Error processing file {file_content.path}: {e}")
                    continue
        
        except GithubException as e:
            # Handle empty repository specifically
            if e.status == 404 and "This repository is empty" in str(e):
                logger.info(f"Repository {repo.name} is empty")
                stats['is_empty'] = True
            else:
                logger.error(f"GitHub API error analyzing repository {repo.name}: {e}")
        except RateLimitExceededException:
            logger.error(f"GitHub API rate limit exceeded while analyzing repository {repo.name}")
            # Wait and continue with partial results
            self.check_rate_limit()
        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")
        
        # Log summary of excluded directories
        if stats['skipped_directories']:
            logger.info(f"Skipped {len(stats['skipped_directories'])} directories and {stats['excluded_file_count']} files in {repo.name}")
            logger.debug(f"Skipped directories in {repo.name}: {', '.join(list(stats['skipped_directories'])[:5])}" + 
                       (f" and {len(stats['skipped_directories']) - 5} more..." if len(stats['skipped_directories']) > 5 else ""))
        
        # Remove the tracking set from final stats
        stats.pop('skipped_directories', None)
        
        return dict(stats)

    def calculate_scores(self, repo_stats: Dict[str, Any], repo: Repository) -> Dict[str, float]:
        """Calculate various quality scores for a repository"""
        scores = {
            'maintenance_score': 0.0,
            'popularity_score': 0.0,
            'code_quality_score': 0.0,
            'documentation_score': 0.0
        }
        
        # Maintenance score (0-100)
        maintenance_score = 0.0
        
        # Documentation (20 points)
        if repo_stats.get('has_docs', False):
            maintenance_score += 15
        if repo_stats.get('has_readme', False):
            maintenance_score += 5
        
        # Tests (20 points)
        if repo_stats.get('has_tests', False):
            test_count = repo_stats.get('test_files_count', 0)
            if test_count > 10:
                maintenance_score += 20
            elif test_count > 5:
                maintenance_score += 15
            elif test_count > 0:
                maintenance_score += 10
        
        # CI/CD (10 points)
        if repo_stats.get('has_cicd', False):
            maintenance_score += 10
        
        # Recent activity (20 points)
        if repo_stats.get('is_active', False):
            maintenance_score += 10
            
            # More points for higher activity
            commits_last_month = repo_stats.get('commits_last_month', 0)
            if commits_last_month > 10:
                maintenance_score += 10
            elif commits_last_month > 0:
                maintenance_score += commits_last_month
        
        # License (10 points)
        if repo.license:
            maintenance_score += 10
        
        # Issues management (10 points)
        try:
            if repo.open_issues_count < 10:
                maintenance_score += 10
            elif repo.open_issues_count < 50:
                maintenance_score += 5
        except:
            pass
        
        # Repository size and structure (10 points)
        if repo_stats.get('total_files', 0) > 5:
            maintenance_score += 5
        if len(repo_stats.get('dependency_files', [])) > 0:
            maintenance_score += 5
        
        scores['maintenance_score'] = min(maintenance_score, 100.0)
        
        # Popularity score (0-100)
        popularity_score = 0.0
        
        # Stars (up to 50 points)
        if repo.stargazers_count > 1000:
            popularity_score += 50
        elif repo.stargazers_count > 100:
            popularity_score += 30
        elif repo.stargazers_count > 10:
            popularity_score += 15
        elif repo.stargazers_count > 0:
            popularity_score += 5
        
        # Forks (up to 30 points)
        if repo.forks_count > 100:
            popularity_score += 30
        elif repo.forks_count > 10:
            popularity_score += 20
        elif repo.forks_count > 0:
            popularity_score += 10
        
        # Watchers and contributors (up to 20 points)
        contributors_count = repo_stats.get('contributors_count', 0)
        if contributors_count > 10:
            popularity_score += 10
        elif contributors_count > 1:
            popularity_score += 5
        
        if repo.watchers_count > 10:
            popularity_score += 10
        elif repo.watchers_count > 0:
            popularity_score += 5
        
        scores['popularity_score'] = min(popularity_score, 100.0)
        
        # Code quality score (0-100)
        code_quality_score = 0.0
        
        # Test coverage
        if repo_stats.get('has_tests', False):
            code_quality_score += 30
        
        # CI/CD
        if repo_stats.get('has_cicd', False):
            code_quality_score += 30
        
        # Code size and complexity
        if repo_stats.get('total_loc', 0) > 0:
            avg_loc = repo_stats.get('avg_loc_per_file', 0)
            if avg_loc > 0 and avg_loc < 300:  # Reasonable file size
                code_quality_score += 20
            elif avg_loc > 0:
                code_quality_score += 10
        
        # Documentation
        if repo_stats.get('has_docs', False):
            code_quality_score += 20
        
        scores['code_quality_score'] = min(code_quality_score, 100.0)
        
        # Documentation score (0-100)
        documentation_score = 0.0
        
        # README
        if repo_stats.get('has_readme', False):
            documentation_score += 40
        
        # Additional documentation
        if repo_stats.get('has_docs', False):
            documentation_score += 40
        
        # Wiki presence
        try:
            if repo.has_wiki:
                documentation_score += 20
        except:
            pass
        
        scores['documentation_score'] = min(documentation_score, 100.0)
        
        return scores

    def analyze_single_repository(self, repo: Repository) -> RepoStats:
        """Analyze a single repository and return detailed statistics"""
        logger.info(f"Analyzing repository: {repo.name}")
        
        try:
            # Get file analysis
            file_stats = self.analyze_repository_files(repo)
            
            # Check if repository is empty and handle accordingly
            is_empty = file_stats.get('is_empty', False)
            
            # Calculate derived statistics
            avg_loc = (file_stats['total_loc'] / file_stats['total_files'] 
                      if file_stats['total_files'] > 0 else 0)
            
            # Check if repository is active (commits in last N months)
            is_active = False
            last_commit_date = None
            commits_last_month = 0
            commits_last_year = 0
            commit_frequency = 0.0
            
            try:
                # Get commit history with rate limit awareness
                self.check_rate_limit()
                commits = list(repo.get_commits().get_page(0))
                
                if commits:
                    latest_commit = commits[0]
                    last_commit_date = latest_commit.commit.author.date
                    
                    # Ensure timezone-aware datetime comparison
                    # Create timezone-aware threshold date
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=self.config["INACTIVE_THRESHOLD_DAYS"])
                    
                    # Check activity within threshold using consistent timezone info
                    if last_commit_date is not None:
                        is_active = last_commit_date > inactive_threshold
                    
                    # Count recent commits
                    one_month_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=30)
                    one_year_ago = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=365)
                    
                    # Get a sample of commits for frequency estimation
                    try:
                        recent_commits = list(repo.get_commits(since=one_year_ago))
                        
                        # Count commits in different periods
                        commits_last_month = sum(1 for c in recent_commits 
                                             if c.commit.author.date > one_month_ago)
                        commits_last_year = len(recent_commits)
                        
                        # Calculate average monthly commit frequency
                        if commits_last_year > 0:
                            # Make sure created_at is timezone-aware for consistent comparison
                            created_at = repo.created_at
                            created_at = ensure_utc(created_at)
                                
                            months_active = min(12, (datetime.now().replace(tzinfo=timezone.utc) - created_at).days / 30)
                            if months_active > 0:
                                commit_frequency = commits_last_year / months_active
                    except GithubException as e:
                        logger.warning(f"Could not get recent commits for {repo.name}: {e}")
            except GithubException as e:
                # Handle empty repository specifically
                if e.status == 409 and "Git Repository is empty" in str(e):
                    logger.info(f"Repository {repo.name} has no commits")
                    # Repository has no commits but we can still use pushed_at as a reference
                    last_commit_date = repo.pushed_at
                else:
                    logger.warning(f"Could not get commit info for {repo.name}: {e}")
                    last_commit_date = repo.pushed_at
                
                if last_commit_date:
                    # Ensure timezone awareness consistency
                    inactive_threshold = datetime.now().replace(tzinfo=timezone.utc) - timedelta(days=self.config["INACTIVE_THRESHOLD_DAYS"])
                    last_commit_date = ensure_utc(last_commit_date)
                    is_active = last_commit_date > inactive_threshold
            
            # Get contributors count
            contributors_count = 0
            try:
                contributors_count = repo.get_contributors().totalCount
            except GithubException as e:
                # Skip logging for empty repos as this is expected
                if not (e.status == 409 and "Git Repository is empty" in str(e)):
                    logger.warning(f"Could not get contributors for {repo.name}: {e}")
            
            # Get open PRs count
            open_prs = 0
            try:
                open_prs = repo.get_pulls(state='open').totalCount
            except Exception as e:
                logger.warning(f"Could not get PRs for {repo.name}: {e}")
            
            # Get closed issues count
            closed_issues = 0
            try:
                closed_issues = repo.get_issues(state='closed').totalCount
            except Exception as e:
                logger.warning(f"Could not get closed issues for {repo.name}: {e}")
            
            # Get languages from GitHub API
            github_languages = {}
            try:
                github_languages = repo.get_languages()
            except Exception as e:
                logger.warning(f"Could not get languages from API for {repo.name}: {e}")
            
            # Merge file analysis languages with GitHub API languages
            combined_languages = dict(file_stats['languages'])
            for lang, bytes_count in github_languages.items():
                if lang in combined_languages:
                    combined_languages[lang] = max(combined_languages[lang], bytes_count)
                else:
                    combined_languages[lang] = bytes_count
            
            # Calculate all scores
            scores = self.calculate_scores(file_stats, repo)
            
            # Use ensure_utc consistently in this section
            # Ensure created_at and last_pushed are timezone-aware
            created_at = ensure_utc(repo.created_at)
                
            last_pushed = ensure_utc(repo.pushed_at)
            
            # Create RepoStats object
            repo_stats = RepoStats(
                name=repo.name,
                is_private=repo.private,
                default_branch=repo.default_branch,
                is_fork=repo.fork,
                is_archived=repo.archived,
                is_template=repo.is_template,
                created_at=created_at,
                last_pushed=last_pushed,
                languages=combined_languages,
                has_docs=file_stats['has_docs'],
                has_readme=file_stats['has_readme'],
                total_files=file_stats['total_files'],
                total_loc=file_stats['total_loc'],
                avg_loc_per_file=avg_loc,
                file_types=dict(file_stats['file_types']),
                has_tests=file_stats['has_tests'],
                test_files_count=file_stats['test_files_count'],
                has_cicd=file_stats.get('has_cicd', False),
                cicd_files=file_stats.get('cicd_files', []),
                dependency_files=file_stats['dependency_files'],
                last_commit_date=last_commit_date or repo.pushed_at,
                is_active=is_active,
                commit_frequency=commit_frequency,
                commits_last_month=commits_last_month,
                commits_last_year=commits_last_year,
                license_name=repo.license.name if repo.license else None,
                license_spdx_id=repo.license.spdx_id if repo.license else None,
                contributors_count=contributors_count,
                open_issues=repo.open_issues_count,
                open_prs=open_prs,
                closed_issues=closed_issues,
                topics=repo.topics,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                watchers=repo.watchers_count,
                size_kb=repo.size,
                description=repo.description,
                homepage=repo.homepage,
                maintenance_score=scores['maintenance_score'],
                popularity_score=scores['popularity_score'],
                code_quality_score=scores['code_quality_score'],
                documentation_score=scores['documentation_score'],
                project_structure=file_stats.get('project_structure', {})
            )
            
            # Store excluded file count
            repo_stats.excluded_file_count = file_stats.get('excluded_file_count', 0)
            
            # Add anomaly for empty repository
            if is_empty:
                repo_stats.add_anomaly("Empty repository with no files")
            
            # Calculate additional derived metrics
            repo_stats.calculate_primary_language()
            repo_stats.detect_monorepo()
            
            # Identify anomalies
            self.detect_anomalies(repo_stats)
            
            return repo_stats
            
        except Exception as e:
            logger.error(f"Error analyzing repository {repo.name}: {e}")
            # Return minimal stats on error
            return RepoStats(
                name=repo.name,
                is_private=getattr(repo, 'private', False),
                default_branch=getattr(repo, 'default_branch', 'unknown'),
                is_fork=getattr(repo, 'fork', False),
                is_archived=getattr(repo, 'archived', False),
                is_template=getattr(repo, 'is_template', False),
                created_at=getattr(repo, 'created_at', datetime.now().replace(tzinfo=timezone.utc)),
                last_pushed=getattr(repo, 'pushed_at', datetime.now().replace(tzinfo=timezone.utc))
            )

    def detect_anomalies(self, repo_stats: RepoStats) -> None:
        """Detect anomalies in repository data"""
        # Large repo without documentation
        if repo_stats.total_loc > self.config["LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.has_docs:
            repo_stats.add_anomaly("Large repository without documentation")
            
        # Large repo without tests
        if repo_stats.total_loc > self.config["LARGE_REPO_LOC_THRESHOLD"] and not repo_stats.has_tests:
            repo_stats.add_anomaly("Large repository without tests")
            
        # Popular repo without docs
        if repo_stats.stars > 10 and not repo_stats.has_docs:
            repo_stats.add_anomaly("Popular repository without documentation")
            
        # Many open issues
        if repo_stats.open_issues > 20 and not repo_stats.is_active:
            repo_stats.add_anomaly("Many open issues but repository is inactive")
            
        # Stale repository with stars
        if not repo_stats.is_active and repo_stats.stars > 10:
            repo_stats.add_anomaly("Popular repository appears to be abandoned")
            
        # Project with code but no license
        if repo_stats.total_loc > 1000 and not repo_stats.license_name:
            repo_stats.add_anomaly("Substantial code without license")
            
        # Imbalanced test coverage
        if repo_stats.has_tests and repo_stats.test_files_count < repo_stats.total_files * 0.05:
            repo_stats.add_anomaly("Low test coverage ratio")
            
        # Missing CI/CD in active project
        if repo_stats.is_active and repo_stats.total_loc > 1000 and not repo_stats.has_cicd:
            repo_stats.add_anomaly("Active project without CI/CD configuration")
            
        # Old repository without recent activity
        if repo_stats.created_at and repo_stats.last_commit_date:
            now = datetime.now().replace(tzinfo=timezone.utc)
            created_at = ensure_utc(repo_stats.created_at)
            last_commit = ensure_utc(repo_stats.last_commit_date)
            
            years_since_created = (now - created_at).days / 365.25
            months_since_last_commit = (now - last_commit).days / 30
            
            if years_since_created > 3 and months_since_last_commit > 12:
                repo_stats.add_anomaly("Old repository without updates in over a year")

    def is_excluded_path(self, file_path: str) -> bool:
        """Check if a file path should be excluded from analysis"""
        path_parts = file_path.split('/')
        
        # Check if any part of the path matches excluded directories
        for part in path_parts:
            if part in EXCLUDED_DIRECTORIES:
                return True
                
        # Also check for specific file patterns to exclude
        file_name = path_parts[-1] if path_parts else ""
        if any(file_name.endswith(ext) for ext in BINARY_EXTENSIONS):
            return True
            
            return False
