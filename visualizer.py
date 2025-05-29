from asyncio.log import logger
from zipfile import Path
from models import RepoStats
from utilities import ensure_utc
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import List
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

