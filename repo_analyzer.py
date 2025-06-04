from models import RepoStats
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional, Dict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import ThemeConfig, DefaultTheme
from console import logger



class PersonalRepoAnalysis:
    """Class responsible for creating repository analysis dashboard"""

    def __init__(self, username: str, theme: Optional[ThemeConfig] = None):
        """Initialize the analyzer with username and theme"""
        self.username = username
        self.theme = theme if theme is not None else DefaultTheme.get_default_theme()

    def create_charts_section(self) -> str:
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

                <!-- Responsive styles for dashboard -->
                <style>
                    @media (max-width: 768px) {
                        #main-dashboard {
                            height: 3000px !important; /* Adjusted height for mobile view */
                        }
                    }
                    @media (max-width: 480px) {
                        #main-dashboard {
                            height: 3500px !important; /* Even taller for small phones */
                        }
                    }
                </style>
                
                <!-- Responsive script for dashboard layout -->
                <script>
                    document.addEventListener('DOMContentLoaded', function() {
                        // Function to handle responsive layout
                        function handleResponsiveLayout() {
                            const dashboard = document.getElementById('main-dashboard');
                            if (!dashboard || !window.dashboardFigure) return;
                            
                            // For mobile devices
                            if (window.innerWidth <= 768) {
                                // Get the current layout
                                const currentLayout = dashboard.layout || {};
                                
                                // Adjust subplot layout for mobile (stacked single column)
                                const update = {
                                    'grid.subplots': [['xy'], ['xy2'], ['x2y2'], ['x2y3'], 
                                                      ['x3y4'], ['x3y5'], ['x4y6'], ['x4y7']],
                                    'grid.rows': 8,
                                    'grid.columns': 1,
                                    'grid.roworder': 'top to bottom',
                                    'height': window.innerWidth <= 480 ? 3500 : 3000, // Adjusted height based on screen size
                                    'width': window.innerWidth * 0.95, // Use 95% of screen width
                                };
                                
                                // Adjust subplot dimensions
                                Plotly.relayout(dashboard, update);
                                
                                // Smaller font size for mobile
                                Plotly.relayout(dashboard, {
                                    'font.size': 10,
                                    'title.font.size': 14,
                                    'margin': { t: 50, l: 35, r: 35, b: 35 },
                                });
                            } else {
                                // For desktop - restore original layout
                                const update = {
                                    'grid.rows': 4,
                                    'grid.columns': 2,
                                    'height': 2000,
                                    'font.size': 12,
                                    'title.font.size': 16,
                                    'margin': { t: 100, l: 50, r: 50, b: 50 },
                                };
                                
                                Plotly.relayout(dashboard, update);
                            }
                        }
                        
                        // Add event listener for window resize
                        window.addEventListener('resize', function() {
                            if (window.resizeTimer) clearTimeout(window.resizeTimer);
                            window.resizeTimer = setTimeout(handleResponsiveLayout, 250);
                        });
                        
                        // Initial check - run twice with a delay to ensure plots load correctly
                        setTimeout(handleResponsiveLayout, 500);
                        setTimeout(handleResponsiveLayout, 1500);
                    });
                </script>

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
                    <div class="scrollable-table-container border border-gray-200 dark:border-gray-700 rounded-lg">
                        <table id="repos-table" class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800 sticky top-0 z-10">
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

    def create_dashboard_figure(self, non_empty_repos: List[RepoStats]) -> go.Figure:
        """Create the main dashboard figure with multiple subplots"""
        # Define subplot layouts based on screen size
        # Default is 4x2 grid for larger screens
        subplot_config = {
            "rows": 4, 
            "cols": 2,
            "subplot_titles": [
                'Top 10 Languages by LOC',
                'Repository Size Distribution',
                'File Type Distribution',
                'Activity Timeline',
                'Stars vs LOC Correlation',
                'Maintenance Score Distribution',
                'Repository Age Distribution',
                'Quality Metrics Overview'
            ],
            "specs": [
                [{"type": "bar"}, {"type": "histogram"}],
                [{"type": "pie"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "histogram"}],
                [{"type": "bar"}, {"type": "bar"}]
            ]
        }

        # Create subplots for different visualizations
        fig = make_subplots(
            rows=subplot_config["rows"],
            cols=subplot_config["cols"],
            subplot_titles=subplot_config["subplot_titles"],
            specs=subplot_config["specs"],
            vertical_spacing=0.12,  # Increased spacing for better mobile view
            horizontal_spacing=0.08  # Adjusted horizontal spacing
        )

        # Use theme colors for plots
        chart_colors = self.theme["chart_palette"]
        
        # Add all chart traces
        self._add_language_chart(fig, chart_colors, non_empty_repos)
        self._add_repo_size_chart(fig, chart_colors, non_empty_repos)
        self._add_file_type_chart(fig, chart_colors, non_empty_repos)
        self._add_activity_timeline_chart(fig, chart_colors, non_empty_repos)
        self._add_stars_vs_loc_chart(fig, chart_colors, non_empty_repos)
        self._add_maintenance_score_chart(fig, chart_colors, non_empty_repos)
        self._add_repo_age_chart(fig, chart_colors, non_empty_repos)
        self._add_quality_metrics_chart(fig, chart_colors, non_empty_repos)
        
        # Update layout with theme colors
        fig.update_layout(
            height=2000,
            title_text=f"📊 GitHub Repository Analysis Dashboard - {self.username}",
            title_x=0.5,
            showlegend=False,
            template="plotly_white",
            paper_bgcolor=self.theme["light_chart_bg"],
            plot_bgcolor=self.theme["light_chart_bg"],
            font=dict(family=self.theme["font_family"], color=self.theme["light_text_color"]),
            autosize=True,
            margin=dict(l=50, r=50, t=100, b=50),
        )

        # Update axes labels
        self._update_axis_labels(fig)
        
        # Add responsive layout configuration
        fig.update_layout(
            grid=dict(
                rows=subplot_config["rows"], 
                columns=subplot_config["cols"],
                pattern='independent',
                roworder='top to bottom'
            )
        )
        
        # Configure for better mobile experience
        fig.update_layout(
            # More compact legend for mobile
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            )
        )
        
        # Update font size for subplot titles
        if fig.layout.annotations:
            for ann in fig.layout.annotations:
                ann.font.size = 12
        
        # Store the figure in a global JavaScript variable for access by the responsive script
        fig.update_layout(
            newshape=dict(line_color=self.theme["chart_palette"][0]),
            # Mobile-specific config
            modebar=dict(
                orientation='v',  # Vertical mode bar for mobile
                bgcolor='rgba(255, 255, 255, 0.7)',  # Semi-transparent background
            )
        )
        
        # Save a reference to the figure in JavaScript global scope with improved handling
        store_as_global = """
        window.dashboardFigure = document.getElementById('main-dashboard')._fullData;
        
        // Enhanced responsive handling
        function updateModeBarVisibility() {
            var modeBarButtons = document.querySelectorAll('.modebar-container');
            var isMobile = window.innerWidth <= 768;
            
            for (var i = 0; i < modeBarButtons.length; i++) {
                // Hide full modebar on mobile, show minimal controls
                var buttons = modeBarButtons[i].querySelectorAll('.modebar-btn');
                for (var j = 0; j < buttons.length; j++) {
                    // On mobile, only show download and zoom buttons
                    var isEssentialButton = buttons[j].getAttribute('data-title') === 'Download plot as a png' || 
                                           buttons[j].getAttribute('data-title') === 'Zoom' ||
                                           buttons[j].getAttribute('data-title') === 'Reset axes';
                    buttons[j].style.display = (isMobile && !isEssentialButton) ? 'none' : 'inline-block';
                }
                
                // Adjust modebar position on mobile
                modeBarButtons[i].style.top = isMobile ? '10px' : '0';
                modeBarButtons[i].style.right = isMobile ? '5px' : '0';
            }
        }
        
        window.addEventListener('resize', function() {
            if (window.resizeTimer) clearTimeout(window.resizeTimer);
            window.resizeTimer = setTimeout(updateModeBarVisibility, 250);
        });
        
        // Initial setup
        setTimeout(updateModeBarVisibility, 1000);
        setTimeout(updateModeBarVisibility, 2000); // Run again to catch any late-loaded elements
        """
        
        # Update config to be more mobile-friendly
        fig.update_layout(
            # Config for better touch interaction
            hovermode='closest',
            dragmode='pan',  # Pan is more touch-friendly than zoom
            # For mobile: adjust spacing between subplots
            grid_xgap=0.1,
            grid_ygap=0.2
        )
        
        # Make sure plots are responsive
        for i in range(1, subplot_config["rows"] + 1):
            for j in range(1, subplot_config["cols"] + 1):
                fig.update_xaxes(automargin=True, row=i, col=j)
                fig.update_yaxes(automargin=True, row=i, col=j)
                
        return fig

    def _add_language_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add language distribution chart to the figure"""
        # Need access to all_languages from the original class
        if hasattr(self, 'all_languages') and self.all_languages:
            top_languages = sorted(self.all_languages.items(), key=lambda x: x[1], reverse=True)[:10]
            langs, locs = zip(*top_languages)

            fig.add_trace(
                go.Bar(x=list(langs), y=list(locs), name="Languages", marker_color=chart_colors[0]),
                row=1, col=1
            )
        else:
            # If no language data at all, show a placeholder
            logger.warning("No language data available for visualization")
            fig.add_trace(
                go.Bar(x=["No Data"], y=[0], name="Languages", marker_color=chart_colors[0]),
                row=1, col=1
            )

    def _add_repo_size_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add repository size distribution chart to the figure"""
        repo_sizes = [stats.total_loc for stats in non_empty_repos if stats.total_loc > 0]
        if repo_sizes:
            fig.add_trace(
                go.Histogram(x=repo_sizes, nbinsx=20, name="Repo Sizes", marker_color=chart_colors[1]),
                row=1, col=2
            )

    def _add_file_type_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add file type distribution chart to the figure"""
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

    def _add_activity_timeline_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add activity timeline chart to the figure"""
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

    def _add_stars_vs_loc_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add stars vs LOC correlation chart to the figure"""
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

    def _add_maintenance_score_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add maintenance score distribution chart to the figure"""
        maintenance_scores = [stats.maintenance_score for stats in non_empty_repos]
        if maintenance_scores:
            fig.add_trace(
                go.Histogram(x=maintenance_scores, nbinsx=20, name="Maintenance Scores", marker_color=chart_colors[4]),
                row=3, col=2
            )

    def _add_repo_age_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add repository age distribution chart to the figure"""
        ages = [(datetime.now().replace(tzinfo=timezone.utc) - stats.created_at).days / 365.25 for stats in
                non_empty_repos]
        if ages:
            fig.add_trace(
                go.Histogram(x=ages, nbinsx=15, name="Repository Ages (Years)", marker_color=chart_colors[5]),
                row=4, col=1
            )

    def _add_quality_metrics_chart(self, fig: go.Figure, chart_colors: list, non_empty_repos: List[RepoStats]) -> None:
        """Add quality metrics overview chart to the figure"""
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

    def _update_axis_labels(self, fig: go.Figure) -> None:
        """Update axis labels for all subplots"""
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


class OrganizationRepoAnalysis:
    """Class responsible for creating repository analysis dashboard for organization repositories"""

    def __init__(self, username: str, org_names: List[str], theme: Optional[ThemeConfig] = None):
        """Initialize the analyzer with username, organization names and theme"""
        self.username = username
        self.org_names = org_names
        self.theme = theme if theme is not None else DefaultTheme.get_default_theme()
        # Dictionary to store languages per organization
        self.org_languages: Dict[str, Dict[str, int]] = {}
        # All languages aggregated
        self.all_languages = defaultdict(int)

    def create_charts_section(self) -> str:
        """Create the charts section of the HTML file for organization repositories"""
        return """<!-- Organization Charts section with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10 transform hover:shadow-2xl transition-all duration-300">
                    <h2 class="text-2xl font-semibold mb-6 dark:text-white flex items-center">
                        <span class="bg-secondary/10 text-secondary p-2 rounded-lg mr-3">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                            </svg>
                        </span>
                        Organization Repository Analysis Dashboard
                    </h2>
                    <div id="org-dashboard" class="w-full animate-chart-enter" style="height: 2000px;"></div>
                </div>

                <!-- Organization Table with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" data-aos-delay="200" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10 transform hover:shadow-2xl transition-all duration-300">
                    <div class="flex flex-col md:flex-row justify-between items-center mb-6">
                        <h2 class="text-2xl font-semibold dark:text-white flex items-center mb-4 md:mb-0">
                            <span class="bg-tertiary/10 text-tertiary p-2 rounded-lg mr-3">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                            </span>
                            Organization Repository Details
                        </h2>
                        <div class="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-2 w-full md:w-auto">
                            <div class="relative">
                                <input id="org-repo-search" type="text" placeholder="Search repositories..." 
                                    class="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary w-full">
                                <div class="absolute left-3 top-2.5 text-gray-400">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                </div>
                            </div>
                            <select id="org-filter" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary">
                                <option value="all">All Organizations</option>
                                <!-- Organization options will be added dynamically -->
                            </select>
                        </div>
                    </div>

                    <!-- Table Container with enhanced animations -->
                    <div class="scrollable-table-container border border-gray-200 dark:border-gray-700 rounded-lg">
                        <table id="org-repos-table" class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead class="bg-gray-50 dark:bg-gray-800 sticky top-0 z-10">
                                <tr>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="name">
                                        Repository <span class="sort-icon">↕</span>
                                    </th>
                                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200" data-sort="org">
                                        Organization <span class="sort-icon">↕</span>
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
                                </tr>
                            </thead>
                            <tbody id="org-repos-table-body" class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                <!-- Rows will be added by JavaScript -->
                            </tbody>
                        </table>
                    </div>

                    <!-- Pagination Controls with enhanced styling -->
                    <div class="flex flex-col sm:flex-row justify-between items-center mt-6 space-y-3 sm:space-y-0">
                        <div class="text-sm text-gray-500 dark:text-gray-400 px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded-lg">
                            <span id="total-org-repos-count">0</span> repositories found
                        </div>
                        <div class="flex space-x-2">
                            <button id="org-prev-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors duration-200 flex items-center">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                                </svg>
                                Previous
                            </button>
                            <span id="org-page-info" class="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg">Page 1</span>
                            <button id="org-next-page" class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors duration-200 flex items-center">
                                Next
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>"""

    def process_repositories(self, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Process organization repositories to extract language data"""
        # Clear previous data
        self.org_languages = {}
        self.all_languages = defaultdict(int)
        
        # Process each organization's repositories
        for org_name, repos in org_repos.items():
            org_lang_data = defaultdict(int)
            
            for repo in repos:
                # Add languages from this repo to the org-specific data
                for lang, loc in repo.languages.items():
                    org_lang_data[lang] += loc
                    # Also add to the overall languages count
                    self.all_languages[lang] += loc
                    
            # Store the organization's language data
            self.org_languages[org_name] = dict(org_lang_data)
            logger.info(f"Processed {len(repos)} repositories for organization {org_name}")
        
        logger.info(f"Processed repositories for {len(org_repos)} organizations")

    def create_dashboard_figure(self, org_repos: Dict[str, List[RepoStats]]) -> go.Figure:
        """Create the main dashboard figure with multiple subplots for organization data"""
        # Define subplot layouts
        subplot_config = {
            "rows": 4, 
            "cols": 2,
            "subplot_titles": [
                'Top 10 Languages in Organizations',
                'Organizations Repository Count',
                'Organization-specific Language Distribution',
                'Repository Size by Organization',
                'Stars Distribution by Organization',
                'Active vs Inactive Repositories',
                'Repository Age Distribution',
                'Organizations Contribution Timeline'
            ],
            "specs": [
                [{"type": "bar"}, {"type": "pie"}],
                [{"type": "bar"}, {"type": "box"}],
                [{"type": "scatter"}, {"type": "histogram"}],
                [{"type": "bar"}, {"type": "bar"}]
            ]
        }

        # Create subplots for different visualizations
        fig = make_subplots(
            rows=subplot_config["rows"],
            cols=subplot_config["cols"],
            subplot_titles=subplot_config["subplot_titles"],
            specs=subplot_config["specs"],
            vertical_spacing=0.12,
            horizontal_spacing=0.08
        )

        # Use theme colors for plots
        chart_colors = self.theme["chart_palette"]
        
        # Combine all repos for easier access
        all_org_repos = []
        for org_repos_list in org_repos.values():
            all_org_repos.extend(org_repos_list)
        
        # Add charts
        self._add_org_language_chart(fig, chart_colors, org_repos)
        self._add_org_repo_count_chart(fig, chart_colors, org_repos)
        self._add_org_specific_language_chart(fig, chart_colors, org_repos)
        self._add_repo_size_by_org_chart(fig, chart_colors, org_repos)
        self._add_stars_by_org_chart(fig, chart_colors, org_repos)
        self._add_activity_status_chart(fig, chart_colors, org_repos)
        self._add_org_repo_age_chart(fig, chart_colors, all_org_repos)
        self._add_org_contribution_timeline(fig, chart_colors, all_org_repos)
        
        # Update layout with theme colors
        fig.update_layout(
            height=2000,
            title_text=f"📊 Organization Repositories Analysis Dashboard - {self.username}",
            title_x=0.5,
            showlegend=False,
            template="plotly_white",
            paper_bgcolor=self.theme["light_chart_bg"],
            plot_bgcolor=self.theme["light_chart_bg"],
            font=dict(family=self.theme["font_family"], color=self.theme["light_text_color"]),
            autosize=True,
            margin=dict(l=50, r=50, t=100, b=50),
        )

        # Update axes labels
        self._update_org_axis_labels(fig)
        
        # Add responsive layout configuration
        fig.update_layout(
            grid=dict(
                rows=subplot_config["rows"], 
                columns=subplot_config["cols"],
                pattern='independent',
                roworder='top to bottom'
            ),
            # More compact legend for mobile
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            )
        )
        
        # Update font size for subplot titles
        if fig.layout.annotations:
            for ann in fig.layout.annotations:
                ann.font.size = 12
                
        # Make sure plots are responsive
        for i in range(1, subplot_config["rows"] + 1):
            for j in range(1, subplot_config["cols"] + 1):
                fig.update_xaxes(automargin=True, row=i, col=j)
                fig.update_yaxes(automargin=True, row=i, col=j)
                
        return fig

    def _add_org_language_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add top languages across all organizations chart"""
        if self.all_languages:
            top_languages = sorted(self.all_languages.items(), key=lambda x: x[1], reverse=True)[:10]
            langs, locs = zip(*top_languages)

            fig.add_trace(
                go.Bar(x=list(langs), y=list(locs), name="Languages", marker_color=chart_colors[0]),
                row=1, col=1
            )
        else:
            # If no language data, show placeholder
            fig.add_trace(
                go.Bar(x=["No Data"], y=[0], name="Languages", marker_color=chart_colors[0]),
                row=1, col=1
            )

    def _add_org_repo_count_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add organization repository count pie chart"""
        if org_repos:
            org_counts = {org: len(repos) for org, repos in org_repos.items()}
            orgs, counts = zip(*org_counts.items())

            fig.add_trace(
                go.Pie(labels=list(orgs), values=list(counts), name="Organizations",
                       marker=dict(colors=chart_colors[:len(org_counts)])),
                row=1, col=2
            )

    def _add_org_specific_language_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add organization-specific language distribution"""
        if self.org_languages:
            # Create data for a stacked bar chart of languages per organization
            orgs = list(self.org_languages.keys())
            
            # Get top 5 languages across all orgs
            all_langs_sorted = sorted(self.all_languages.items(), key=lambda x: x[1], reverse=True)
            top_langs = [lang for lang, _ in all_langs_sorted[:5]]
            
            # Create a trace for each top language
            for i, lang in enumerate(top_langs):
                y_values = []
                for org in orgs:
                    y_values.append(self.org_languages[org].get(lang, 0))
                
                fig.add_trace(
                    go.Bar(
                        x=orgs, 
                        y=y_values,
                        name=lang,
                        marker_color=chart_colors[i % len(chart_colors)]
                    ),
                    row=2, col=1
                )
            
            # Set barmode to stack for this subplot
            fig.update_layout(barmode='stack')

    def _add_repo_size_by_org_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add repository size boxplot by organization"""
        if org_repos:
            # Create data for boxplot
            boxplot_data = []
            org_names = []
            
            for org_name, repos in org_repos.items():
                repo_sizes = [repo.total_loc for repo in repos if repo.total_loc > 0]
                if repo_sizes:
                    boxplot_data.append(repo_sizes)
                    org_names.append(org_name)
            
            if boxplot_data:
                fig.add_trace(
                    go.Box(
                        y=boxplot_data[0],
                        name=org_names[0],
                        marker_color=chart_colors[0]
                    ),
                    row=2, col=2
                )
                
                # Add additional box plots for each organization
                for i in range(1, len(boxplot_data)):
                    fig.add_trace(
                        go.Box(
                            y=boxplot_data[i],
                            name=org_names[i],
                            marker_color=chart_colors[i % len(chart_colors)]
                        ),
                        row=2, col=2
                    )

    def _add_stars_by_org_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add stars distribution by organization"""
        if org_repos:
            orgs = []
            total_stars = []
            
            for org_name, repos in org_repos.items():
                orgs.append(org_name)
                total_stars.append(sum(repo.stars for repo in repos))
            
            fig.add_trace(
                go.Bar(
                    x=orgs,
                    y=total_stars,
                    name="Total Stars",
                    marker_color=chart_colors[2]
                ),
                row=3, col=1
            )

    def _add_activity_status_chart(self, fig: go.Figure, chart_colors: list, org_repos: Dict[str, List[RepoStats]]) -> None:
        """Add active vs inactive repositories by organization"""
        if org_repos:
            orgs = []
            active_counts = []
            inactive_counts = []
            
            for org_name, repos in org_repos.items():
                orgs.append(org_name)
                active_counts.append(sum(1 for repo in repos if repo.is_active))
                inactive_counts.append(sum(1 for repo in repos if not repo.is_active))
            
            fig.add_trace(
                go.Bar(
                    x=orgs,
                    y=active_counts,
                    name="Active",
                    marker_color=chart_colors[3]
                ),
                row=3, col=2
            )
            
            fig.add_trace(
                go.Bar(
                    x=orgs,
                    y=inactive_counts,
                    name="Inactive",
                    marker_color=chart_colors[4]
                ),
                row=3, col=2
            )
            
            # Set barmode to group for this subplot only
            fig.update_layout(barmode='group')

    def _add_org_repo_age_chart(self, fig: go.Figure, chart_colors: list, all_org_repos: List[RepoStats]) -> None:
        """Add repository age distribution chart for all organization repos"""
        ages = [(datetime.now().replace(tzinfo=timezone.utc) - stats.created_at).days / 365.25 for stats in all_org_repos]
        if ages:
            fig.add_trace(
                go.Histogram(x=ages, nbinsx=15, name="Repository Ages (Years)", marker_color=chart_colors[5]),
                row=4, col=1
            )

    def _add_org_contribution_timeline(self, fig: go.Figure, chart_colors: list, all_org_repos: List[RepoStats]) -> None:
        """Add organization contribution timeline chart"""
        # Group repos by creation year
        years = defaultdict(int)
        for repo in all_org_repos:
            year = repo.created_at.year
            years[year] += 1
        
        if years:
            sorted_years = sorted(years.items())
            year_labels, repo_counts = zip(*sorted_years)
            
            fig.add_trace(
                go.Bar(
                    x=list(year_labels),
                    y=list(repo_counts),
                    name="Repos Created",
                    marker_color=chart_colors[6]
                ),
                row=4, col=2
            )

    def _update_org_axis_labels(self, fig: go.Figure) -> None:
        """Update axis labels for all subplots"""
        fig.update_xaxes(title_text="Language", row=1, col=1)
        fig.update_yaxes(title_text="Lines of Code", row=1, col=1)

        fig.update_xaxes(title_text="Organization", row=2, col=1)
        fig.update_yaxes(title_text="Lines of Code", row=2, col=1)

        fig.update_xaxes(title_text="Organization", row=2, col=2)
        fig.update_yaxes(title_text="Repository Size (LOC)", row=2, col=2)

        fig.update_xaxes(title_text="Organization", row=3, col=1)
        fig.update_yaxes(title_text="Total Stars", row=3, col=1)

        fig.update_xaxes(title_text="Organization", row=3, col=2)
        fig.update_yaxes(title_text="Repository Count", row=3, col=2)

        fig.update_xaxes(title_text="Age (Years)", row=4, col=1)
        fig.update_yaxes(title_text="Repository Count", row=4, col=1)

        fig.update_xaxes(title_text="Year", row=4, col=2)
        fig.update_yaxes(title_text="Repositories Created", row=4, col=2)