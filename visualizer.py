from asyncio.log import logger
from zipfile import Path
from models import RepoStats
from utilities import ensure_utc
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Optional, Literal, TypedDict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json


class ThemeConfig(TypedDict, total=False):
    """Theme configuration for the visualization dashboard"""
    # Color schemes
    primary_color: str       # Main brand color
    secondary_color: str     # Secondary brand color
    accent_color: str        # Accent color for highlights
    
    # Light mode colors
    light_bg_color: str      # Light mode background
    light_text_color: str    # Light mode text color
    light_card_bg: str       # Light mode card background
    light_chart_bg: str       # Light mode chart background
    
    # Dark mode colors
    dark_bg_color: str       # Dark mode background
    dark_text_color: str     # Dark mode text color
    dark_card_bg: str        # Dark mode card background
    dark_chart_bg: str       # Dark mode chart background
    
    # Typography
    font_family: str         # Main font family
    heading_font: str        # Font for headings
    code_font: str           # Font for code sections
    
    # UI Elements
    border_radius: str       # Border radius for cards/buttons
    shadow_style: str        # Shadow style for elements
    
    # Chart colors
    chart_palette: List[str] # Colors for charts
    
    # Header gradient
    header_gradient: str     # CSS gradient for header


class DefaultTheme:
    """Default theme settings for the visualization dashboard"""
    
    @staticmethod
    def get_default_theme() -> ThemeConfig:
        """Return the default theme configuration"""
        return {
            # Color schemes
            "primary_color": "#4f46e5",      # Indigo-600
            "secondary_color": "#7c3aed",    # Violet-600
            "accent_color": "#f97316",       # Orange-500
            
            # Light mode colors
            "light_bg_color": "#ffffff",
            "light_text_color": "#111827",   # Gray-900
            "light_card_bg": "#f3f4f6",      # Gray-100
            "light_chart_bg": "#f9fafb",     # Gray-50
            
            # Dark mode colors
            "dark_bg_color": "#1f2937",      # Gray-800
            "dark_text_color": "#f9fafb",    # Gray-50
            "dark_card_bg": "#374151",       # Gray-700
            "dark_chart_bg": "#111827",      # Gray-900
            
            # Typography
            "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            "heading_font": "'Inter', sans-serif",
            "code_font": "'Fira Code', 'Courier New', monospace",
            
            # UI Elements
            "border_radius": "0.75rem",
            "shadow_style": "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            
            # Chart colors
            "chart_palette": [
                "#4f46e5", "#7c3aed", "#f97316", "#10b981", "#f59e0b",
                "#ef4444", "#06b6d4", "#8b5cf6", "#ec4899", "#14b8a6"
            ],
            
            # Header gradient
            "header_gradient": "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)"
        }


class GithubVisualizer:
    """Class responsible for creating visualizations from GitHub repository data"""
    
    def __init__(self, username: str, reports_dir: Path, theme: Optional[ThemeConfig] = None):
        """Initialize the visualizer with username and reports directory"""
        self.username = username
        self.reports_dir = reports_dir
        self.theme = theme if theme is not None else DefaultTheme.get_default_theme()
    
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
        
        # Use theme colors for plots
        chart_colors = self.theme["chart_palette"]
        
        # 1. Top 10 Languages by LOC
        all_languages = defaultdict(int)
        for stats in non_empty_repos:
            for lang, loc in stats.languages.items():
                all_languages[lang] += loc
        
        if all_languages:
            top_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)[:10]
            langs, locs = zip(*top_languages)
            
            fig.add_trace(
                go.Bar(x=list(langs), y=list(locs), name="Languages", marker_color=chart_colors[0]),
                row=1, col=1
            )
        
        # 2. Repository Size Distribution
        repo_sizes = [stats.total_loc for stats in non_empty_repos if stats.total_loc > 0]
        if repo_sizes:
            fig.add_trace(
                go.Histogram(x=repo_sizes, nbinsx=20, name="Repo Sizes", marker_color=chart_colors[1]),
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
                go.Pie(labels=list(types), values=list(counts), name="File Types", 
                      marker=dict(colors=chart_colors[:len(top_file_types)])),
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
                             mode='lines+markers', name="Activity", line=dict(color=chart_colors[2])),
                    row=2, col=2
                )
        
        # 5. Stars vs LOC Correlation
        stars = [stats.stars for stats in non_empty_repos]
        locs = [stats.total_loc for stats in non_empty_repos]
        names = [stats.name for stats in non_empty_repos]
        
        fig.add_trace(
            go.Scatter(x=locs, y=stars, mode='markers',
                      text=names, name="Repos",
                      marker=dict(color=chart_colors[3]),
                      hovertemplate='<b>%{text}</b><br>LOC: %{x}<br>Stars: %{y}'),
            row=3, col=1
        )
        
        # 6. Maintenance Score Distribution
        maintenance_scores = [stats.maintenance_score for stats in non_empty_repos]
        if maintenance_scores:
            fig.add_trace(
                go.Histogram(x=maintenance_scores, nbinsx=20, name="Maintenance Scores", marker_color=chart_colors[4]),
                row=3, col=2
            )
        
        # 7. Repository Age Distribution
        ages = [(datetime.now().replace(tzinfo=timezone.utc) - stats.created_at).days / 365.25 for stats in non_empty_repos]
        if ages:
            fig.add_trace(
                go.Histogram(x=ages, nbinsx=15, name="Repository Ages (Years)", marker_color=chart_colors[5]),
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
                   name="Quality Metrics", marker_color=chart_colors[6]),
            row=4, col=2
        )
        
        # Update layout with theme colors
        fig.update_layout(
            height=2000,
            title_text=f"📊 GitHub Repository Analysis Dashboard - {self.username}",
            title_x=0.5,
            showlegend=False,
            template="plotly_white",
            paper_bgcolor=self.theme["light_chart_bg"],
            plot_bgcolor=self.theme["light_chart_bg"],
            font=dict(family=self.theme["font_family"], color=self.theme["light_text_color"])
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
        
        # Create HTML with Tailwind CSS, custom styling and interactivity
        html_content = self._generate_dashboard_html(fig, non_empty_repos)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Visual report saved to {report_path}")
        
        # Also create individual static charts for detailed analysis
        self.create_detailed_charts(all_stats)
        
    def _generate_dashboard_html(self, fig, non_empty_repos):
        """Generate HTML content for the dashboard with Tailwind CSS and theme support"""
        # Get timestamp for the report
        timestamp = datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create statistics
        total_repos = len(non_empty_repos)
        total_loc = f"{sum(s.total_loc for s in non_empty_repos):,}"
        total_stars = f"{sum(s.stars for s in non_empty_repos):,}"
        active_repos = sum(1 for s in non_empty_repos if s.is_active)
        
        # Prepare repository data for the table
        repos_table_data = []
        for repo in non_empty_repos:
            repos_table_data.append({
                "name": repo.name,
                "language": repo.primary_language or "Unknown",
                "stars": repo.stars,
                "loc": repo.total_loc,
                "is_active": repo.is_active,
                "maintenance": f"{repo.maintenance_score:.1f}"
            })
        
        # Convert to JSON for JavaScript
        repos_json = json.dumps(repos_table_data)
        
        # Create parts of HTML separately to avoid f-string nesting issues
        head_section = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <title>GitHub Repository Analysis Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
            <script>
                tailwind.config = {{
                    darkMode: 'class',
                    theme: {{
                        extend: {{
                            colors: {{
                                primary: '{self.theme["primary_color"]}',
                                secondary: '{self.theme["secondary_color"]}',
                                accent: '{self.theme["accent_color"]}',
                            }},
                            fontFamily: {{
                                sans: ['{self.theme["heading_font"].split(",")[0].replace("'", "")}', 'sans-serif'],
                                mono: ['{self.theme["code_font"].split(",")[0].replace("'", "")}', 'monospace'],
                            }},
                            borderRadius: {{
                                DEFAULT: '{self.theme["border_radius"]}',
                            }},
                            boxShadow: {{
                                custom: '{self.theme["shadow_style"]}',
                            }}
                        }}
                    }}
                }}
            </script>
            <style>
                /* Custom styles that extend Tailwind */
                .bg-gradient-primary {{
                    background: {self.theme["header_gradient"]};
                }}
                
                /* Theme transition */
                .transition-theme {{
                    transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
                }}
                
                /* Custom scrollbar */
                ::-webkit-scrollbar {{
                    width: 8px;
                    height: 8px;
                }}
                
                ::-webkit-scrollbar-track {{
                    background: #f1f1f1;
                }}
                
                .dark ::-webkit-scrollbar-track {{
                    background: #374151;
                }}
                
                ::-webkit-scrollbar-thumb {{
                    background: #888;
                    border-radius: 4px;
                }}
                
                ::-webkit-scrollbar-thumb:hover {{
                    background: #555;
                }}
                
                .dark ::-webkit-scrollbar-thumb {{
                    background: #555;
                }}
                
                .dark ::-webkit-scrollbar-thumb:hover {{
                    background: #777;
                }}
                
                /* Stats animation */
                @keyframes countUp {{
                    from {{ transform: translateY(10px); opacity: 0; }}
                    to {{ transform: translateY(0); opacity: 1; }}
                }}
                
                .animate-count-up {{
                    animation: countUp 0.8s ease-out forwards;
                }}
                
                /* Card hover effects */
                .stat-card {{
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}
                
                .stat-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                }}
            </style>
        </head>"""
        
        body_start = f"""<body class="transition-theme bg-gray-100 dark:bg-gray-900 min-h-screen">
            <!-- Theme toggle button -->
            <button id="theme-toggle" class="fixed top-4 right-4 z-50 p-2 rounded-full bg-white/20 dark:bg-gray-800/20 backdrop-blur-sm text-black dark:text-white border border-gray-200 dark:border-gray-700 hover:bg-white/30 dark:hover:bg-gray-800/30 transition-all duration-300 shadow-lg">
                <svg id="theme-toggle-dark-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
                </svg>
                <svg id="theme-toggle-light-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill-rule="evenodd" clip-rule="evenodd"></path>
                </svg>
            </button>
            
            <div class="container mx-auto px-4 py-8 max-w-7xl">
                <!-- Header section -->
                <div class="bg-gradient-primary rounded-lg shadow-xl mb-8 overflow-hidden">
                    <div class="p-6 md:p-10 text-center">
                        <h1 class="text-3xl md:text-5xl font-light text-white mb-4">📊 GitHub Repository Analysis</h1>
                        <p class="text-lg text-white/90">
                            User: <span class="font-semibold">{self.username}</span> | Generated: {timestamp}
                        </p>
                    </div>
                </div>"""
        
        stats_section = f"""<!-- Stats overview -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                    <!-- Repositories count -->
                    <div class="stat-card bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-primary shadow-lg dark:text-white">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Repositories</p>
                                <p class="text-3xl font-bold animate-count-up">{total_repos}</p>
                            </div>
                            <div class="bg-primary/10 rounded-full p-3">
                                <svg class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
                                </svg>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Total LOC -->
                    <div class="stat-card bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-secondary shadow-lg dark:text-white">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Lines of Code</p>
                                <p class="text-3xl font-bold animate-count-up">{total_loc}</p>
                            </div>
                            <div class="bg-secondary/10 rounded-full p-3">
                                <svg class="w-8 h-8 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                                </svg>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Total Stars -->
                    <div class="stat-card bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-accent shadow-lg dark:text-white">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Stars</p>
                                <p class="text-3xl font-bold animate-count-up">{total_stars}</p>
                            </div>
                            <div class="bg-accent/10 rounded-full p-3">
                                <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                </svg>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Active Repositories -->
                    <div class="stat-card bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-green-500 shadow-lg dark:text-white">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Active Repositories</p>
                                <p class="text-3xl font-bold animate-count-up">{active_repos}</p>
                            </div>
                            <div class="bg-green-500/10 rounded-full p-3">
                                <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                            </div>
                        </div>
                    </div>
                </div>"""
        
        charts_section = """<!-- Charts section -->
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10">
                    <h2 class="text-2xl font-semibold mb-6 dark:text-white">Repository Analysis Dashboard</h2>
                    <div id="main-dashboard" class="w-full" style="height: 2000px;"></div>
                </div>
                
                <!-- Repository Details Table -->
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme">
                    <div class="flex justify-between items-center mb-6">
                        <h2 class="text-2xl font-semibold dark:text-white">Repository Details</h2>
                        <div class="flex space-x-2">
                            <input id="repo-search" type="text" placeholder="Search repositories..." 
                                class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary">
                            <select id="repo-filter" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary">
                                <option value="all">All Repositories</option>
                                <option value="active">Active Only</option>
                                <option value="inactive">Inactive Only</option>
                                <option value="has-docs">With Documentation</option>
                                <option value="no-docs">Without Documentation</option>
                            </select>
                        </div>
                    </div>
                    
                    <!-- Table Container with Horizontal Scroll for Mobile -->
                    <div class="overflow-x-auto">
                        <table id="repos-table" class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="name">
                                        Repository <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="language">
                                        Language <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="stars">
                                        Stars <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="loc">
                                        LOC <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="activity">
                                        Status <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" data-sort="maintenance">
                                        Quality <span class="sort-icon">↕</span>
                                    </th>
                                </tr>
                            </thead>
                            <tbody id="repos-table-body" class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                <!-- Rows will be added by JavaScript -->
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Pagination Controls -->
                    <div class="flex justify-between items-center mt-4">
                        <div class="text-sm text-gray-500 dark:text-gray-400">
                            <span id="total-repos-count">0</span> repositories
                        </div>
                        <div class="flex space-x-2">
                            <button id="prev-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600">
                                Previous
                            </button>
                            <span id="page-info" class="px-4 py-2 text-gray-700 dark:text-gray-300">Page 1</span>
                            <button id="next-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600">
                                Next
                            </button>
                        </div>
                    </div>
                </div>"""
                
        footer_section = f"""<!-- Footer -->
                <div class="mt-10 text-center text-gray-500 dark:text-gray-400">
                    <p>Generated with GHRepoLens • {timestamp}</p>
                </div>
            </div>"""
        
        # JavaScript section with complex escaping issues
        js_part1 = """<script>
                // Initialize theme based on user preference
                if (localStorage.getItem('color-theme') === 'dark' || 
                    (!localStorage.getItem('color-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark');
                    document.getElementById('theme-toggle-light-icon').classList.remove('hidden');
                } else {
                    document.documentElement.classList.remove('dark');
                    document.getElementById('theme-toggle-dark-icon').classList.remove('hidden');
                }
                
                // Theme toggle functionality
                const themeToggleBtn = document.getElementById('theme-toggle');
                const themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
                const themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');
                
                themeToggleBtn.addEventListener('click', function() {
                    // Toggle icons
                    themeToggleDarkIcon.classList.toggle('hidden');
                    themeToggleLightIcon.classList.toggle('hidden');
                    
                    // Toggle dark class
                    document.documentElement.classList.toggle('dark');"""
                    
        js_part2 = f"""
                    // Update localStorage
                    if (document.documentElement.classList.contains('dark')) {{
                        localStorage.setItem('color-theme', 'dark');
                        // Update Plotly chart colors for dark mode
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': '{self.theme["dark_chart_bg"]}',
                            'plot_bgcolor': '{self.theme["dark_chart_bg"]}',
                            'font.color': '{self.theme["dark_text_color"]}'
                        }});
                    }} else {{
                        localStorage.setItem('color-theme', 'light');
                        // Update Plotly chart colors for light mode
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': '{self.theme["light_chart_bg"]}',
                            'plot_bgcolor': '{self.theme["light_chart_bg"]}',
                            'font.color': '{self.theme["light_text_color"]}'
                        }});
                    }}
                }});
                
                // Plot the main dashboard
                var plotData = {fig.to_json()};
                Plotly.newPlot('main-dashboard', plotData.data, plotData.layout, {{responsive: true}});
                
                // Initialize charts with the correct theme
                if (document.documentElement.classList.contains('dark')) {{
                    Plotly.relayout('main-dashboard', {{
                        'paper_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'plot_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'font.color': '{self.theme["dark_text_color"]}'
                    }});
                }}"""
                
        # Add repository table JavaScript
        repo_table_js = f"""
                // Repository data
                const reposData = {repos_json};
                let currentPage = 1;
                const reposPerPage = 10;
                let sortField = 'name';
                let sortDirection = 'asc';
                let filteredRepos = [...reposData];
                
                function initReposTable() {{
                    // Set up sorting
                    document.querySelectorAll('th[data-sort]').forEach(th => {{
                        th.addEventListener('click', () => {{
                            const field = th.getAttribute('data-sort');
                            if (sortField === field) {{
                                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                            }} else {{
                                sortField = field;
                                sortDirection = 'asc';
                            }}
                            
                            // Reset all sort icons
                            document.querySelectorAll('.sort-icon').forEach(icon => {{
                                icon.textContent = '↕';
                            }});
                            
                            // Update current sort icon
                            const sortIcon = th.querySelector('.sort-icon');
                            sortIcon.textContent = sortDirection === 'asc' ? '↓' : '↑';
                            
                            renderTable();
                        }});
                    }});
                    
                    // Set up search and filter
                    document.getElementById('repo-search').addEventListener('input', filterRepos);
                    document.getElementById('repo-filter').addEventListener('change', filterRepos);
                    
                    // Set up pagination
                    document.getElementById('prev-page').addEventListener('click', () => {{
                        if (currentPage > 1) {{
                            currentPage--;
                            renderTable();
                        }}
                    }});
                    
                    document.getElementById('next-page').addEventListener('click', () => {{
                        const totalPages = Math.ceil(filteredRepos.length / reposPerPage);
                        if (currentPage < totalPages) {{
                            currentPage++;
                            renderTable();
                        }}
                    }});
                    
                    // Initial render
                    filterRepos();
                }}
                
                function filterRepos() {{
                    const searchTerm = document.getElementById('repo-search').value.toLowerCase();
                    const filterValue = document.getElementById('repo-filter').value;
                    
                    filteredRepos = reposData.filter(repo => {{
                        // Apply search filter
                        const matchesSearch = 
                            repo.name.toLowerCase().includes(searchTerm) || 
                            repo.language.toLowerCase().includes(searchTerm);
                        
                        // Apply dropdown filter
                        let matchesDropdown = true;
                        if (filterValue === 'active') matchesDropdown = repo.is_active;
                        else if (filterValue === 'inactive') matchesDropdown = !repo.is_active;
                        else if (filterValue === 'has-docs') matchesDropdown = repo.has_docs === 'Yes';
                        else if (filterValue === 'no-docs') matchesDropdown = repo.has_docs === 'No';
                        
                        return matchesSearch && matchesDropdown;
                    }});
                    
                    // Reset to first page
                    currentPage = 1;
                    renderTable();
                }}
                
                function renderTable() {{
                    // Sort repos
                    filteredRepos.sort((a, b) => {{
                        let comparison = 0;
                        
                        if (sortField === 'name' || sortField === 'language') {{
                            comparison = String(a[sortField]).localeCompare(String(b[sortField]));
                        }} else if (sortField === 'stars' || sortField === 'loc') {{
                            comparison = Number(a[sortField]) - Number(b[sortField]);
                        }} else if (sortField === 'activity') {{
                            comparison = a.is_active === b.is_active ? 0 : a.is_active ? -1 : 1;
                        }} else if (sortField === 'maintenance') {{
                            comparison = parseFloat(a.maintenance) - parseFloat(b.maintenance);
                        }}
                        
                        return sortDirection === 'asc' ? comparison : -comparison;
                    }});
                    
                    // Calculate pagination
                    const totalPages = Math.ceil(filteredRepos.length / reposPerPage);
                    const startIndex = (currentPage - 1) * reposPerPage;
                    const endIndex = Math.min(startIndex + reposPerPage, filteredRepos.length);
                    const currentRepos = filteredRepos.slice(startIndex, endIndex);
                    
                    // Update table body
                    const tableBody = document.getElementById('repos-table-body');
                    tableBody.innerHTML = '';
                    
                    currentRepos.forEach(repo => {{
                        const row = document.createElement('tr');
                        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700';
                        
                        row.innerHTML = `
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-primary">
                                ${{repo.name}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.language}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.stars}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.loc.toLocaleString()}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="${{repo.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300'}} px-2 py-1 rounded-full text-xs font-medium">
                                    ${{repo.is_active ? 'Active' : 'Inactive'}}
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                                    <div class="bg-primary h-2.5 rounded-full" style="width: ${{repo.maintenance}}%"></div>
                                </div>
                                <span class="text-xs text-gray-600 dark:text-gray-400 mt-1 block">${{repo.maintenance}}%</span>
                            </td>
                        `;
                        
                        tableBody.appendChild(row);
                    }});
                    
                    // Update pagination info
                    document.getElementById('total-repos-count').textContent = filteredRepos.length;
                    document.getElementById('page-info').textContent = `Page ${{currentPage}} of ${{totalPages || 1}}`;
                    
                    // Enable/disable pagination buttons
                    document.getElementById('prev-page').disabled = currentPage === 1;
                    document.getElementById('next-page').disabled = currentPage === totalPages || totalPages === 0;
                    
                    // Update button styles based on disabled state
                    document.getElementById('prev-page').classList.toggle('opacity-50', currentPage === 1);
                    document.getElementById('next-page').classList.toggle('opacity-50', currentPage === totalPages || totalPages === 0);
                }}
                """
                
        js_part3 = f"""
                // Animate stat cards on scroll
                document.addEventListener('DOMContentLoaded', function() {{
                    const observer = new IntersectionObserver((entries) => {{
                        entries.forEach(entry => {{
                            if (entry.isIntersecting) {{
                                entry.target.classList.add('animate-count-up');
                                observer.unobserve(entry.target);
                            }}
                        }});
                    }}, {{ threshold: 0.1 }});
                    
                    document.querySelectorAll('.stat-card .text-3xl').forEach(card => {{
                        observer.observe(card);
                    }});
                    
                    // Initialize repository table
                    initReposTable();
                }});
                
                {repo_table_js}
            </script>
        </body>
        </html>"""
        
        # Combine all parts
        html_content = "\n".join([
            head_section,
            body_start,
            stats_section,
            charts_section,
            footer_section,
            js_part1,
            js_part2,
            js_part3
        ])
        
        return html_content

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

