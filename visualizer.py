from asyncio.log import logger
import os
import shutil
from zipfile import Path
from models import RepoStats
from utilities import ensure_utc
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Literal, TypedDict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import numpy as np
from wordcloud import WordCloud


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

        # Copy assets to the reports directory
        self.copy_assets(reports_dir)

    
    def copy_assets(self, reports_dir: Path) -> None:
        """Copy assets to the reports directory"""
        assets_dir = Path(__file__).parent / "assets"
        for asset in assets_dir.glob("*"):
            dest_dir = reports_dir / "assets"
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(asset, dest_dir / asset.name)
    
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
            <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
            <link href="https://unpkg.com/aos@2.3.1/dist/aos.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.2/dist/gsap.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
            <link rel="icon" type="image/png" href="assets/favicon.png">
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
                            }},
                            animation: {{
                                'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                                'float': 'float 3s ease-in-out infinite',
                                'slide-up': 'slideUp 0.5s ease-out',
                                'zoom-in': 'zoomIn 0.5s ease-out',
                                'bounce-in': 'bounceIn 0.7s ease-out',
                                'fade-in': 'fadeIn 0.5s ease-out',
                                'spin-slow': 'spin 8s linear infinite',
                            }},
                            keyframes: {{
                                float: {{
                                    '0%, 100%': {{ transform: 'translateY(0)' }},
                                    '50%': {{ transform: 'translateY(-10px)' }},
                                }},
                                slideUp: {{
                                    '0%': {{ transform: 'translateY(20px)', opacity: '0' }},
                                    '100%': {{ transform: 'translateY(0)', opacity: '1' }},
                                }},
                                zoomIn: {{
                                    '0%': {{ transform: 'scale(0.95)', opacity: '0' }},
                                    '100%': {{ transform: 'scale(1)', opacity: '1' }},
                                }},
                                bounceIn: {{
                                    '0%': {{ transform: 'scale(0.3)', opacity: '0' }},
                                    '50%': {{ transform: 'scale(1.05)', opacity: '0.8' }},
                                    '70%': {{ transform: 'scale(0.9)', opacity: '0.9' }},
                                    '100%': {{ transform: 'scale(1)', opacity: '1' }},
                                }},
                                fadeIn: {{
                                    '0%': {{ opacity: '0' }},
                                    '100%': {{ opacity: '1' }},
                                }}
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
                    box-shadow: 0 15px 30px -5px rgba(0, 0, 0, 0.15), 0 10px 15px -5px rgba(0, 0, 0, 0.08);
                }}
                
                /* New animation classes */
                .card-3d-effect {{
                    transform-style: preserve-3d;
                    perspective: 1000px;
                    transition: all 0.3s ease;
                }}
                
                .card-3d-effect:hover {{
                    transform: rotateX(5deg) rotateY(5deg);
                }}
                
                .card-inner {{
                    transform: translateZ(20px);
                    transition: all 0.3s ease;
                }}
                
                /* Animated background */
                .animated-bg {{
                    background-size: 400% 400%;
                    animation: gradientBG 15s ease infinite;
                }}
                
                @keyframes gradientBG {{
                    0% {{ background-position: 0% 50%; }}
                    50% {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}
                
                /* Progress bar animation */
                @keyframes progressFill {{
                    from {{ width: 0%; }}
                    to {{ width: var(--progress-width); }}
                }}
                
                .animate-progress {{
                    animation: progressFill 1.5s ease-out forwards;
                }}
                
                /* Icon pulse */
                @keyframes iconPulse {{
                    0% {{ transform: scale(1); }},
                    50% {{ transform: scale(1.1); }},
                    100% {{ transform: scale(1); }}
                }}
                
                .animate-icon-pulse {{
                    animation: iconPulse 2s ease-in-out infinite;
                }}
                
                /* Chart entrance animation */
                @keyframes chartEnter {{
                    0% {{ opacity: 0; transform: translateY(30px); }}
                    100% {{ opacity: 1; transform: translateY(0); }}
                }}
                
                .animate-chart-enter {{
                    animation: chartEnter 0.8s ease-out forwards;
                }}
                
                /* Creator section animation */
                @keyframes glowPulse {{
                    0% {{ box-shadow: 0 0 5px 0 rgba(79, 70, 229, 0.5); }}
                    50% {{ box-shadow: 0 0 20px 5px rgba(79, 70, 229, 0.5); }}
                    100% {{ box-shadow: 0 0 5px 0 rgba(79, 70, 229, 0.5); }}
                }}
                
                .animate-glow {{
                    animation: glowPulse 3s infinite;
                }}
                
                .social-link {{
                    transition: all 0.3s ease;
                }}
                
                .social-link:hover {{
                    transform: translateY(-3px);
                    filter: brightness(1.2);
                }}
                
                /* New creator card styles */
                .creator-card {{
                    position: relative;
                    overflow: hidden;
                    border-radius: 16px;
                    transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1);
                }}
                
                .creator-card::before {{
                    content: "";
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(225deg, rgba(79, 70, 229, 0.4) 0%, rgba(124, 58, 237, 0.4) 50%, rgba(249, 115, 22, 0.4) 100%);
                    opacity: 0;
                    z-index: 0;
                    transition: opacity 0.5s ease;
                }}
                
                .creator-card:hover::before {{
                    opacity: 1;
                }}
                
                .creator-profile-img {{
                    position: relative;
                    transition: all 0.5s ease;
                }}
                
                .creator-card:hover .creator-profile-img {{
                    transform: scale(1.05);
                }}
                
                .creator-info {{
                    position: relative;
                    z-index: 1;
                }}
                
                .social-icon {{
                    transition: all 0.3s ease;
                    position: relative;
                    overflow: hidden;
                }}
                
                .social-icon::after {{
                    content: "";
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.2) 100%);
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }}
                
                .social-icon:hover {{
                    transform: translateY(-5px) scale(1.1);
                }}
                
                .social-icon:hover::after {{
                    opacity: 1;
                }}
                
                .stack-badge {{
                    position: relative;
                    overflow: hidden;
                }}
                
                .stack-badge::before {{
                    content: "";
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
                    transform: rotate(45deg);
                    animation: shine 3s infinite;
                }}
                
                @keyframes shine {{
                    0% {{ transform: translateX(-100%) rotate(45deg); }}
                    100% {{ transform: translateX(100%) rotate(45deg); }}
                }}
                
                .animate-typing {{
                    overflow: hidden;
                    border-right: 2.5px solid;
                    white-space: nowrap;
                    animation: typing 2.5s steps(40, end) forwards, 
                               blink-caret 0.65s step-end infinite;
                    width: 0;
                    display: inline-block;
                    max-width: calc(20ch + 10px);
                }}
                
                @keyframes typing {{
                    from {{ width: 0 }}
                    to {{ width: calc(20ch + 10px) }}
                }}
                
                @keyframes blink-caret {{
                    from, to {{ border-color: transparent }}
                    50% {{ border-color: currentColor }}
                }}
                
                .tech-badge {{
                    background: rgba(79, 70, 229, 0.1);
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(79, 70, 229, 0.2);
                    transition: all 0.3s ease;
                }}
                
                .tech-badge:hover {{
                    background: rgba(79, 70, 229, 0.2);
                    transform: translateY(-2px);
                }}
                
                .floating {{
                    animation: floating 3s ease-in-out infinite;
                }}
                
                @keyframes floating {{
                    0% {{ transform: translateY(0px); }}
                    50% {{ transform: translateY(-10px); }}
                    100% {{ transform: translateY(0px); }}
                }}
            </style>
        </head>"""
        
        body_start = f"""<body class="transition-theme bg-gray-100 dark:bg-gray-900 min-h-screen">
            <!-- Theme toggle button with animation -->
            <button id="theme-toggle" class="fixed top-4 right-4 z-50 p-2 rounded-full bg-white/20 dark:bg-gray-800/20 backdrop-blur-sm text-black dark:text-white border border-gray-200 dark:border-gray-700 hover:bg-white/30 dark:hover:bg-gray-800/30 transition-all duration-300 shadow-lg hover:animate-spin-slow">
                <svg id="theme-toggle-dark-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
                </svg>
                <svg id="theme-toggle-light-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill-rule="evenodd" clip-rule="evenodd"></path>
                </svg>
            </button>
            
            <div class="container mx-auto px-4 py-8 max-w-7xl">
                <!-- Header section with enhanced animations and banner as background -->
                <div data-aos="fade-down" data-aos-duration="800" class="relative bg-gradient-primary animated-bg rounded-lg shadow-xl mb-8 overflow-hidden transform transition-all hover:shadow-2xl">
                    <!-- Semi-transparent background banner image -->
                    <div class="absolute inset-0 w-full h-full opacity-20 dark:hidden">
                        <img src="assets/light_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>
                    <div class="absolute inset-0 w-full h-full opacity-20 hidden dark:block">
                        <img src="assets/dark_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>
                    
                    <div class="relative p-6 md:p-10 text-center z-10">
                        <h1 class="text-3xl md:text-5xl font-light text-white mb-4 animate-bounce-in">📊 GitHub Repository Analysis</h1>
                        <p class="text-lg text-white/90 animate-fade-in">
                            User: <span class="font-semibold">{self.username}</span> | Generated: {timestamp}
                        </p>
                    </div>
                </div>"""
        
        # Add creator section right after the header section
        creator_section = """
                <!-- Creator Section - Modern & Compact -->
                <div id="creator-section" class="relative overflow-hidden bg-white/10 dark:bg-gray-800/20 backdrop-blur-sm rounded-xl shadow-lg mb-6 transition-all duration-500 group">
                    <div class="absolute inset-0 bg-gradient-to-br from-primary/5 via-secondary/5 to-accent/5 dark:from-primary/10 dark:via-secondary/10 dark:to-accent/10 opacity-80"></div>
                    
                    <div class="relative z-10 flex items-center p-4 gap-4">
                        <!-- Creator Image & Name -->
                        <div class="relative w-16 h-16 rounded-full overflow-hidden shadow-lg border-2 border-primary/30 creator-profile-img" data-aos="zoom-in" data-aos-delay="100">
                            <img src="assets/alaamer.jpg" alt="Amr Muhamed" class="w-full h-full object-cover" />
                            <div class="absolute inset-0 bg-gradient-to-tr from-primary/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                        </div>
                        
                        <div class="flex-1">
                            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                                <!-- Name & Role -->
                                <div>
                                    <h3 class="text-xl font-bold text-gray-800 dark:text-white flex items-center" data-aos="fade-right" data-aos-delay="150">
                                        <span class="mr-2">Amr Muhamed</span>
                                        <span class="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary dark:bg-primary/20 stack-badge">
                                            Full Stack Dev
                                        </span>
                                    </h3>
                                    <p class="text-sm text-gray-600 dark:text-gray-300" data-aos="fade-right" data-aos-delay="200">
                                        <span class="animate-typing">Creator of GHRepoLens 😄  </span>
                                    </p>
                                </div>
                                
                                <!-- Social Links -->
                                <div class="flex gap-2" data-aos="fade-left" data-aos-delay="250">
                                    <a href="https://github.com/alaamer12" target="_blank" class="social-icon p-2 rounded-full bg-gray-800 text-white hover:bg-primary shadow-md">
                                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                                        </svg>
                                    </a>
                                    <a href="https://www.linkedin.com/in/amr-muhamed-0b0709265/" target="_blank" class="social-icon p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 shadow-md">
                                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                                        </svg>
                                    </a>
                                    <a href="https://portfolio-qiw8.vercel.app/" target="_blank" class="social-icon p-2 rounded-full bg-emerald-600 text-white hover:bg-emerald-700 shadow-md">
                                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M12 0c-6.627 0-12 5.373-12 12s5.373 12 12 12 12-5.373 12-12-5.373-12-12-12zm1 16.057v-3.057h2.994c-.059 1.143-.212 2.24-.456 3.279-.823-.12-1.674-.188-2.538-.222zm1.957 2.162c-.499 1.33-1.159 2.497-1.957 3.456v-3.62c.666.028 1.319.081 1.957.164zm-1.957-7.219v-3.015c.868-.034 1.721-.103 2.548-.224.238 1.027.389 2.111.446 3.239h-2.994zm0-5.014v-3.661c.806.969 1.471 2.15 1.971 3.496-.642.084-1.3.137-1.971.165zm2.703-3.267c1.237.496 2.354 1.228 3.29 2.146-.642.234-1.311.442-2.019.607-.344-.992-.775-1.91-1.271-2.753zm-7.241 13.56c-.244-1.039-.398-2.136-.456-3.279h2.994v3.057c-.865.034-1.714.102-2.538.222zm2.538 1.776v3.62c-.798-.959-1.458-2.126-1.957-3.456.638-.083 1.291-.136 1.957-.164zm-2.994-7.055c.057-1.128.207-2.212.446-3.239.827.121 1.68.19 2.548.224v3.015h-2.994zm1.024-5.179c.5-1.346 1.165-2.527 1.97-3.496v3.661c-.671-.028-1.329-.081-1.97-.165zm-2.005-.35c-.708-.165-1.377-.373-2.018-.607.937-.918 2.053-1.65 3.29-2.146-.496.844-.927 1.762-1.272 2.753zm-.549 1.918c-.264 1.151-.434 2.36-.492 3.611h-3.933c.165-1.658.739-3.197 1.617-4.518.88.361 1.816.67 2.808.907zm.009 9.262c-.988.236-1.92.542-2.797.9-.89-1.328-1.471-2.879-1.637-4.551h3.934c.058 1.265.231 2.488.5 3.651zm.553 1.917c.342.976.768 1.881 1.257 2.712-1.223-.49-2.326-1.211-3.256-2.115.636-.229 1.299-.435 1.999-.597zm9.924 0c.7.163 1.362.367 1.999.597-.931.903-2.034 1.625-3.257 2.116.489-.832.915-1.737 1.258-2.713zm.553-1.917c.27-1.163.442-2.386.501-3.651h3.934c-.167 1.672-.748 3.223-1.638 4.551-.877-.358-1.81-.664-2.797-.9zm.501-5.651c-.058-1.251-.229-2.46-.492-3.611.992-.237 1.929-.546 2.809-.907.877 1.321 1.451 2.86 1.616 4.518h-3.933z"/>
                                        </svg>
                                    </a>
                                </div>
                            </div>
                            
                            <!-- Technologies Row -->
                            <div class="mt-2 flex flex-wrap gap-2" data-aos="fade-up" data-aos-delay="300">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">Python</span>
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">JavaScript</span>
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">React</span>
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">Data Analysis</span>
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">ML</span>
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">GitHub API</span>
                            </div>
                        </div>
                        
                    </div>
                </div>
                
                <script>
                // Initialize GSAP animations for the creator section
                document.addEventListener('DOMContentLoaded', function() {
                    if (typeof gsap !== 'undefined') {
                        const creatorSection = document.getElementById('creator-section');
                        if (creatorSection) {
                            // Create hover effect
                            creatorSection.addEventListener('mouseenter', function() {
                                gsap.to(this, {
                                    scale: 1.02,
                                    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
                                    duration: 0.3,
                                    ease: 'power2.out'
                                });
                                
                                // Animate technology badges
                                gsap.to(this.querySelectorAll('.tech-badge'), {
                                    stagger: 0.05,
                                    y: -4,
                                    scale: 1.1,
                                    duration: 0.2,
                                    ease: 'back.out(1.7)'
                                });
                            });
                            
                            creatorSection.addEventListener('mouseleave', function() {
                                gsap.to(this, {
                                    scale: 1,
                                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                                    duration: 0.3,
                                    ease: 'power2.out'
                                });
                                
                                // Reset technology badges
                                gsap.to(this.querySelectorAll('.tech-badge'), {
                                    stagger: 0.05,
                                    y: 0,
                                    scale: 1,
                                    duration: 0.2,
                                    ease: 'back.out(1.7)'
                                });
                            });
                        }
                    }
                });
                </script>"""
        
        stats_section = f"""<!-- Stats overview with enhanced animations -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                    <!-- Repositories count -->
                    <div data-aos="zoom-in" data-aos-delay="100" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-primary shadow-lg dark:text-white overflow-hidden relative group">
                        <div class="card-inner flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Repositories</p>
                                <p id="repo-count" class="text-3xl font-bold">0</p>
                            </div>
                            <div class="bg-primary/10 rounded-full p-3 group-hover:animate-icon-pulse">
                                <svg class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
                                </svg>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-primary transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500"></div>
                    </div>
                    
                    <!-- Total LOC -->
                    <div data-aos="zoom-in" data-aos-delay="200" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-secondary shadow-lg dark:text-white overflow-hidden relative group">
                        <div class="card-inner flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Lines of Code</p>
                                <p id="loc-count" class="text-3xl font-bold">0</p>
                            </div>
                            <div class="bg-secondary/10 rounded-full p-3 group-hover:animate-icon-pulse">
                                <svg class="w-8 h-8 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                                </svg>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-secondary transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500"></div>
                    </div>
                    
                    <!-- Total Stars -->
                    <div data-aos="zoom-in" data-aos-delay="300" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-accent shadow-lg dark:text-white overflow-hidden relative group">
                        <div class="card-inner flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Total Stars</p>
                                <p id="stars-count" class="text-3xl font-bold">0</p>
                            </div>
                            <div class="bg-accent/10 rounded-full p-3 group-hover:animate-icon-pulse">
                                <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                </svg>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-accent transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500"></div>
                    </div>
                    
                    <!-- Active Repositories -->
                    <div data-aos="zoom-in" data-aos-delay="400" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-green-500 shadow-lg dark:text-white overflow-hidden relative group">
                        <div class="card-inner flex items-center justify-between">
                            <div>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Active Repositories</p>
                                <p id="active-count" class="text-3xl font-bold">0</p>
                            </div>
                            <div class="bg-green-500/10 rounded-full p-3 group-hover:animate-icon-pulse">
                                <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-green-500 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-500"></div>
                    </div>
                </div>"""
        
        charts_section = """<!-- Charts section with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10 transform hover:shadow-2xl transition-all duration-300">
                    <h2 class="text-2xl font-semibold mb-6 dark:text-white flex items-center">
                        <span class="bg-primary/10 text-primary p-2 rounded-lg mr-3">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        </span>
                        Repository Analysis Dashboard
                    </h2>
                    <div id="main-dashboard" class="w-full animate-chart-enter" style="height: 2000px;"></div>
                </div>
                
                <!-- Repository Details Table with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" data-aos-delay="200" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme transform hover:shadow-2xl transition-all duration-300">
                    <div class="flex flex-col md:flex-row justify-between items-center mb-6">
                        <h2 class="text-2xl font-semibold dark:text-white flex items-center mb-4 md:mb-0">
                            <span class="bg-secondary/10 text-secondary p-2 rounded-lg mr-3">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                            </span>
                            Repository Details
                        </h2>
                        <div class="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-2 w-full md:w-auto">
                            <div class="relative">
                                <input id="repo-search" type="text" placeholder="Search repositories..." 
                                    class="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary w-full">
                                <div class="absolute left-3 top-2.5 text-gray-400">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                </div>
                            </div>
                            <select id="repo-filter" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary">
                                <option value="all">All Repositories</option>
                                <option value="active">Active Only</option>
                                <option value="inactive">Inactive Only</option>
                                <option value="has-docs">With Documentation</option>
                                <option value="no-docs">Without Documentation</option>
                            </select>
                        </div>
                    </div>
                    
                    <!-- Table Container with enhanced animations -->
                    <div class="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                        <table id="repos-table" class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="name">
                                        Repository <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="language">
                                        Language <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="stars">
                                        Stars <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="loc">
                                        LOC <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="activity">
                                        Status <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="maintenance">
                                        Quality <span class="sort-icon">↕</span>
                                    </th>
                                </tr>
                            </thead>
                            <tbody id="repos-table-body" class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                <!-- Rows will be added by JavaScript -->
                            </tbody>
                        </table>
                    </div>
                    
                    <!-- Pagination Controls with enhanced styling -->
                    <div class="flex flex-col sm:flex-row justify-between items-center mt-6 space-y-3 sm:space-y-0">
                        <div class="text-sm text-gray-500 dark:text-gray-400 px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded-lg">
                            <span id="total-repos-count">0</span> repositories found
                        </div>
                        <div class="flex space-x-2">
                            <button id="prev-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors duration-200 flex items-center">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                                </svg>
                                Previous
                            </button>
                            <span id="page-info" class="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg">Page 1</span>
                            <button id="next-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors duration-200 flex items-center">
                                Next
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                                </svg>
                            </button>
                        </div>
                    </div>"""
                
        # NEW: Add links to additional static charts with enhanced animations
        additional_charts_section = """<!-- Additional Charts Section with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" data-aos-delay="300" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10 transform hover:shadow-2xl transition-all duration-300">
                    <h2 class="text-2xl font-semibold mb-6 dark:text-white flex items-center">
                        <span class="bg-accent/10 text-accent p-2 rounded-lg mr-3">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                            </svg>
                        </span>
                        Additional Analysis Charts
                    </h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <!-- Timeline Chart -->
                        <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-primary dark:group-hover:text-primary transition-colors duration-300">Repository Timeline</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Chronological view of repository creation and last commit dates</p>
                                <a href="repository_timeline.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="repository_timeline.png" alt="Repository Timeline" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-primary/0 group-hover:bg-primary/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-primary font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Language Evolution -->
                        <div data-aos="zoom-in" data-aos-delay="150" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-secondary dark:group-hover:text-secondary transition-colors duration-300">Language Evolution</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">How language usage has changed over time</p>
                                <a href="language_evolution.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="language_evolution.png" alt="Language Evolution" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-secondary/0 group-hover:bg-secondary/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-secondary font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Quality Heatmap -->
                        <div data-aos="zoom-in" data-aos-delay="200" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-accent dark:group-hover:text-accent transition-colors duration-300">Maintenance Quality Matrix</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Quality factors across top repositories</p>
                                <a href="quality_heatmap.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="quality_heatmap.png" alt="Quality Heatmap" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-accent/0 group-hover:bg-accent/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-accent font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Repository Types -->
                        <div data-aos="zoom-in" data-aos-delay="250" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-green-500 dark:group-hover:text-green-500 transition-colors duration-300">Repository Types</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Distribution of different repository types</p>
                                <a href="repo_types_distribution.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="repo_types_distribution.png" alt="Repository Types" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-green-500/0 group-hover:bg-green-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-green-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Commit Activity -->
                        <div data-aos="zoom-in" data-aos-delay="300" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-blue-500 dark:group-hover:text-blue-500 transition-colors duration-300">Commit Activity</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Heatmap of commit activity by month and year</p>
                                <a href="commit_activity_heatmap.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="commit_activity_heatmap.png" alt="Commit Activity" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-blue-500/0 group-hover:bg-blue-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-blue-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Top Repositories -->
                        <div data-aos="zoom-in" data-aos-delay="350" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-purple-500 dark:group-hover:text-purple-500 transition-colors duration-300">Top Repositories</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Top repositories by various metrics</p>
                                <a href="top_repos_metrics.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="top_repos_metrics.png" alt="Top Repositories" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-purple-500/0 group-hover:bg-purple-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-purple-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Metrics Correlation -->
                        <div data-aos="zoom-in" data-aos-delay="400" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-pink-500 dark:group-hover:text-pink-500 transition-colors duration-300">Metrics Correlation</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Correlation between different repository metrics</p>
                                <a href="metrics_correlation.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="metrics_correlation.png" alt="Metrics Correlation" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-pink-500/0 group-hover:bg-pink-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-pink-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Topics Word Cloud -->
                        <div data-aos="zoom-in" data-aos-delay="450" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-yellow-500 dark:group-hover:text-yellow-500 transition-colors duration-300">Topics Word Cloud</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Visual representation of repository topics</p>
                                <a href="topics_wordcloud.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="topics_wordcloud.png" alt="Topics Word Cloud" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-yellow-500/0 group-hover:bg-yellow-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-yellow-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                        
                        <!-- Active vs Inactive Age -->
                        <div data-aos="zoom-in" data-aos-delay="500" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                            <div class="p-4">
                                <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-teal-500 dark:group-hover:text-teal-500 transition-colors duration-300">Active vs Inactive Repos</h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">Age distribution of active vs inactive repositories</p>
                                <a href="active_inactive_age.png" target="_blank" class="block relative">
                                    <div class="overflow-hidden rounded-lg">
                                        <img src="active_inactive_age.png" alt="Active vs Inactive Age" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                                    </div>
                                    <div class="absolute inset-0 bg-teal-500/0 group-hover:bg-teal-500/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                                        <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-teal-500 font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View Full Size
                                        </span>
                                    </div>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>"""
                
        footer_section = f"""<!-- Footer with animations -->
                <div data-aos="fade-up" data-aos-duration="600" class="mt-10 text-center">
                    <div class="py-6 px-4 bg-gradient-primary rounded-lg text-white/90 shadow-lg">
                        <p class="flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 animate-pulse-slow" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            Generated with GHRepoLens • {timestamp}
                        </p>
                    </div>
                </div>
            </div>"""
        
        # JavaScript section with complex escaping issues
        js_part1 = """<script>
                // Initialize AOS animations
                document.addEventListener('DOMContentLoaded', function() {
                    AOS.init({
                        duration: 800,
                        easing: 'ease-in-out',
                        once: true,
                        mirror: false
                    });
                });
                
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
                
                // Plot the main dashboard with animation
                var plotData = {fig.to_json()};
                Plotly.newPlot('main-dashboard', plotData.data, plotData.layout, {{responsive: true}});
                
                // Initialize charts with the correct theme
                if (document.documentElement.classList.contains('dark')) {{
                    Plotly.relayout('main-dashboard', {{
                        'paper_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'plot_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'font.color': '{self.theme["dark_text_color"]}'
                    }});
                }}
                
                // Animated number counters
                function animateCounters() {{
                    // Counter animation function
                    function animateValue(element, start, end, duration) {{
                        let startTimestamp = null;
                        const step = (timestamp) => {{
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            let value = Math.floor(progress * (end - start) + start);
                            
                            // Format with commas if needed
                            if (end > 999) {{
                                value = value.toLocaleString();
                            }}
                            
                            element.textContent = value;
                            if (progress < 1) {{
                                window.requestAnimationFrame(step);
                            }}
                        }};
                        window.requestAnimationFrame(step);
                    }}
                    
                    // Animate repo count
                    const repoCountElement = document.getElementById('repo-count');
                    animateValue(repoCountElement, 0, {total_repos}, 1500);
                    
                    // Animate LOC count - parse the string value directly in JavaScript
                    const locCountElement = document.getElementById('loc-count');
                    const locValue = '{total_loc}';
                    animateValue(locCountElement, 0, parseInt(locValue.replace(/,/g, '')), 2000);
                    
                    // Animate stars count - parse the string value directly in JavaScript
                    const starsCountElement = document.getElementById('stars-count');
                    const starsValue = '{total_stars}';
                    animateValue(starsCountElement, 0, parseInt(starsValue.replace(/,/g, '')), 2000);
                    
                    // Animate active count
                    const activeCountElement = document.getElementById('active-count');
                    animateValue(activeCountElement, 0, {active_repos}, 1500);
                }}"""
                
        # Add repository table JavaScript with enhanced animations
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
                    
                    currentRepos.forEach((repo, index) => {{
                        const row = document.createElement('tr');
                        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-150';
                        row.style.animation = `slideUp ${{0.2 + index * 0.05}}s ease-out forwards`;
                        
                        // Animate progress bar
                        const animateProgress = `style="--progress-width: ${{repo.maintenance}}%; animation: progressFill 1s ease-out forwards; animation-delay: ${{0.5 + index * 0.1}}s;"`;
                        
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
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                                    <div class="bg-primary h-2.5 rounded-full w-0 animate-progress" ${{animateProgress}}></div>
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
                // Initialize when DOM is loaded
                document.addEventListener('DOMContentLoaded', function() {{
                    // Start animated counters
                    animateCounters();
                    
                    // Initialize repository table
                    initReposTable();
                    
                    // Add intersection observer for animations not handled by AOS
                    const observer = new IntersectionObserver((entries) => {{
                        entries.forEach(entry => {{
                            if (entry.isIntersecting) {{
                                entry.target.classList.add('animate-fade-in');
                                observer.unobserve(entry.target);
                            }}
                        }});
                    }}, {{ threshold: 0.1 }});
                    
                    // Observe elements that need animation
                    document.querySelectorAll('.needs-animation').forEach(el => {{
                        observer.observe(el);
                    }});
                }});
                
                {repo_table_js}
            </script>
        </body>
        </html>"""
        
        # Combine all parts
        html_content = "\n".join([
            head_section,
            body_start,
            creator_section,
            stats_section,
            charts_section,
            additional_charts_section,
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
        
        # Use theme colors for consistency
        chart_colors = self.theme["chart_palette"]
        
        # 1. Repository Timeline Chart
        _, ax = plt.subplots(figsize=(15, 8))
        
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
        
        # 3. Maintenance Quality Heatmap (only for non-empty repos)
        if non_empty_repos:
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
        
        # 5. NEW: Repository Types Distribution
        _, ax = plt.subplots(figsize=(12, 8))
        
        # Count different repository types
        repo_types = {
            'Regular': sum(1 for s in all_stats if not (s.is_fork or s.is_archived or s.is_template)),
            'Forks': sum(1 for s in all_stats if s.is_fork),
            'Archived': sum(1 for s in all_stats if s.is_archived),
            'Templates': sum(1 for s in all_stats if s.is_template),
            'Private': sum(1 for s in all_stats if s.is_private),
            'Public': sum(1 for s in all_stats if not s.is_private)
        }
        
        # Create bar chart
        bars = ax.bar(repo_types.keys(), repo_types.values(), color=chart_colors[:len(repo_types)])
        
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
        
        # 6. NEW: Commit Activity Heatmap
        if non_empty_repos:
            # Extract monthly commit data from non-empty repos
            # Group by month and year
            commit_data = defaultdict(int)
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            for stats in non_empty_repos:
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
                    
                    fig, ax = plt.subplots(figsize=(12, len(years) * 0.8 + 2))
                    
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
        
        # 7. NEW: Top 10 Repositories by Metrics
        if len(non_empty_repos) > 0:
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
        
        # 8. NEW: Score Correlation Matrix
        if len(non_empty_repos) > 5:  # Only do this if we have enough repos for meaningful correlations
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
        
        # 9. NEW: Repository Topics WordCloud
        if non_empty_repos:
            # Collect all topics
            all_topics = []
            for repo in non_empty_repos:
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
        
        # 10. NEW: Active vs Inactive Repositories Age Distribution
        if non_empty_repos:
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
        
        # 11. NEW: Open Issues vs Stars Scatter Plot
        if non_empty_repos:
            _, ax = plt.subplots(figsize=(12, 8))
            
            # Extract data
            stars = [r.stars for r in non_empty_repos]
            issues = [r.open_issues for r in non_empty_repos]
            names = [r.name for r in non_empty_repos]
            
            # Create scatter plot
            scatter = ax.scatter(stars, issues, 
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
            
        # 12. NEW: Repository Creation Timeline
        if all_stats:
            fig, ax = plt.subplots(figsize=(15, 6))
            
            # Extract creation dates
            creation_dates = [ensure_utc(r.created_at) for r in all_stats]
            
            # Create histogram by year and month
            years_months = [(d.year, d.month) for d in creation_dates]
            unique_years_months = sorted(set(years_months))
            
            if unique_years_months:
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
        
        # 13. NEW: Documentation and README Quality Distribution
        if non_empty_repos:
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
            
        # 14. NEW: Infrastructure Quality Metrics (Packages, Deployments, Releases)
        if non_empty_repos:
            _, ax = plt.subplots(figsize=(12, 8))
            
            # Calculate percentages for each metric
            total = len(non_empty_repos)
            with_packages = sum(1 for r in non_empty_repos if r.has_packages)
            with_deployments = sum(1 for r in non_empty_repos if r.has_deployments)
            with_releases = sum(1 for r in non_empty_repos if r.has_releases)
            with_cicd = sum(1 for r in non_empty_repos if r.has_cicd)
            
            # Create data for grouped bar chart
            categories = ['Package Management', 'Deployment Config', 'Releases', 'CI/CD']
            yes_counts = [with_packages, with_deployments, with_releases, with_cicd]
            no_counts = [total - count for count in yes_counts]
            
            # Plot the data
            x = np.arange(len(categories))
            width = 0.35
            
            # Plot "Yes" bars
            yes_bars = ax.bar(x - width/2, yes_counts, width, label='Yes', color=chart_colors[0])
            # Plot "No" bars
            no_bars = ax.bar(x + width/2, no_counts, width, label='No', color=chart_colors[1])
            
            # Add counts and percentages
            for i, bars in enumerate([yes_bars, no_bars]):
                label = "Yes" if i == 0 else "No"
                for j, bar in enumerate(bars):
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
            
        # 15. NEW: Release Counts (for repos with releases)
        repos_with_releases = [r for r in non_empty_repos if r.has_releases and r.release_count > 0]
        if len(repos_with_releases) >= 3:  # Only create if we have at least 3 repos with releases
            # Sort by release count
            top_by_releases = sorted(repos_with_releases, key=lambda x: x.release_count, reverse=True)[:15]
            
            # Create horizontal bar chart
            _, ax = plt.subplots(figsize=(12, max(6, len(top_by_releases) * 0.4)))
            
            names = [r.name for r in top_by_releases]
            release_counts = [r.release_count for r in top_by_releases]
            
            # Create horizontal bar chart
            bars = ax.barh(names, release_counts, color=chart_colors[2])
            
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
        
        logger.info("Detailed charts saved to reports directory")

                        