"""
GitHub Repository Visualizer Module

This module generates interactive visualizations and dashboards for repository analysis.
It creates HTML reports with charts, graphs, and insights from repository data.
"""

import os
import shutil
from zipfile import Path
from models import RepoStats
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional, Dict
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import json
from config import ThemeConfig, DefaultTheme
from console import logger
from charts import CreateDetailedCharts
from repo_analyzer import PersonalRepoAnalysis, OrganizationRepoAnalysis


def _get_ext_to_lang_mapping() -> dict:
    """Get the mapping of file extensions to languages"""
    return {
        ".py": "Python",
        ".js": "JavaScript",
        ".tsx": "TypeScript",
        ".ts": "TypeScript",
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
        ".jsx": "JavaScript",
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
        ".zig": "Zig"
    }


class GithubVisualizer:
    """Class responsible for creating visualizations from GitHub repository data"""

    def __init__(self, username: str, reports_dir: Path, theme: Optional[ThemeConfig] = None):
        """Initialize the visualizer with username and reports directory"""
        self.all_stats: Optional[List[RepoStats]] = None
        self.username = username
        self.reports_dir = reports_dir
        self.assets_dir = Path("assets")  # Changed from Path("static") / "assets" to just "assets"
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

    def _process_repo_language(self, stats: RepoStats, all_languages: dict) -> None:
        """Process language data for a single repository"""
        # Check if repository has any valid language data
        lang_sum = sum(stats.languages.values())

        if lang_sum == 0 or lang_sum > stats.total_loc * 1.1:
            # Either no language data or inconsistent data (>10% over total)
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
            # Repository has consistent language data
            for lang, loc in stats.languages.items():
                all_languages[lang] += loc

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

        return inferred_language

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
        timestamp = datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        # Create statistics
        total_repos = len(non_empty_repos)
        total_loc = f"{sum(s.total_loc for s in non_empty_repos):,}"
        total_stars = f"{sum(s.stars for s in non_empty_repos):,}"
        active_repos = sum(1 for s in non_empty_repos if s.is_active)

        # Log information about repos_with_unknown_language
        if hasattr(self, 'repos_with_unknown_language'):
            logger.info(
                f"In _generate_dashboard_html: Found repos_with_unknown_language with {len(self.repos_with_unknown_language)} entries")
            logger.info(f"  Content: {sorted(list(self.repos_with_unknown_language))}")
        else:
            logger.warning("In _generate_dashboard_html: repos_with_unknown_language attribute not found!")

        # Prepare repository data for the table
        repos_table_data = []
        languages_in_table = {}

        for repo in non_empty_repos:
            # Check if this repository has an inferred language
            if hasattr(self, 'inferred_languages') and repo.name in self.inferred_languages:
                language = self.inferred_languages[repo.name]
            # Otherwise check if it's marked as Unknown
            elif hasattr(self, 'repos_with_unknown_language') and repo.name in self.repos_with_unknown_language:
                language = "Unknown"
            # Fallback to the original primary language
            else:
                language = repo.primary_language or "Unknown"

            # Log individual language decisions
            if repo.primary_language != language:
                logger.info(
                    f"Repository {repo.name}: Overriding primary_language '{repo.primary_language}' with '{language}'")

            # Track languages for later summary
            languages_in_table[repo.name] = language

            repos_table_data.append({
                "name": repo.name,
                "language": language,
                "stars": repo.stars,
                "loc": repo.total_loc,
                "is_active": repo.is_active,
                "maintenance": f"{repo.maintenance_score:.1f}",
                "url": f"https://github.com/{self.username}/{repo.name}"  # Add GitHub URL
            })

        # Log summary of languages in table
        logger.info("Summary of languages in repository table:")
        for repo_name, language in sorted(languages_in_table.items()):
            logger.info(f"  {repo_name}: {language}")

        # Convert to JSON for JavaScript
        repos_json = json.dumps(repos_table_data)

        # Create parts of HTML separately to avoid f-string nesting issues
        head_section = self._create_head_section()
        body_start = self._create_body_start(timestamp)
        # Add creator section right after the header section
        creator_section = self._create_creator_section()
        # Add repository type tabs after creator section
        repo_type_tabs = self._create_repo_type_tabs()

        stats_section = self._create_stats_section()

        charts_section = self._create_charts_section()
        # NEW: Add links to additional static charts with enhanced animations
        additional_charts_section = self._create_additional_charts_section()

        # Add Chart Modal Container with iframe support for interactive charts
        chart_modal_container = self._create_chart_modal_container()

        footer_section = self._create_footer_section(timestamp)

        # JavaScript section with complex escaping issues
        js_part1 = self._create_js_part1()
        js_part2 = self._create_js_part2(fig, total_repos, total_loc, total_stars, active_repos)
        # Add repository table JavaScript with enhanced animations
        repo_table_js = self._create_repo_table_js(repos_json)
        # Add repository type tabs JavaScript
        repo_tabs_js = self._create_repo_tabs_js()

        js_part3 = self._create_js_part3(repo_table_js, repo_tabs_js)

        # Combine all parts
        html_content = "\n".join([
            head_section,
            body_start,
            creator_section,
            repo_type_tabs,  # Add repo type tabs to HTML content
            stats_section,
            charts_section,
            additional_charts_section,
            chart_modal_container,
            footer_section,
            js_part1,
            js_part2,
            js_part3
        ])

        return html_content

    @staticmethod
    def _create_chart_modal_container() -> str:
        """Create the chart modal container"""
        return """
                <!-- Modal for full-screen chart view with interactive content -->
                <div class="chart-modal" id="chartModal">
                    <div class="chart-modal-content">
                        <button class="chart-modal-close" id="chartModalClose">&times;</button>
                        <div class="chart-modal-iframe-container">
                            <iframe class="chart-modal-iframe" id="chartModalIframe" src="" frameborder="0" allowfullscreen></iframe>
                        </div>
                        <div class="chart-modal-info">
                            <h3 class="chart-modal-title" id="chartModalTitle"></h3>
                            <p class="chart-modal-description" id="chartModalDescription"></p>
                        </div>
                    </div>
                </div>
        """

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
            <link rel="icon" type="image/png" href="static/assets/favicon.png">
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

                /* Chart Modal Styles with iframe support */
                .chart-modal {{
                    visibility: hidden;
                    position: fixed;
                    top: 0;
                    right: 0;
                    bottom: 0;
                    left: 0;
                    background-color: rgba(0, 0, 0, 0.85);
                    z-index: 9999;
                    opacity: 0;
                    backdrop-filter: blur(5px);
                    transition: all 0.4s ease-in-out;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}

                .chart-modal.active {{
                     visibility: visible;
                    opacity: 1;
                }}

                .chart-modal-content {{
                   background-color: white;
                    width: 90%;
                    max-width: 1200px;
                    height: 85vh;
                    margin: 0 auto;
                    border-radius: 16px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
                    overflow-y: auto !important;
                    display: flex;
                    flex-direction: column;
                    transform: scale(0.95);
                    opacity: 0;
                    transition: all 0.3s ease-in-out;
                }}
                
                 .chart-modal.active .chart-modal-content {{
                    transform: scale(1);
                    opacity: 1;
                }}

                .dark .chart-modal-content {{
                    background-color: #1f2937;
                    color: white;
                }}

                .chart-modal-iframe-container {{
                     flex: 1;
                    overflow-y: auto !important;
                    overflow-x: auto !important;
                    scroll-behavior: smooth;
                    display: block;
                }}

                .chart-modal-iframe {{
                      width: 100%;
                    height: 100%;
                    border: none;
                    transition: opacity 0.3s ease;
                    display: block;
                }}

                .chart-modal-close {{
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    font-size: 24px;
                    color: #fff;
                    background: rgba(255, 255, 255, 0.2);
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    z-index: 10;
                    backdrop-filter: blur(4px);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
                    transition: all 0.3s cubic-bezier(0.19, 1, 0.22, 1);
                }}

                .dark .chart-modal-close {{
                    color: white;
                    background: #374151;
                }}

                .chart-modal-close:hover {{
                     transform: scale(1.1) rotate(90deg);
                    background-color: rgba(255, 255, 255, 0.3);
                }}

                .dark .chart-modal-close:hover {{
                    background-color: #4b5563;
                }}

                .chart-modal-info {{
                    padding: 20px;
                    background: linear-gradient(to top, rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.3), transparent);
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    transform: translateY(100%);
                    opacity: 0;
                    transition: all 0.6s cubic-bezier(0.19, 1, 0.22, 1);
                    transition-delay: 0.1s;
                    z-index: 5;
                }}

                .dark .chart-modal-info {{
                    border-top: 1px solid #374151;
                }}

                .chart-modal-title {{
                     font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 8px;
                    color: white;
                }}

                .chart-modal-description {{
                    font-size: 1rem;
                    color: rgba(255, 255, 255, 0.8);
                }}

                .dark .chart-modal-description {{
                    color: #9ca3af;
                }}

                /* Custom scrollbar */
                ::-webkit-scrollbar {{
                    width: 12px !important;
                    height: 12px !important;
                    display: block !important;
                }}

                ::-webkit-scrollbar-track {{
                    background: #f1f1f1;
                    border-radius: 4px;
                    margin: 2px;
                    display: block !important;
                }}

                .dark ::-webkit-scrollbar-track {{
                    background: #374151;
                }}

                ::-webkit-scrollbar-thumb {{
                     background: linear-gradient(135deg, rgba(79, 70, 229, 0.9) 0%, rgba(124, 58, 237, 0.9) 50%, rgba(249, 115, 22, 0.9) 100%) !important;
                    border-radius: 6px;
                    border: 2px solid transparent;
                    background-clip: padding-box;
                    transition: all 0.3s ease;
                    display: block !important;
                    min-height: 40px;
                }}

                ::-webkit-scrollbar-thumb:hover {{
                    background: linear-gradient(135deg, rgba(79, 70, 229, 1) 0%, rgba(124, 58, 237, 1) 50%, rgba(249, 115, 22, 1) 100%) !important;
                }}

                .dark ::-webkit-scrollbar-thumb {{
                     background: linear-gradient(135deg, rgba(79, 70, 229, 0.8) 0%, rgba(124, 58, 237, 0.8) 50%, rgba(249, 115, 22, 0.8) 100%) !important;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}

                .dark ::-webkit-scrollbar-thumb:hover {{
                    background: linear-gradient(135deg, rgba(79, 70, 229, 1) 0%, rgba(124, 58, 237, 1) 50%, rgba(249, 115, 22, 1) 100%) !important;
                }}
                
                /* Smooth scrolling for the entire page */
                html {{
                    scroll-behavior: smooth;
                    overflow-y: auto !important;
                }}
                
                 /* Styles for scrollable tables and sections */
                .scrollable-table-container {{
                    max-height: 500px;
                    overflow-y: auto !important;
                    overflow-x: hidden;
                    border-radius: 0.5rem;
                    position: relative;
                    scrollbar-width: thin;
                    scrollbar-color: var(--primary) var(--scrollbar-track);
                    padding-right: 0.25rem;
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
                    0% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
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

                /* Chart Modal Styles */
                .chart-modal {{
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.85);
                    z-index: 1000;
                    backdrop-filter: blur(5px);
                    opacity: 0;
                    transition: opacity 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                }}

                .chart-modal.active {{
                   display: flex;
                    align-items: center;
                    justify-content: center;
                    opacity: 1;
                }}

                .chart-modal-content {{
                  position: relative;
                    max-width: 90vw;
                    max-height: 90vh;
                    border-radius: 20px;
                    overflow: hidden;
                    box-shadow: 0 25px 50px rgba(0,0,0,0.5);
                    transform: scale(0.8) translateY(20px);
                    opacity: 0;
                    transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                }}

                .chart-modal.active .chart-modal-content {{
                    transform: scale(1) translateY(0);
                    opacity: 1;
                }}

                .chart-modal-image {{
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    display: block;
                }}

                .chart-modal-close {{
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    background: rgba(255,255,255,0.2);
                    border: none;
                    color: white;
                    font-size: 1.5rem;
                    width: 50px;
                    height: 50px;
                    border-radius: 50%;
                    cursor: pointer;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.3);
                    transition: all 0.3s ease;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1010;
                }}

                .chart-modal-close:hover {{
                    background: rgba(255,255,255,0.3);
                    transform: scale(1.1);
                }}

                .chart-modal-info {{
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    background: linear-gradient(transparent, rgba(0,0,0,0.8));
                    color: white;
                    padding: 40px 30px 30px;
                    text-align: center;
                    transform: translateY(100%);
                    opacity: 0;
                    transition: all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                }}

                .chart-modal.active .chart-modal-info {{
                  transform: translateY(0);
                    opacity: 1;
                }}

                .chart-modal-title {{
                    font-size: 1.5rem;
                    font-weight: 300;
                    margin-bottom: 0.5rem;
                }}

                .chart-modal-description {{
                      opacity: 0.8;
                    font-size: 0.9rem;
                }}
                
                /* Force scrollbar display for Firefox */
                * {{
                    scrollbar-width: thin;
                    scrollbar-color: var(--primary) var(--scrollbar-track);
                }}

                /* Additional scrollbar styling for modal in dark mode */
                .chart-modal.active .chart-modal-content::-webkit-scrollbar,
                .chart-modal.active .chart-modal-iframe-container::-webkit-scrollbar {{
                    width: 14px !important;
                    display: block !important;
                }}

                .chart-modal.active .chart-modal-content::-webkit-scrollbar-thumb,
                .chart-modal.active .chart-modal-iframe-container::-webkit-scrollbar-thumb {{
                    background: linear-gradient(135deg, rgba(124, 58, 237, 0.9) 0%, rgba(249, 115, 22, 0.9) 100%) !important;
                    border: 2px solid #1f2937;
                    min-height: 50px;
                }}

                /* Make iframe container take full height */
                .chart-modal.active .chart-modal-iframe-container {{
                    min-height: 400px;
                    height: 75vh;
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
                        <img src="static/assets/light_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>
                    <div class="absolute inset-0 w-full h-full opacity-20 hidden dark:block">
                        <img src="static/assets/dark_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>

                    <div class="relative p-6 md:p-10 text-center z-10">
                        <h1 class="text-3xl md:text-5xl font-light text-white mb-4 animate-bounce-in">📊 GitHub Repository Analysis</h1>
                        <p class="text-lg text-white/90 animate-fade-in">
                            User: <span class="font-semibold">{self.username}</span> | Generated: {timestamp}
                        </p>
                    </div>
                </div>"""

        return body_start

    @staticmethod
    def _create_creator_section() -> str:
        """Create the creator section of the HTML file"""
        creator_section = """
            <!-- Creator Section - Modern & Compact -->
            <div id="creator-section" class="relative overflow-hidden bg-white/10 dark:bg-gray-800/20 backdrop-blur-sm rounded-xl shadow-lg mb-6 transition-all duration-500 group">
                <div class="absolute inset-0 bg-gradient-to-br from-primary/5 via-secondary/5 to-accent/5 dark:from-primary/10 dark:via-secondary/10 dark:to-accent/10 opacity-80"></div>

                <div class="relative z-10 flex items-center p-4 gap-4">
                    <!-- Creator Image & Name -->
                    <div class="relative w-16 h-16 rounded-full overflow-hidden shadow-lg border-2 border-primary/30 creator-profile-img" data-aos="zoom-in" data-aos-delay="100">
                        <img src="static/assets/alaamer.jpg" alt="Amr Muhamed" class="w-full h-full object-cover" />
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
                                    <span class="animate-typing">Creator of GHRepoLens 😄</span>
                                </p>
                            </div>

                            <!-- Social Links -->
                            <div class="flex gap-3" data-aos="fade-left" data-aos-delay="250">
                                <a href="https://github.com/alaamer12" target="_blank"
                                   class="social-icon p-2 rounded-full bg-gray-800 text-white hover:bg-primary shadow-md transition-all duration-300 hover:scale-110 hover:rotate-6 transform"
                                   aria-label="GitHub Profile">
                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                                    </svg>
                                </a>
                                <a href="https://www.linkedin.com/in/amr-muhamed-0b0709265/" target="_blank"
                                   class="social-icon p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 shadow-md transition-all duration-300 hover:scale-110 hover:-rotate-6 transform"
                                   aria-label="LinkedIn Profile">
                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.454C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.225 0z"/>
                                    </svg>
                                </a>
                                <a href="https://portfolio-qiw8.vercel.app/" target="_blank"
                                   class="social-icon p-2 rounded-full bg-emerald-600 text-white hover:bg-emerald-700 shadow-md transition-all duration-300 hover:scale-110 hover:rotate-6 transform"
                                   aria-label="Portfolio Website">
                                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm1 16.057v-3.05c2.083.129 4.066-.534 5.18-1.412-1.381 2.070-3.482 3.678-5.18 4.462zm-1 1.05c-4.986 0-9.047-4.061-9.047-9.07 0-4.99 4.061-9.044 9.047-9.044 4.986 0 9.047 4.054 9.047 9.044 0 4.37-3.099 8.008-7.197 8.851v-2.137c1.816-.471 3.857-1.932 3.857-6.001 0-2.186-.5-3.99-1.57-4.814.324-1.045.345-2.717-.42-3.818-.345-.003-1.208.154-2.679 1.135-.768-.22-1.59-.334-2.429-.334-.84 0-1.662.114-2.428.334-1.472-.98-2.343-1.138-2.688-1.135-.765 1.101-.735 2.773-.419 3.818-1.074.825-1.564 2.628-1.564 4.814 0 4.062 2.074 5.53 3.846 6.001v2.137c-4.098-.843-7.197-4.481-7.197-8.851 0-4.99 4.061-9.044 9.047-9.044 4.986 0 9.047 4.054 9.047 9.044 0 5.009-4.061 9.07-9.047 9.07z"/>
                                    </svg>
                                </a>
                            </div>
                        </div>

                        <!-- Technologies Row -->
                        <div class="mt-2 flex flex-wrap gap-2" data-aos="fade-up" data-aos-delay="300">
                            <a href="https://www.python.org" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">Python</span>
                            </a>
                            <a href="https://developer.mozilla.org/en-US/docs/Web/JavaScript" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">JavaScript</span>
                            </a>
                            <a href="https://reactjs.org" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">React</span>
                            </a>
                            <a href="https://en.wikipedia.org/wiki/Data_analysis" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">Data Analysis</span>
                            </a>
                            <a href="https://en.wikipedia.org/wiki/Machine_learning" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">ML</span>
                            </a>
                            <a href="https://docs.github.com/en/rest" target="_blank" rel="noopener noreferrer">
                                <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">GitHub API</span>
                            </a>
                        </div>
                    </div>
                </div>
            </div>

            <script>
            document.addEventListener('DOMContentLoaded', function() {{
                if (typeof gsap !== 'undefined') {{
                    const creatorSection = document.getElementById('creator-section');
                    if (creatorSection) {{
                        creatorSection.addEventListener('mouseenter', function() {{
                            gsap.to(this, {{
                                scale: 1.02,
                                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
                                duration: 0.3,
                                ease: 'power2.out'
                            }});
                            gsap.to(this.querySelectorAll('.tech-badge'), {{
                                stagger: 0.05,
                                y: -4,
                                scale: 1.1,
                                duration: 0.2,
                                ease: 'back.out(1.7)'
                            }});
                        }});
                        creatorSection.addEventListener('mouseleave', function() {{
                            gsap.to(this, {{
                                scale: 1,
                                boxShadow: 'none',
                                duration: 0.3,
                                ease: 'power2.out'
                            }});
                            gsap.to(this.querySelectorAll('.tech-badge'), {{
                                stagger: 0.05,
                                y: 0,
                                scale: 1,
                                duration: 0.2,
                                ease: 'back.out(1.7)'
                            }});
                        }});
                    }}
                }}
            }});
            </script>
        """
        return creator_section

    def _create_repo_type_tabs(self) -> str:
        """Create tab buttons to switch between personal and organization repositories"""
        # If there are no organization repositories, don't show the tabs
        if not self.has_org_repos:
            return ""

        repo_type_tabs = """
            <!-- Repository Type Tabs - Toggle between Personal and Organization repositories -->
            <div data-aos="fade-up" data-aos-duration="600" class="mb-8">
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 flex flex-col sm:flex-row justify-between items-center">
                    <div class="flex-1">
                        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3 sm:mb-0">Repository Analysis Type</h3>
                    </div>
                    
                    <!-- Tab buttons with modern styling -->
                    <div class="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1 shadow-inner relative overflow-hidden">
                        <!-- Personal repositories tab -->
                        <button id="personal-repos-tab" class="flex items-center justify-center px-6 py-2 text-sm font-medium rounded-md relative z-10 transition-all duration-300 text-gray-900 dark:text-white active-tab">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                            Personal
                        </button>
                        
                        <!-- Organizations repositories tab -->
                        <button id="org-repos-tab" class="flex items-center justify-center px-6 py-2 text-sm font-medium rounded-md relative z-10 transition-all duration-300 text-gray-500 dark:text-gray-400">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                            </svg>
                            Organizations
                        </button>
                        
                        <!-- Active indicator pill that slides between tabs -->
                        <span id="tab-indicator" class="absolute inset-y-1 left-1 bg-primary/90 dark:bg-primary rounded-md transition-all duration-300 shadow-md"></span>
                    </div>
                </div>
                
                <!-- Current view indicator -->
                <div class="mt-3 text-sm text-center">
                    <div class="inline-flex items-center bg-primary/10 text-primary dark:bg-primary/20 px-3 py-1 rounded-full">
                        <span id="current-view-icon" class="mr-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                        </span>
                        <span id="current-view-text">Viewing Personal Repository Stats</span>
                    </div>
                </div>
            </div>
        """
        return repo_type_tabs

    @staticmethod
    def _create_stats_section() -> str:
        """Create the stats section of the HTML file"""
        stats_section = f"""<!-- Stats overview with enhanced animations -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                    <!-- Repositories count - Represents collection/organization -->
                    <div data-aos="zoom-in" data-aos-delay="100" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-primary shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-primary">Total Repositories</p>
                                <p id="repo-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-primary transform group-hover:animate-pulse">0</p>
                            </div>
                            <!-- Stack of folders animation - representing organized collection -->
                            <div class="relative bg-primary/10 rounded-full p-3 transition-all duration-500 group-hover:bg-primary/20">
                                <svg class="w-8 h-8 text-primary transition-all duration-700 group-hover:scale-125" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Floating mini boxes to represent multiple repos -->
                                <div class="absolute -top-1 -right-1 w-2 h-2 bg-primary rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.1s;"></div>
                                <div class="absolute -top-2 right-1 w-1.5 h-1.5 bg-primary/70 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.2s;"></div>
                                <div class="absolute top-0 -right-2 w-1 h-1 bg-primary/50 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.3s;"></div>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-primary to-primary/50 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1000"></div>
                        <div class="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                    </div>

                    <!-- Total LOC - Represents typing/code flowing -->
                    <div data-aos="zoom-in" data-aos-delay="200" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-secondary shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-secondary">Total Lines of Code</p>
                                <!-- Counter animation simulating incrementing lines -->
                                <p id="loc-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-secondary relative overflow-hidden">
                                    <span class="inline-block transform transition-transform duration-700 group-hover:translate-y-[-100%]">0</span>
                                </p>
                            </div>
                            <!-- Typing animation - code brackets moving -->
                            <div class="relative bg-secondary/10 rounded-full p-3 transition-all duration-500 group-hover:bg-secondary/20">
                                <svg class="w-8 h-8 text-secondary transition-all duration-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Flowing code dots animation -->
                                <div class="absolute top-2 left-1 w-1 h-1 bg-secondary rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0s;"></div>
                                <div class="absolute top-4 left-2 w-1 h-1 bg-secondary/70 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.2s;"></div>
                                <div class="absolute top-6 left-3 w-1 h-1 bg-secondary/50 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.4s;"></div>
                            </div>
                        </div>
                        <!-- Progressive filling bar like code compilation -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-secondary via-secondary/70 to-secondary/50 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1500 ease-out"></div>
                        <div class="absolute inset-0 bg-secondary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg"></div>
                    </div>

                    <!-- Total Stars - Represents appreciation/twinkling -->
                    <div data-aos="zoom-in" data-aos-delay="300" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-accent shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-accent">Total Stars</p>
                                <!-- Glowing number effect for stars -->
                                <p id="stars-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-accent group-hover:drop-shadow-lg group-hover:filter group-hover:brightness-125">0</p>
                            </div>
                            <!-- Twinkling star animation -->
                            <div class="relative bg-accent/10 rounded-full p-3 transition-all duration-500 group-hover:bg-accent/20">
                                <svg class="w-8 h-8 text-accent transition-all duration-1000 group-hover:scale-125 group-hover:rotate-180 group-hover:drop-shadow-lg" fill="currentColor" stroke="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                </svg>
                                <!-- Sparkle effects around the star -->
                                <div class="absolute -top-1 -left-1 w-1 h-1 bg-accent rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0s;"></div>
                                <div class="absolute -top-2 -right-1 w-1.5 h-1.5 bg-accent/80 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.3s;"></div>
                                <div class="absolute -bottom-1 -left-2 w-1 h-1 bg-accent/60 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.6s;"></div>
                                <div class="absolute -bottom-2 -right-2 w-2 h-2 bg-accent/40 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.9s;"></div>
                            </div>
                        </div>
                        <!-- Shimmering progress bar like starlight -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-accent via-yellow-300 to-accent transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1200 ease-out"></div>
                        <div class="absolute inset-0 bg-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg group-hover:animate-pulse"></div>
                    </div>

                    <!-- Active Repositories - Represents life/activity/heartbeat -->
                    <div data-aos="zoom-in" data-aos-delay="400" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-green-500 shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-green-500">Active Repositories</p>
                                <!-- Heartbeat-like pulsing number -->
                                <p id="active-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-green-500 group-hover:animate-pulse">0</p>
                            </div>
                            <!-- Heartbeat/pulse animation for activity -->
                            <div class="relative bg-green-500/10 rounded-full p-3 transition-all duration-500 group-hover:bg-green-500/20">
                                <svg class="w-8 h-8 text-green-500 transition-all duration-700 group-hover:scale-125" fill="currentColor" stroke="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Ripple effects for activity -->
                                <div class="absolute inset-0 rounded-full bg-green-500/20 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700"></div>
                                <div class="absolute inset-1 rounded-full bg-green-500/15 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700" style="animation-delay: 0.3s;"></div>
                                <div class="absolute inset-2 rounded-full bg-green-500/10 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700" style="animation-delay: 0.6s;"></div>
                            </div>
                        </div>
                        <!-- Rhythmic progress bar like activity monitor -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-green-500 via-green-400 to-green-300 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1000 ease-in-out"></div>
                        <div class="absolute inset-0 bg-green-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg"></div>
                        <!-- Subtle heartbeat lines -->
                        <div class="absolute top-4 right-4 opacity-0 group-hover:opacity-30 transition-opacity duration-500">
                            <div class="w-8 h-0.5 bg-green-500/50 group-hover:animate-pulse"></div>
                            <div class="w-6 h-0.5 bg-green-500/30 mt-1 group-hover:animate-pulse" style="animation-delay: 0.2s;"></div>
                            <div class="w-4 h-0.5 bg-green-500/20 mt-1 group-hover:animate-pulse" style="animation-delay: 0.4s;"></div>
                        </div>
                    </div>
                </div>"""
        return stats_section

    def _create_charts_section(self) -> str:
        """Create the charts section of the HTML file"""
        # Generate personal repository charts
        personal_charts = self.prepo_analysis.create_charts_section()

        # Generate organization repository charts if applicable
        org_charts = ""
        if self.has_org_repos and self.orepo_analysis:
            org_charts = self.orepo_analysis.create_charts_section()

        # If there are organization repositories, we'll include both sections
        # The repo_tabs_js will handle showing/hiding these sections
        if self.has_org_repos:
            return f"""
            <!-- Personal Repository Charts (visible by default) -->
            <div id="personal-repos-content">
                {personal_charts}
            </div>
            
            <!-- Organization Repository Charts (hidden by default) -->
            <div id="org-repos-content" class="hidden">
                {org_charts}
            </div>
            """
        else:
            # If there are no organization repositories, just return the personal charts
            return personal_charts

    def _check_chart_exists(self, chart_name: str) -> bool:
        """Check if a chart file exists in the reports directory"""
        chart_path = self.reports_dir / f"{chart_name}.png"
        # Add logging to debug the issue
        logger.info(f"Checking if chart exists at: {chart_path}")
        exists = chart_path.exists()
        logger.info(f"Chart {chart_name}.png exists: {exists}")

        # Always return True to include the section with placeholder images when needed
        # The _get_chart_html method will handle displaying a placeholder if the file doesn't exist
        return True

    def _get_chart_html(self, chart_name: str, title: str, description: str, color_class: str) -> str:
        """Generate HTML for a chart, with fallback for missing charts"""
        chart_path = self.reports_dir / f"{chart_name}.png"
        chart_exists = chart_path.exists()

        if chart_exists:
            # Use HTML file for interactive version instead of PNG
            return f"""
            <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                <div class="p-4">
                    <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-{color_class} dark:group-hover:text-{color_class} transition-colors duration-300">{title}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{description}</p>
                    <div class="chart-item cursor-pointer block relative" 
                         data-chart-src="{chart_name}.html" 
                         data-chart-title="{title}" 
                         data-chart-description="{description}">
                        <div class="overflow-hidden rounded-lg">
                            <img src="{chart_name}.png" alt="{title}" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                        </div>
                        <div class="absolute inset-0 bg-{color_class}/0 group-hover:bg-{color_class}/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                            <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-{color_class} font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                                View Interactive Chart
                            </span>
                        </div>
                    </div>
                </div>
            </div>"""
        else:
            logger.warning(f"Chart {chart_name} not found. Using placeholder.")
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
        # Log which charts exist before creating the section
        chart_names = ["repository_timeline", "repo_creation_timeline", "quality_heatmap",
                       "repo_types_distribution", "commit_activity_heatmap", "top_repos_metrics",
                       "infrastructure_metrics", "documentation_quality", "active_inactive_age"]

        logger.info("Checking charts for additional section:")
        for chart_name in chart_names:
            exists = self._check_chart_exists(chart_name)
            logger.info(f"- {chart_name}: {'✓' if exists else '✗'}")

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
            self._get_chart_html("repository_timeline", "Repository Timeline",
                                 "Chronological view of repository creation and last commit dates", "primary"),
            self._get_chart_html("repo_creation_timeline", "Repository Creation Timeline",
                                 "When repositories were created over time", "secondary"),
            self._get_chart_html("quality_heatmap", "Maintenance Quality Matrix",
                                 "Quality factors across top repositories", "accent"),
            self._get_chart_html("repo_types_distribution", "Repository Types",
                                 "Distribution of different repository types", "green-500"),
            self._get_chart_html("commit_activity_heatmap", "Commit Activity",
                                 "Heatmap of commit activity by month and year", "blue-500"),
            self._get_chart_html("top_repos_metrics", "Top Repositories", "Top repositories by various metrics",
                                 "purple-500"),
            self._get_chart_html("infrastructure_metrics", "Infrastructure Metrics",
                                 "Analysis of repository infrastructure and quality", "pink-500"),
            self._get_chart_html("documentation_quality", "Documentation Quality",
                                 "Quality of documentation across repositories", "yellow-500"),
            self._get_chart_html("active_inactive_age", "Active vs Inactive Repos",
                                 "Age distribution of active vs inactive repositories", "teal-500")
        )

        return additional_charts_section

    @staticmethod
    def _create_footer_section(timestamp: str) -> str:
        """Create the footer section of the HTML file with enhanced style and dynamic timestamp"""
        footer_section = f"""
        <!-- Footer with enhanced style and animation -->
        <div data-aos="fade-up" data-aos-duration="800" class="mt-12 text-center border-none">
            <div class="py-6 px-8 opacity-80 border-none bg-none">
                <p class="flex items-center justify-center font-medium">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3 
                        dark:text-teal-400 
                        text-teal-700
                        animate-pulse-slow 
                        opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span class="relative">
                        <span class="mr-1 opacity-100 bg-clip-text text-transparent 
                            bg-gradient-to-r from-teal-400 to-blue-500 font-semibold
                            dark:bg-gradient-to-r dark:from-teal-400 dark:to-blue-500
                            bg-gradient-to-r from-teal-500 via-cyan-400 to-blue-600
                            dark:bg-clip-text dark:text-transparent
                        ">
                            Generated with GHRepoLens
                        </span>
                        <span class="inline-block ml-1 dark:text-white">• {timestamp}</span>
                        <span class="absolute -bottom-1 left-0 w-full h-px bg-gradient-to-r from-transparent via-teal-500/50 to-transparent"></span>
                    </span>
                </p>
            </div>
        </div>
        </div>"""
        return footer_section

    @staticmethod
    def _create_js_part1() -> str:
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
                            'paper_bgcolor': '#ffffff',
                            'plot_bgcolor': '#ffffff',
                            'font.color': '#111827'
                        }});
                    }}

                    // Update scrollbar colors based on theme
                    if (document.documentElement.classList.contains('dark')) {{
                        document.documentElement.style.setProperty('--scrollbar-track', '#374151');
                    }} else {{
                        document.documentElement.style.setProperty('--scrollbar-track', '#f1f1f1');
                    }}
                }});

                // Plot the main dashboard with animation
                var plotData = {fig.to_json()};
                
                // Config options for the plot
                const plotlyConfig = {{
                    responsive: true,
                    displayModeBar: false,  // Hide the modebar for cleaner mobile view
                    scrollZoom: false,      // Disable scroll zoom on mobile
                }};
                
                // Create the plot with proper config options
                Plotly.newPlot('main-dashboard', plotData.data, plotData.layout, plotlyConfig);
                
                // Store the dashboard figure in a global variable for access by other functions
                window.dashboardFigure = document.getElementById('main-dashboard')._fullData;
                
                // Add resize listener for responsive adjustments
                window.addEventListener('resize', function() {{
                    if (window.resizeTimer) clearTimeout(window.resizeTimer);
                    window.resizeTimer = setTimeout(function() {{
                        // Adjust modebar visibility on mobile
                        var modeBarButtons = document.querySelectorAll('.modebar-container');
                        for (var i = 0; i < modeBarButtons.length; i++) {{
                            modeBarButtons[i].style.display = (window.innerWidth <= 768) ? 'none' : 'flex';
                        }}
                    }}, 250);
                }});

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

    @staticmethod
    def _create_repo_table_js(repos_json: str) -> str:
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
                                <a href="${{repo.url}}" target="_blank" class="hover:underline hover:text-primary-dark transition-colors duration-200 flex items-center">
                                    ${{repo.name}}
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd" />
                                    </svg>
                                </a>
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

    def _create_repo_tabs_js(self) -> str:
        """Create the JavaScript for repository type tabs functionality"""
        # If there are no organization repositories, return empty JavaScript
        if not self.has_org_repos:
            return ""

        repo_tabs_js = """
                // Repository Type Tabs Functionality
                function initRepoTypeTabs() {
                    const personalReposTab = document.getElementById('personal-repos-tab');
                    const orgReposTab = document.getElementById('org-repos-tab');
                    const tabIndicator = document.getElementById('tab-indicator');
                    const currentViewText = document.getElementById('current-view-text');
                    const currentViewIcon = document.getElementById('current-view-icon');
                    
                    // Wait for stats counters to be fully animated before storing values
                    setTimeout(() => {
                        // Store the initial personal data state for restoration when switching back
                        window.personalData = null;
                        window.personalLayout = null;
                        window.personalTableData = null;
                        window.personalStats = {
                            repoCount: document.getElementById('repo-count').textContent,
                            locCount: document.getElementById('loc-count').textContent,
                            starsCount: document.getElementById('stars-count').textContent,
                            activeCount: document.getElementById('active-count').textContent
                        };
                        
                        // Store initial table state
                        const tableBody = document.getElementById('repos-table-body');
                        window.personalTableData = tableBody.innerHTML;
                        
                        // Store initial total repos and page info
                        window.totalReposCount = document.getElementById('total-repos-count').textContent;
                        window.pageInfo = document.getElementById('page-info').textContent;
                        
                        // Capture the initial plot data
                        const dashboardElement = document.getElementById('main-dashboard');
                        if (dashboardElement && dashboardElement.data) {
                            window.personalData = JSON.parse(JSON.stringify(dashboardElement.data));
                            window.personalLayout = JSON.parse(JSON.stringify(dashboardElement.layout));
                        }
                        
                        console.log('Personal stats stored:', window.personalStats);
                    }, 2500); // Wait for animations to complete
                    
                    // Personal icon SVG
                    const personalIconSvg = `
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    `;
                    
                    // Organization icon SVG
                    const orgIconSvg = `
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                    `;
                    
                    // Set initial tab indicator position
                    setTimeout(() => {
                        if (personalReposTab && tabIndicator) {
                            tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                        }
                    }, 100);
                    
                    // Personal repos tab click handler
                    if (personalReposTab) {
                        personalReposTab.addEventListener('click', () => {
                            // Update tab styles
                            personalReposTab.classList.add('text-gray-900', 'dark:text-white');
                            personalReposTab.classList.remove('text-gray-500', 'dark:text-gray-400');
                            
                            orgReposTab.classList.remove('text-gray-900', 'dark:text-white');
                            orgReposTab.classList.add('text-gray-500', 'dark:text-gray-400');
                            
                            // Update tab indicator
                            tabIndicator.style.left = '1px';
                            tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                            
                            // Update view text and icon
                            currentViewText.textContent = 'Viewing Personal Repository Stats';
                            currentViewIcon.innerHTML = personalIconSvg;
                            
                            // Update content
                            switchToPersonalRepos();
                        });
                    }
                    
                    // Organization repos tab click handler
                    if (orgReposTab) {
                        orgReposTab.addEventListener('click', () => {
                            // Update tab styles
                            orgReposTab.classList.add('text-gray-900', 'dark:text-white');
                            orgReposTab.classList.remove('text-gray-500', 'dark:text-gray-400');
                            
                            personalReposTab.classList.remove('text-gray-900', 'dark:text-white');
                            personalReposTab.classList.add('text-gray-500', 'dark:text-gray-400');
                            
                            // Update tab indicator
                            tabIndicator.style.left = `${personalReposTab.offsetWidth + 1}px`;
                            tabIndicator.style.width = `${orgReposTab.offsetWidth}px`;
                            
                            // Update view text and icon
                            currentViewText.textContent = 'Viewing Organization Repository Stats';
                            currentViewIcon.innerHTML = orgIconSvg;
                            
                            // Update content
                            switchToOrgRepos();
                        });
                    }
                    
                    // Function to switch to personal repos content (default view)
                    function switchToPersonalRepos() {
                        console.log('Switched to personal repositories view');
                        
                        if (!window.personalStats) {
                            console.error('Personal stats not found!');
                            return;
                        }
                        
                        console.log('Restoring personal stats:', window.personalStats);
                        
                        // Restore personal stats with animation
                        const repoCount = document.getElementById('repo-count');
                        const locCount = document.getElementById('loc-count');
                        const starsCount = document.getElementById('stars-count');
                        const activeCount = document.getElementById('active-count');
                        
                        // First store current state for animation
                        const currentRepoCount = repoCount.textContent;
                        const currentLocCount = locCount.textContent;
                        const currentStarsCount = starsCount.textContent;
                        const currentActiveCount = activeCount.textContent;
                        
                        // Clear current values
                        repoCount.textContent = '0';
                        locCount.textContent = '0';
                        starsCount.textContent = '0';
                        activeCount.textContent = '0';
                        
                        // Then animate to the saved values
                        setTimeout(() => {
                            // Animate repo count
                            animateValue(repoCount, 0, parseInt(window.personalStats.repoCount.replace(/,/g, '')), 800);
                            
                            // Animate LOC count
                            animateValue(locCount, 0, parseInt(window.personalStats.locCount.replace(/,/g, '')), 800);
                            
                            // Animate stars count
                            animateValue(starsCount, 0, parseInt(window.personalStats.starsCount.replace(/,/g, '')), 800);
                            
                            // Animate active count
                            animateValue(activeCount, 0, parseInt(window.personalStats.activeCount.replace(/,/g, '')), 800);
                        }, 100);
                        
                        // Restore original chart if we have saved data
                        if (window.personalData && window.personalLayout) {
                            const plotlyConfig = {
                                responsive: true,
                                displayModeBar: false,
                                scrollZoom: false
                            };
                            
                            Plotly.newPlot('main-dashboard', window.personalData, window.personalLayout, plotlyConfig);
                        }
                        
                        // Restore table data
                        if (window.personalTableData) {
                            document.getElementById('repos-table-body').innerHTML = window.personalTableData;
                            document.getElementById('total-repos-count').textContent = window.totalReposCount;
                            document.getElementById('page-info').textContent = window.pageInfo;
                        }
                    }
                    
                    // Function to switch to organization repos content (empty for now)
                    function switchToOrgRepos() {
                        console.log('Switched to organization repositories view');
                        
                        // Reset stats to zero with animation
                        const repoCount = document.getElementById('repo-count');
                        const locCount = document.getElementById('loc-count');
                        const starsCount = document.getElementById('stars-count');
                        const activeCount = document.getElementById('active-count');
                        
                        // First store current state for animation
                        const currentRepoCount = parseInt(repoCount.textContent.replace(/,/g, ''));
                        const currentLocCount = parseInt(locCount.textContent.replace(/,/g, ''));
                        const currentStarsCount = parseInt(starsCount.textContent.replace(/,/g, ''));
                        const currentActiveCount = parseInt(activeCount.textContent.replace(/,/g, ''));
                        
                        // Animate to zero
                        animateValue(repoCount, currentRepoCount, 0, 800);
                        animateValue(locCount, currentLocCount, 0, 800);
                        animateValue(starsCount, currentStarsCount, 0, 800);
                        animateValue(activeCount, currentActiveCount, 0, 800);
                        
                        // Clear the charts
                        Plotly.purge('main-dashboard');
                        
                        // Create empty/placeholder chart
                        const emptyLayout = {
                            height: 2000,
                            title: {
                                text: '📊 Organization Repository Analysis Dashboard - Not Implemented Yet',
                                x: 0.5
                            },
                            annotations: [{
                                text: 'Organization repositories analysis will be available soon',
                                font: {
                                    size: 20,
                                    color: document.documentElement.classList.contains('dark') ? 'white' : 'black'
                                },
                                showarrow: false,
                                xref: 'paper',
                                yref: 'paper',
                                x: 0.5,
                                y: 0.5
                            }],
                            paper_bgcolor: document.documentElement.classList.contains('dark') ? '#1f2937' : '#ffffff',
                            plot_bgcolor: document.documentElement.classList.contains('dark') ? '#1f2937' : '#ffffff'
                        };
                        
                        // Make sure to apply the same config options when creating the empty chart
                        const plotlyConfig = {
                            responsive: true,
                            displayModeBar: false,
                            scrollZoom: false
                        };
                        
                        Plotly.newPlot('main-dashboard', [], emptyLayout, plotlyConfig);
                        
                        // Clear repository table
                        document.getElementById('repos-table-body').innerHTML = '';
                        document.getElementById('total-repos-count').textContent = '0';
                        document.getElementById('page-info').textContent = 'Page 1 of 1';
                    }
                    
                    // Reuse the counter animation function
                    function animateValue(element, start, end, duration) {
                        let startTimestamp = null;
                        const step = (timestamp) => {
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            let value = Math.floor(progress * (end - start) + start);

                            // Format with commas if needed
                            if (end > 999 || start > 999) {
                                value = value.toLocaleString();
                            }

                            element.textContent = value;
                            if (progress < 1) {
                                window.requestAnimationFrame(step);
                            }
                        };
                        window.requestAnimationFrame(step);
                    }
                    
                    // Handle window resize for tab indicator
                    window.addEventListener('resize', () => {
                        if (personalReposTab && orgReposTab && tabIndicator) {
                            if (personalReposTab.classList.contains('text-gray-900') || 
                                personalReposTab.classList.contains('dark:text-white')) {
                                tabIndicator.style.left = '1px';
                                tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                            } else {
                                tabIndicator.style.left = `${personalReposTab.offsetWidth + 1}px`;
                                tabIndicator.style.width = `${orgReposTab.offsetWidth}px`;
                            }
                        }
                    });
                }
                """
        return repo_tabs_js

    @staticmethod
    def _create_js_part3(repo_table_js: str, repo_tabs_js: str) -> str:
        """Create the third part of the JavaScript section of the HTML file"""
        # Add conditional check for repo_tabs_js
        init_repo_tabs_js = """
                    // Initialize repository type tabs
                    initRepoTypeTabs();
        """ if repo_tabs_js else ""

        js_part3 = f"""
                // Initialize when DOM is loaded
                document.addEventListener('DOMContentLoaded', function() {{
                    // Start animated counters
                    animateCounters();

                    // Initialize repository table
                    initReposTable();
                    {init_repo_tabs_js}

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

                    // Chart Modal Functionality
                    const chartModal = document.getElementById('chartModal');
                    const chartModalIframe = document.getElementById('chartModalIframe');
                    const chartModalTitle = document.getElementById('chartModalTitle');
                    const chartModalDescription = document.getElementById('chartModalDescription');
                    const chartModalClose = document.getElementById('chartModalClose');

                    // Set up chart click handlers
                    document.querySelectorAll('.chart-item').forEach(chart => {{
                        chart.addEventListener('click', () => {{
                            openChartModal(chart);
                        }});
                    }});

                    // Handle iframe load events
                    chartModalIframe.addEventListener('load', function() {{
                        // Ensure iframe content is properly displayed
                        try {{
                            // Allow a moment for the iframe to fully render its contents
                            setTimeout(() => {{
                                // Make iframe visible with a smooth fade in
                                chartModalIframe.style.opacity = '0';
                                setTimeout(() => {{
                                    chartModalIframe.style.opacity = '1';
                                }}, 100);
                            }}, 300);
                        }} catch (e) {{
                            console.error("Error handling iframe load:", e);
                        }}
                    }});

                    function openChartModal(chartElement) {{
                        // Get chart data from dataset
                        const src = chartElement.dataset.chartSrc;
                        const title = chartElement.dataset.chartTitle;
                        const description = chartElement.dataset.chartDescription;
                        
                        console.log(`Opening modal for: ${{title}}, src: ${{src}}`);

                        // Set modal content
                        chartModalIframe.src = src;
                        chartModalTitle.textContent = title;
                        chartModalDescription.textContent = description;

                        // Show modal with animation 
                        document.body.style.overflow = 'hidden';
                        
                        // Trigger a reflow to ensure animations work properly
                        void chartModal.offsetWidth;
                        
                        // Add active class to show the modal
                        chartModal.classList.add('active');
                        
                        // Scroll to top when opening modal
                        if (chartModalIframe.parentElement) {{
                            chartModalIframe.parentElement.scrollTop = 0;
                        }}
                        
                        // Force the scrollbars to display
                        setTimeout(() => {{
                            const modalContent = document.querySelector('.chart-modal-content');
                            const iframeContainer = document.querySelector('.chart-modal-iframe-container');
                            
                            if (modalContent) {{
                                modalContent.style.overflowY = 'auto';
                                modalContent.style.display = 'block';
                            }}
                            
                            if (iframeContainer) {{
                                iframeContainer.style.overflowY = 'auto';
                                iframeContainer.style.display = 'block';
                                iframeContainer.style.height = '75vh';
                            }}
                        }}, 300);
                        
                        console.log('Modal should now be visible');
                    }}

                    function closeChartModal() {{
                        // Hide modal and restore scrolling
                        chartModal.classList.remove('active');
                        document.body.style.overflow = 'auto';
                        
                        // Clear iframe source after animation completes
                        setTimeout(() => {{
                            chartModalIframe.src = '';
                        }}, 500);
                    }}

                    // Event listeners for closing modal
                    chartModalClose.addEventListener('click', closeChartModal);
                    chartModal.addEventListener('click', (e) => {{
                        if (e.target === chartModal) {{
                            closeChartModal();
                        }}
                    }});

                    // Keyboard navigation for modal
                    document.addEventListener('keydown', (e) => {{
                        if (e.key === 'Escape' && chartModal.classList.contains('active')) {{
                            closeChartModal();
                        }}
                    }});

                    // Set CSS variables for scrollbar colors
                    document.documentElement.style.setProperty('--primary', '#4f46e5');
                    document.documentElement.style.setProperty('--scrollbar-track', '#f1f1f1');
                }});

                {repo_table_js}
                
                {repo_tabs_js}
            </script>
            </div>
        </body>
        </html>"""
        return js_part3
