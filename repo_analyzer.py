from models import RepoStats
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Optional
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
                            height: 3500px !important; /* Increase height for stacked layout on mobile */
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
                                // Store reference to the plotly figure
                                const figure = window.dashboardFigure;
                                
                                // Adjust subplot layout for mobile (stacked single column)
                                const update = {
                                    'grid.subplots': [['xy'], ['xy2'], ['x2y2'], ['x2y3'], 
                                                      ['x3y4'], ['x3y5'], ['x4y6'], ['x4y7']],
                                    'grid.rows': 8,
                                    'grid.columns': 1,
                                    'grid.roworder': 'top to bottom',
                                    'height': 3500 // Taller for stacked single-column layout
                                };
                                
                                Plotly.relayout(dashboard, update);
                            } else {
                                // For desktop - restore original layout if needed
                                const update = {
                                    'grid.rows': 4,
                                    'grid.columns': 2,
                                    'height': 2000
                                };
                                
                                Plotly.relayout(dashboard, update);
                            }
                        }
                        
                        // Add event listener for window resize
                        window.addEventListener('resize', handleResponsiveLayout);
                        
                        // Initial check
                        setTimeout(handleResponsiveLayout, 1000); // Delay to ensure plot is loaded
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
            vertical_spacing=0.1  # Increased spacing for better mobile view
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
            # Make layout responsive to screen size
            autosize=True,
            margin=dict(l=50, r=50, t=100, b=50),
        )

        # Update axes labels
        self._update_axis_labels(fig)
        
        # Add responsive layout configuration
        fig.update_layout(
            # This config ensures the plots stack properly
            grid=dict(
                rows=subplot_config["rows"], 
                columns=subplot_config["cols"],
                pattern='independent',
                roworder='top to bottom'
            )
        )
        
        # Add display configurations that handle responsiveness
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Add config for responsive behavior
        fig.config = {
            'responsive': True,
            'displayModeBar': False,  # Hide the modebar for cleaner mobile view
            'scrollZoom': False       # Disable scroll zoom on mobile
        }
        
        # Store the figure in a global JavaScript variable for access by the responsive script
        fig.update_layout(
            newshape=dict(line_color=self.theme["chart_palette"][0]),
        )
        
        # Save a reference to the figure in JavaScript global scope
        store_as_global = """
        window.dashboardFigure = document.getElementById('main-dashboard')._fullData;
        window.addEventListener('resize', function() {
            if (window.resizeTimer) clearTimeout(window.resizeTimer);
            window.resizeTimer = setTimeout(function() {
                var modeBarButtons = document.querySelectorAll('.modebar-container');
                for (var i = 0; i < modeBarButtons.length; i++) {
                    modeBarButtons[i].style.display = (window.innerWidth <= 768) ? 'none' : 'flex';
                }
            }, 250);
        });
        """
        
        # Add to the figure config
        if not hasattr(fig, 'layout'):
            fig.layout = {}
        
        if 'updatemenus' not in fig.layout:
            fig.layout['updatemenus'] = []
            
        # Store the script for execution after plot is rendered
        fig.layout['updatemenus'].append({
            'buttons': [],
            'direction': 'left',
            'pad': {'r': 10, 't': 10},
            'showactive': False,
            'type': 'buttons',
            'x': 0.1,
            'xanchor': 'right',
            'y': 0,
            'yanchor': 'top'
        })
        
        if not hasattr(fig, '_config'):
            fig._config = {}
            
        fig._config['responsive'] = True
        fig._config['post_script'] = [store_as_global]
        
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