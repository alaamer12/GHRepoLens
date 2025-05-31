from asyncio.log import logger
import os
import shutil
from zipfile import Path
from models import RepoStats
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from config import ThemeConfig, DefaultTheme
from charts import CreateDetailedCharts


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
        static_dir = Path("reports/static/assets")
        os.makedirs(static_dir, exist_ok=True)
        
        for asset in assets_dir.glob("*"):
            try:
                shutil.copy(asset, static_dir / asset.name)
                logger.info(f"Copied asset {asset.name} to {static_dir}")
            except Exception as e:
                logger.error(f"Failed to copy asset {asset.name}: {str(e)}")
    
    def create_visualizations(self, all_stats: List[RepoStats]) -> None:
        """Generate visual reports with charts and graphs"""
        logger.info("Generating visual report")
        
        # Store all_stats as an instance attribute for later use
        self.all_stats = all_stats
        
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
        # Verify total LOC for sanity check
        total_loc_sum = sum(stats.total_loc for stats in non_empty_repos)
        logger.info(f"Total LOC across all repositories: {total_loc_sum:,}")
        
        # Collect language data more carefully
        all_languages = defaultdict(int)
        for stats in non_empty_repos:
            # Skip repositories with anomalous language data
            if sum(stats.languages.values()) > stats.total_loc * 1.1:  # Allow 10% margin for rounding
                logger.warning(f"Repository {stats.name} has inconsistent language data. Skipping for language chart.")
                continue
                
            for lang, loc in stats.languages.items():
                all_languages[lang] += loc
        
        # Verify and log the total sum of language-specific LOC
        lang_loc_sum = sum(all_languages.values())
        logger.info(f"Sum of language-specific LOC: {lang_loc_sum:,}")
        
        # If there's still a significant discrepancy, scale the language values
        if lang_loc_sum > total_loc_sum * 1.5:  # If language sum is more than 50% higher than total
            scaling_factor = total_loc_sum / lang_loc_sum
            logger.warning(f"Scaling language LOC by factor of {scaling_factor:.2f} to match total LOC")
            all_languages = {lang: int(loc * scaling_factor) for lang, loc in all_languages.items()}
        
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
        
        # Ensure the static directory exists
        static_dir = Path("reports/static")
        os.makedirs(static_dir, exist_ok=True)
        
        # Also create individual static charts for detailed analysis
        detailed_charts = CreateDetailedCharts(self.all_stats, self.theme, self.reports_dir)
        detailed_charts.create()
        
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
        head_section = self._create_head_section()
        body_start = self._create_body_start(timestamp)
        # Add creator section right after the header section
        creator_section = self._create_creator_section()
        
        stats_section = self._create_stats_section()
        
        charts_section = self._create_charts_section()
        # NEW: Add links to additional static charts with enhanced animations
        additional_charts_section = self._create_additional_charts_section()

        footer_section = self._create_footer_section(timestamp)

        # JavaScript section with complex escaping issues
        js_part1 = self._create_js_part1()
        js_part2 = self._create_js_part2(fig, total_repos, total_loc, total_stars, active_repos)
        # Add repository table JavaScript with enhanced animations
        repo_table_js = self._create_repo_table_js(repos_json)
                
        js_part3 = self._create_js_part3(repo_table_js)
        
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
    
    def _create_head_section(self) -> str:
        """Create the head section of the HTML file"""
        head = f"""<!DOCTYPE html>
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
        
        return head

    def _create_body_start(self, timestamp: str) -> str:
        """Create the body start section of the HTML file"""
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
        
        return body_start
    
    def _create_creator_section(self) -> str:
        """Create the creator section of the HTML file"""
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
        return creator_section
    
    def _create_stats_section(self) -> str:
        """Create the stats section of the HTML file"""
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
        return stats_section
    
    def _create_charts_section(self) -> str:
        """Create the charts section of the HTML file"""
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
                
        return charts_section
    
    def _check_chart_exists(self, chart_name: str) -> bool:
        """Check if a chart file exists in the reports directory"""
        chart_path = self.reports_dir / f"{chart_name}.png"
        return chart_path.exists()

    def _get_chart_html(self, chart_name: str, title: str, description: str, color_class: str) -> str:
        """Generate HTML for a chart, with fallback for missing charts"""
        chart_exists = self._check_chart_exists(chart_name)
        
        if chart_exists:
            return f"""
            <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                <div class="p-4">
                    <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-{color_class} dark:group-hover:text-{color_class} transition-colors duration-300">{title}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{description}</p>
                    <a href="{chart_name}.png" target="_blank" class="block relative">
                        <div class="overflow-hidden rounded-lg">
                            <img src="{chart_name}.png" alt="{title}" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                        </div>
                        <div class="absolute inset-0 bg-{color_class}/0 group-hover:bg-{color_class}/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                            <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-{color_class} font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                                View Full Size
                            </span>
                        </div>
                    </a>
                </div>
            </div>"""
        else:
            return f"""
            <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group">
                <div class="p-4">
                    <h3 class="text-lg font-medium mb-2 dark:text-white text-{color_class} dark:text-{color_class}">{title}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{description}</p>
                    <div class="flex items-center justify-center h-48 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <div class="text-center p-4">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto mb-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p class="text-gray-500 dark:text-gray-400">Chart not available</p>
                            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Not enough data to generate this visualization</p>
                        </div>
                    </div>
                </div>
            </div>"""

    def _create_additional_charts_section(self) -> str:
        """Create the additional charts section of the HTML file"""
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
                        {0}
                        
                        <!-- Language Evolution -->
                        {1}
                        
                        <!-- Quality Heatmap -->
                        {2}
                        
                        <!-- Repository Types -->
                        {3}
                        
                        <!-- Commit Activity -->
                        {4}
                        
                        <!-- Top Repositories -->
                        {5}
                        
                        <!-- Metrics Correlation -->
                        {6}
                        
                        <!-- Topics Word Cloud -->
                        {7}
                        
                        <!-- Active vs Inactive Age -->
                        {8}
                    </div>
                </div>""".format(
                    self._get_chart_html("repository_timeline", "Repository Timeline", "Chronological view of repository creation and last commit dates", "primary"),
                    self._get_chart_html("language_evolution", "Language Evolution", "How language usage has changed over time", "secondary"),
                    self._get_chart_html("quality_heatmap", "Maintenance Quality Matrix", "Quality factors across top repositories", "accent"),
                    self._get_chart_html("repo_types_distribution", "Repository Types", "Distribution of different repository types", "green-500"),
                    self._get_chart_html("commit_activity_heatmap", "Commit Activity", "Heatmap of commit activity by month and year", "blue-500"),
                    self._get_chart_html("top_repos_metrics", "Top Repositories", "Top repositories by various metrics", "purple-500"),
                    self._get_chart_html("metrics_correlation", "Metrics Correlation", "Correlation between different repository metrics", "pink-500"),
                    self._get_chart_html("topics_wordcloud", "Topics Word Cloud", "Visual representation of repository topics", "yellow-500"),
                    self._get_chart_html("active_inactive_age", "Active vs Inactive Repos", "Age distribution of active vs inactive repositories", "teal-500")
                )
        
        return additional_charts_section
    
    def _create_footer_section(self, timestamp: str) -> str:
        """Create the footer section of the HTML file"""
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

        return footer_section
    
    def _create_js_part1(self) -> str:
        """Create the first part of the JavaScript section of the HTML file"""
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
        
        return js_part1
    
    def _create_js_part2(self, fig, total_repos, total_loc, total_stars, active_repos) -> str:
        """Create the second part of the JavaScript section of the HTML file"""
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
  
        return js_part2
    
    def _create_repo_table_js(self, repos_json: str) -> str:
        """Create the JavaScript section for the repository table"""
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
        return repo_table_js
    
    def _create_js_part3(self, repo_table_js: str) -> str:
        """Create the third part of the JavaScript section of the HTML file"""
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
        return js_part3