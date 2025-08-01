"""
GitHub Repository Charts Module

This module generates visualizations and charts for repository analysis data.
It creates interactive charts and graphs to visualize repository statistics,
code quality metrics, and project trends.
"""

import os
import tempfile
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import plotly.graph_objects as go
from PIL import Image
from plotly.subplots import make_subplots
from wordcloud import WordCloud

from config import ThemeConfig
from console import logger
from models import RepoStats
from utilities import ensure_utc


def save_figure(fig, filename, reports_dir: Path) -> None:
    """
    Save a figure as both HTML and PNG files to the specified reports directory.
    
    Args:
        fig: The plotly figure to save
        filename: The base filename without extension
        reports_dir: The directory to save the files to
    """
    # Ensure the directory exists
    os.makedirs(reports_dir, exist_ok=True)

    # Save the HTML version
    html_path = reports_dir / f"{filename}.html"
    fig.write_html(str(html_path))

    # Save the PNG version with increased scale for better quality
    png_path = reports_dir / f"{filename}.png"
    fig.write_image(str(png_path), scale=3)

    logger.info(f"Saved figure to {html_path} and {png_path}")


# noinspection PyTypeChecker
class InfrastructureQualityMetricsCreator:
    """Class responsible for creating detailed charts for repository analysis"""

    def __init__(self, non_empty_repos: List[RepoStats], chart_colors: List[str],
                 reports_dir: Path, all_stats: Optional[List[RepoStats]] = None):
        self.non_empty_repos = non_empty_repos
        self.chart_colors = chart_colors
        self.reports_dir = reports_dir
        self.all_stats = all_stats

        # Ensure the reports directory exists
        os.makedirs(self.reports_dir, exist_ok=True)

    def create_infrastructure_quality_chart(self) -> None:
        """Create grouped bar chart showing infrastructure quality metrics"""
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

        # Calculate percentages for hover text
        yes_percentages = [(count / total) * 100 for count in yes_counts]
        no_percentages = [(count / total) * 100 for count in no_counts]

        # Create hover texts
        yes_hover = [f"Yes: {count}<br>({percentage:.1f}%)" for count, percentage in zip(yes_counts, yes_percentages)]
        no_hover = [f"No: {count}<br>({percentage:.1f}%)" for count, percentage in zip(no_counts, no_percentages)]

        # Create plotly figure
        fig = go.Figure()

        # Add Yes bars
        fig.add_trace(go.Bar(
            x=categories,
            y=yes_counts,
            name='Yes',
            marker_color=self.chart_colors[0],
            text=[f"{count}<br>({percentage:.1f}%)" for count, percentage in zip(yes_counts, yes_percentages)],
            textposition='auto',
            hoverinfo='text',
            hovertext=yes_hover
        ))

        # Add No bars
        fig.add_trace(go.Bar(
            x=categories,
            y=no_counts,
            name='No',
            marker_color=self.chart_colors[1],
            text=[f"{count}<br>({percentage:.1f}%)" for count, percentage in zip(no_counts, no_percentages)],
            textposition='auto',
            hoverinfo='text',
            hovertext=no_hover
        ))

        # Update layout
        fig.update_layout(
            title='Infrastructure Quality Metrics',
            yaxis_title='Number of Repositories',
            barmode='group',
            bargap=0.15,
            bargroupgap=0.1,
            yaxis=dict(range=[0, max(yes_counts + no_counts) * 1.15]),  # Add 15% padding
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Save the figure
        save_figure(fig, 'infrastructure_metrics', self.reports_dir)

    def create_commit_activity_heatmap(self) -> None:
        """Create a heatmap showing commit activity by month and year"""
        commit_data = self._extract_commit_data()

        if not commit_data:
            return

        years = self._get_sorted_years(commit_data)
        if not years:
            return

        z_data = self._build_heatmap_data(commit_data, years)
        hover_text = self._create_heatmap_hover_text(commit_data, years)

        fig = self._create_heatmap_figure(z_data, hover_text, years)
        save_figure(fig, 'commit_activity_heatmap', self.reports_dir)

    def _extract_commit_data(self) -> Dict[tuple, int]:
        """Extract commit data grouped by year and month"""
        commit_data = defaultdict(int)

        for stats in self.non_empty_repos:
            if stats.last_commit_date:
                month = stats.last_commit_date.month - 1  # 0-indexed
                year = stats.last_commit_date.year
                commit_data[(year, month)] += 1

        return commit_data

    @staticmethod
    def _get_sorted_years(commit_data: Dict[tuple, int]) -> List[int]:
        """Get sorted list of years from commit data"""
        return sorted(set(year for year, _ in commit_data.keys()))

    @staticmethod
    def _build_heatmap_data(commit_data: Dict[tuple, int], years: List[int]) -> List[List[int]]:
        """Build z-data matrix for the heatmap"""
        z_data = []
        for year in years:
            row = [commit_data.get((year, month), 0) for month in range(12)]
            z_data.append(row)
        return z_data

    @staticmethod
    def _create_heatmap_hover_text(commit_data: Dict[tuple, int], years: List[int]) -> List[List[str]]:
        """Create hover text for the heatmap"""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        hover_text = []

        for year in years:
            hover_row = []
            for month in range(12):
                count = commit_data.get((year, month), 0)
                hover_row.append(f"Year: {year}<br>Month: {month_names[month]}<br>Commits: {count}")
            hover_text.append(hover_row)

        return hover_text

    @staticmethod
    def _create_heatmap_figure(z_data: List[List[int]], hover_text: List[List[str]], years: List[int]) -> go.Figure:
        """Create the plotly heatmap figure"""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=month_names,
            y=years,
            colorscale='YlGnBu',
            text=z_data,  # Show commit counts as text
            texttemplate="%{text}",
            hoverinfo='text',
            hovertext=hover_text,
            colorbar=dict(title='Commit Count')
        ))

        # Update layout
        fig.update_layout(
            title='Repository Commit Activity by Month',
            xaxis_title='Month',
            yaxis_title='Year',
            xaxis=dict(side='top'),  # Show month names at the top like in seaborn
        )

        return fig

    def create_top_repos_by_metrics(self) -> None:
        """Create charts showing top 10 repositories by various metrics"""
        if len(self.non_empty_repos) > 0:
            # Create subplot with 2x2 grid
            fig = make_subplots(
                rows=2,
                cols=2,
                subplot_titles=(
                    'Top 10 Repositories by Size (LOC)',
                    'Top 10 Repositories by Stars',
                    'Top 10 Repositories by Maintenance Score',
                    'Top 10 Repositories by Contributors'
                ),
                vertical_spacing=0.12
            )

            # Top 10 by Size (LOC)
            top_by_loc = sorted(self.non_empty_repos, key=lambda x: x.total_loc, reverse=True)[:10]
            names_loc = [r.name for r in top_by_loc]
            locs = [r.total_loc for r in top_by_loc]

            fig.add_trace(
                go.Bar(
                    x=locs,
                    y=names_loc,
                    orientation='h',
                    marker_color=self.chart_colors[0],
                    text=[f"{loc:,}" for loc in locs],
                    textposition='auto',
                    hovertemplate='Repository: %{y}<br>Lines of Code: %{x:,}<extra></extra>'
                ),
                row=1, col=1
            )

            # Top 10 by Stars
            top_by_stars = sorted(self.non_empty_repos, key=lambda x: x.stars, reverse=True)[:10]
            names_stars = [r.name for r in top_by_stars]
            stars = [r.stars for r in top_by_stars]

            fig.add_trace(
                go.Bar(
                    x=stars,
                    y=names_stars,
                    orientation='h',
                    marker_color=self.chart_colors[1],
                    text=stars,
                    textposition='auto',
                    hovertemplate='Repository: %{y}<br>Stars: %{x}<extra></extra>'
                ),
                row=1, col=2
            )

            # Top 10 by Maintenance Score
            top_by_maint = sorted(self.non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:10]
            names_maint = [r.name for r in top_by_maint]
            maint_scores = [r.maintenance_score for r in top_by_maint]

            fig.add_trace(
                go.Bar(
                    x=maint_scores,
                    y=names_maint,
                    orientation='h',
                    marker_color=self.chart_colors[2],
                    text=[f"{score:.1f}" for score in maint_scores],
                    textposition='auto',
                    hovertemplate='Repository: %{y}<br>Maintenance Score: %{x:.1f}<extra></extra>'
                ),
                row=2, col=1
            )

            # Top 10 by Contributors
            top_by_contrib = sorted(self.non_empty_repos, key=lambda x: x.contributors_count, reverse=True)[:10]
            names_contrib = [r.name for r in top_by_contrib]
            contribs = [r.contributors_count for r in top_by_contrib]

            fig.add_trace(
                go.Bar(
                    x=contribs,
                    y=names_contrib,
                    orientation='h',
                    marker_color=self.chart_colors[3],
                    text=contribs,
                    textposition='auto',
                    hovertemplate='Repository: %{y}<br>Contributors: %{x}<extra></extra>'
                ),
                row=2, col=2
            )

            # Update layout
            fig.update_layout(
                height=800,
                width=1000,
                showlegend=False,
                title_text="Repository Metrics Comparison"
            )

            # Update axes
            fig.update_xaxes(title_text="Lines of Code", row=1, col=1)
            fig.update_xaxes(title_text="Stars", row=1, col=2)
            fig.update_xaxes(title_text="Maintenance Score", row=2, col=1)
            fig.update_xaxes(title_text="Contributors Count", row=2, col=2)

            # Save the figure using the utility function
            save_figure(fig, 'top_repos_metrics', self.reports_dir)

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

            # Create mask for upper triangle (for cleaner visualization)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))

            # Get labels and values for plotly heatmap
            labels = corr_matrix.columns.tolist()
            z_values = corr_matrix.values

            # Apply mask - replace upper triangle with None for plotly
            z_masked = z_values.copy()
            z_masked[mask] = None

            # Create custom hover text
            hover_text = []
            for i, row_label in enumerate(labels):
                hover_row = []
                for j, col_label in enumerate(labels):
                    if mask[i, j]:  # Skip upper triangle
                        hover_row.append(None)
                    else:
                        corr_value = z_values[i, j]
                        hover_row.append(f"{row_label} x {col_label}<br>Correlation: {corr_value:.2f}")
                hover_text.append(hover_row)

            # Create plotly heatmap
            fig = go.Figure(data=go.Heatmap(
                z=z_masked,
                x=labels,
                y=labels,
                colorscale='RdBu_r',  # Similar to coolwarm in seaborn
                zmid=0,  # Center color scale at 0
                text=hover_text,
                hoverinfo='text',
                colorbar=dict(
                    title='Correlation'
                )
            ))

            # Update layout
            fig.update_layout(
                title='Correlation Between Repository Metrics',
                width=700,
                height=700,
                xaxis=dict(ticks='', showticklabels=True, side='bottom'),
                yaxis=dict(ticks='', showticklabels=True),
            )

            # Save the figure using the utility function
            save_figure(fig, 'metrics_correlation', self.reports_dir)

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

            # Create a temporary file for the wordcloud image
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                wordcloud.to_file(tmp.name)
                tmp_filename = tmp.name

            # Convert the wordcloud image to a format plotly can use
            img = Image.open(tmp_filename)

            # Create a plotly figure with the wordcloud image
            fig = go.Figure()

            # Add the image
            fig.add_layout_image(
                dict(
                    source=img,
                    x=0,
                    y=1,
                    xref="paper",
                    yref="paper",
                    sizex=1,
                    sizey=1,
                    sizing="stretch",
                    opacity=1,
                    layer="below"
                )
            )

            # Update layout to make it look nice
            fig.update_layout(
                title='Repository Topics WordCloud',
                width=800,
                height=400,
                margin=dict(l=0, r=0, t=30, b=0),
            )

            # Remove axes and grid
            fig.update_xaxes(visible=False, showticklabels=False, showgrid=False, zeroline=False)
            fig.update_yaxes(visible=False, showticklabels=False, showgrid=False, zeroline=False)

            # Save the figure using the utility function
            save_figure(fig, 'topics_wordcloud', self.reports_dir)

            # Clean up the temporary file
            os.unlink(tmp_filename)

    def create_active_inactive_age_distribution(self) -> None:
        """Create histogram comparing age distribution of active vs inactive repositories"""
        # Separate active and inactive repos
        active_repos = [r for r in self.non_empty_repos if r.is_active]
        inactive_repos = [r for r in self.non_empty_repos if not r.is_active]

        # Calculate ages in years
        active_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in active_repos]
        inactive_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in
                         inactive_repos]

        # Create figure
        fig = go.Figure()

        # Add histograms
        if active_ages:
            fig.add_trace(go.Histogram(
                x=active_ages,
                nbinsx=15,
                opacity=0.7,
                name='Active',
                marker_color=self.chart_colors[0],
                hovertemplate='Age: %{x:.1f} years<br>Count: %{y}<extra>Active Repositories</extra>'
            ))

        if inactive_ages:
            fig.add_trace(go.Histogram(
                x=inactive_ages,
                nbinsx=15,
                opacity=0.7,
                name='Inactive',
                marker_color=self.chart_colors[1],
                hovertemplate='Age: %{x:.1f} years<br>Count: %{y}<extra>Inactive Repositories</extra>'
            ))

        # Update layout
        fig.update_layout(
            title='Age Distribution: Active vs Inactive Repositories',
            xaxis_title='Repository Age (Years)',
            yaxis_title='Count',
            barmode='overlay',  # Overlay histograms
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Add grid lines
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

        # Save the figure using the utility function
        save_figure(fig, 'active_inactive_age', self.reports_dir)

    def create_stars_vs_issues_scatter(self) -> None:
        """Create scatter plot of repository stars vs open issues"""
        # Extract data
        stars = [r.stars for r in self.non_empty_repos]
        issues = [r.open_issues for r in self.non_empty_repos]
        names = [r.name for r in self.non_empty_repos]
        is_active = [r.is_active for r in self.non_empty_repos]

        # Create a list of colors based on active status
        colors = [self.chart_colors[0] if active else self.chart_colors[1] for active in is_active]

        # Determine if we need logarithmic scales
        use_log_x = max(stars) > 100 * min([s for s in stars if s > 0] or [1])
        use_log_y = max(issues) > 100 * min([i for i in issues if i > 0] or [1])

        # Create custom hover text
        hover_texts = [
            f"Repository: {name}<br>Stars: {star}<br>Issues: {issue}<br>Status: {'Active' if active else 'Inactive'}"
            for name, star, issue, active in zip(names, stars, issues, is_active)]

        # Create plotly figure
        fig = go.Figure()

        # Add scatter plot
        fig.add_trace(go.Scatter(
            x=stars,
            y=issues,
            mode='markers',
            marker=dict(
                size=12,
                color=colors,
                opacity=0.7,
                line=dict(width=1, color='DarkSlateGrey')
            ),
            text=hover_texts,
            hoverinfo='text'
        ))

        # Add annotations for repos with many stars or issues
        threshold_stars = np.percentile(stars, 90) if len(stars) > 10 else 0
        threshold_issues = np.percentile(issues, 90) if len(issues) > 10 else 0

        for i, (name, s, iss) in enumerate(zip(names, stars, issues)):
            if s > threshold_stars or iss > threshold_issues:
                fig.add_annotation(
                    x=s,
                    y=iss,
                    text=name,
                    showarrow=False,
                    font=dict(size=10),
                    xshift=10,
                    yshift=10
                )

        # Update layout
        fig.update_layout(
            title='Repository Popularity vs. Maintenance Burden',
            xaxis_title='Stars',
            yaxis_title='Open Issues',
            hovermode='closest',
            xaxis=dict(
                type='log' if use_log_x else 'linear',
                showgrid=True
            ),
            yaxis=dict(
                type='log' if use_log_y else 'linear',
                showgrid=True
            )
        )

        # Save the figure using the utility function
        save_figure(fig, 'stars_vs_issues', self.reports_dir)

    def create_repository_creation_timeline(self) -> None:
        """Create timeline showing repository creation over time"""
        if self.all_stats:
            # Extract creation dates
            creation_dates = [ensure_utc(r.created_at) for r in self.all_stats]

            # Create histogram by year and month
            years_months = [(d.year, d.month) for d in creation_dates]
            unique_years_months = sorted(set(years_months))

            if unique_years_months:
                # Convert to datetime for better plotting
                plot_dates = [datetime(year=ym[0], month=ym[1], day=15) for ym in unique_years_months]
                counts = [years_months.count(ym) for ym in unique_years_months]

                # Create plotly figure
                fig = go.Figure()

                # Add bar chart
                fig.add_trace(go.Bar(
                    x=plot_dates,
                    y=counts,
                    marker_color=self.chart_colors[0],
                    opacity=0.8,
                    hovertemplate='Date: %{x|%Y-%m}<br>New Repositories: %{y}<extra></extra>'
                ))

                # Add trend line (smoothed moving average) if enough data points
                if len(counts) > 3:
                    from scipy.ndimage import gaussian_filter1d
                    smoothed = gaussian_filter1d(counts, sigma=1.5)

                    fig.add_trace(go.Scatter(
                        x=plot_dates,
                        y=smoothed,
                        mode='lines',
                        line=dict(color='red', width=2),
                        opacity=0.7,
                        name='Trend',
                        hovertemplate='Date: %{x|%Y-%m}<br>Trend: %{y:.1f}<extra></extra>'
                    ))

                # Update layout
                fig.update_layout(
                    title='Repository Creation Timeline',
                    xaxis_title='Date',
                    yaxis_title='New Repositories',
                    hovermode='closest',
                    showlegend=False
                )

                # Format x-axis with dates
                fig.update_xaxes(
                    tickformat='%Y-%m',
                    tickangle=45,
                    tickmode='auto',
                    nticks=20
                )

                # Add grid
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

                # Save the figure using the utility function
                save_figure(fig, 'repo_creation_timeline', self.reports_dir)

    def create_documentation_quality_distribution(self) -> None:
        """Create charts showing distribution of documentation and README quality"""
        # Create subplots with 1 row and 2 columns
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=('Documentation Size Distribution', 'README Comprehensiveness Distribution')
        )

        # Documentation Size Distribution
        docs_categories = Counter(r.docs_size_category for r in self.non_empty_repos)
        # Sort categories in logical order
        category_order = ["None", "Small", "Intermediate", "Big"]
        docs_data = [docs_categories.get(cat, 0) for cat in category_order]

        # Add bar chart for documentation size
        fig.add_trace(
            go.Bar(
                x=category_order,
                y=docs_data,
                marker_color=self.chart_colors[:len(category_order)],
                text=docs_data,  # Show counts on bars
                textposition='auto',
                hovertemplate='Category: %{x}<br>Count: %{y}<extra></extra>'
            ),
            row=1, col=1
        )

        # README Comprehensiveness Distribution
        readme_categories = Counter(r.readme_comprehensiveness for r in self.non_empty_repos)
        # Sort categories in logical order
        readme_order = ["None", "Small", "Good", "Comprehensive"]
        readme_data = [readme_categories.get(cat, 0) for cat in readme_order]

        # Add bar chart for README comprehensiveness
        fig.add_trace(
            go.Bar(
                x=readme_order,
                y=readme_data,
                marker_color=self.chart_colors[3:3 + len(readme_order)],
                text=readme_data,  # Show counts on bars
                textposition='auto',
                hovertemplate='Category: %{x}<br>Count: %{y}<extra></extra>'
            ),
            row=1, col=2
        )

        # Update layout
        fig.update_layout(
            height=500,
            width=1000,
            showlegend=False,
        )

        # Update y-axis titles
        fig.update_yaxes(title_text="Number of Repositories", row=1, col=1)
        fig.update_yaxes(title_text="Number of Repositories", row=1, col=2)

        # Save the figure using the utility function
        save_figure(fig, 'documentation_quality', self.reports_dir)

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

            names = [r.name for r in top_by_releases]
            release_counts = [r.release_count for r in top_by_releases]

            # Create horizontal bar chart using plotly
            fig = go.Figure(data=go.Bar(
                x=release_counts,
                y=names,
                orientation='h',
                marker_color=self.chart_colors[2],
                text=release_counts,  # Show counts on bars
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Releases: %{x}<extra></extra>'
            ))

            # Update layout
            fig.update_layout(
                title='Repositories with Most Releases',
                xaxis_title='Number of Releases',
                height=max(600, len(top_by_releases) * 30),  # Dynamic height based on number of repos
                margin=dict(l=150, r=20, t=50, b=50),  # Add margin for long repo names
                yaxis=dict(
                    autorange="reversed"  # Show highest count at the top
                )
            )

            # Save the figure using the utility function
            save_figure(fig, 'release_counts', self.reports_dir)


class RepositoryTimelineCreator:
    """Class responsible for creating repository timeline visualizations"""

    def __init__(self, all_stats: List[RepoStats], reports_dir: Path):
        self.all_stats = all_stats
        self.reports_dir = reports_dir

    def create_timeline(self) -> None:
        """Create repository timeline chart showing creation and last commit dates"""
        repo_data = self._prepare_timeline_data()
        if not repo_data:
            return

        fig = self._create_timeline_figure(repo_data)
        self._configure_timeline_layout(fig, repo_data)
        save_figure(fig, 'repository_timeline', self.reports_dir)

    def _prepare_timeline_data(self) -> List[Dict]:
        """Prepare data for timeline visualization"""
        repo_data = []
        for stats in self.all_stats:
            created = ensure_utc(stats.created_at)
            last_commit = ensure_utc(stats.last_commit_date or stats.last_pushed)
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

        return sorted(repo_data, key=lambda x: x['created'])

    def _create_timeline_figure(self, repo_data: List[Dict]) -> go.Figure:
        """Create the timeline figure with lines and markers"""
        fig = go.Figure()

        for i, repo in enumerate(repo_data):
            self._add_timeline_traces(fig, repo, i)

        return fig

    def _add_timeline_traces(self, fig: go.Figure, repo: Dict, index: int) -> None:
        """Add timeline traces for a single repository"""
        color, opacity, marker_symbol = self._get_repo_style(repo)

        # Add line from creation to last commit
        fig.add_trace(go.Scatter(
            x=[repo['created'], repo['last_commit']],
            y=[index, index],
            mode='lines',
            line=dict(color=color, width=2),
            opacity=opacity,
            showlegend=False,
            hoverinfo='skip'
        ))

        # Add creation marker
        fig.add_trace(go.Scatter(
            x=[repo['created']],
            y=[index],
            mode='markers',
            marker=dict(
                color='blue',
                size=10,
                symbol=marker_symbol,
                line=dict(width=1, color='DarkSlateGrey')
            ),
            name='Created' if index == 0 else None,
            showlegend=index == 0,
            hovertemplate=f"Repository: {repo['name']}<br>Created: %{{x|%Y-%m-%d}}<extra></extra>"
        ))

        # Add last commit marker
        marker_size = min(20, max(8, repo['stars'] * 2 + 8))
        fig.add_trace(go.Scatter(
            x=[repo['last_commit']],
            y=[index],
            mode='markers',
            marker=dict(
                color=color,
                size=marker_size,
                symbol=marker_symbol,
                line=dict(width=1, color='DarkSlateGrey')
            ),
            name='Last Commit' if index == 0 else None,
            showlegend=index == 0,
            hovertemplate=f"Repository: {repo['name']}<br>Last Commit: %{{x|%Y-%m-%d}}<br>Stars: {repo['stars']}<br>Status: {'Empty' if repo['is_empty'] else 'Active' if repo['is_active'] else 'Inactive'}<extra></extra>"
        ))

    @staticmethod
    def _get_repo_style(repo: Dict) -> tuple:
        """Get color, opacity, and marker symbol for repository based on status"""
        if repo['is_empty']:
            return 'red', 0.3, 'x'
        else:
            color = 'green' if repo['is_active'] else 'gray'
            opacity = 0.7 if repo['is_active'] else 0.3
            return color, opacity, 'circle'

    @staticmethod
    def _configure_timeline_layout(fig: go.Figure, repo_data: List[Dict]) -> None:
        """Configure the layout for the timeline chart"""
        fig.update_layout(
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(len(repo_data))),
                ticktext=[r['name'] for r in repo_data]
            )
        )

        fig.update_layout(
            title='Repository Timeline (Creation → Last Commit)',
            xaxis_title='Date',
            yaxis_title='Repository',
            hovermode='closest',
            height=max(600, len(repo_data) * 25),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=150, r=20, t=50, b=50)
        )

        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')


class LanguageEvolutionCreator:
    """Class responsible for creating language evolution visualizations"""

    def __init__(self, non_empty_repos: List[RepoStats], reports_dir: Path):
        self.non_empty_repos = non_empty_repos
        self.reports_dir = reports_dir

    def create_evolution_chart(self) -> None:
        """Create language evolution chart showing how language usage has changed over time"""
        if len(self.non_empty_repos) <= 1:
            return

        yearly_languages, yearly_total_loc = self._gather_yearly_language_data()
        self._adjust_yearly_totals(yearly_languages, yearly_total_loc)

        top_languages = self._get_top_languages(yearly_languages)
        years, lang_data = self._prepare_evolution_data(yearly_languages, top_languages)

        fig = self._create_evolution_figure(years, lang_data, top_languages)
        save_figure(fig, 'language_evolution', self.reports_dir)

    def _gather_yearly_language_data(self) -> tuple:
        """Gather language data grouped by year"""
        yearly_languages = defaultdict(lambda: defaultdict(int))
        yearly_total_loc = defaultdict(int)

        # First pass: gather total LOC by year
        for stats in self.non_empty_repos:
            created_at = ensure_utc(stats.created_at)
            year = created_at.year
            yearly_total_loc[year] += stats.total_loc

        # Second pass: gather language data
        for stats in self.non_empty_repos:
            created_at = ensure_utc(stats.created_at)
            year = created_at.year

            self._process_repo_languages(stats, yearly_languages[year])

        return yearly_languages, yearly_total_loc

    @staticmethod
    def _process_repo_languages(stats: RepoStats, year_languages: Dict[str, int]) -> None:
        """Process language data for a single repository"""
        lang_sum = sum(stats.languages.values())

        if lang_sum == 0:
            if stats.total_loc > 0:
                year_languages["Unknown"] += stats.total_loc
            return

        # Handle inconsistent language data
        if lang_sum > stats.total_loc * 1.1:
            scaling_factor = stats.total_loc / lang_sum if lang_sum > 0 else 1
            logger.info(
                f"Repository {stats.name} has inconsistent language data. Scaling by factor {scaling_factor:.4f}")

            for lang, loc in stats.languages.items():
                year_languages[lang] += int(loc * scaling_factor)
        else:
            for lang, loc in stats.languages.items():
                year_languages[lang] += loc

    @staticmethod
    def _adjust_yearly_totals(yearly_languages: Dict, yearly_total_loc: Dict) -> None:
        """Adjust yearly language totals to match expected LOC"""
        for year in yearly_languages:
            lang_sum = sum(yearly_languages[year].values())
            total_loc = yearly_total_loc[year]

            if abs(lang_sum - total_loc) > total_loc * 0.05:
                logger.info(f"Year {year}: Adjusting language data to match total LOC ({total_loc:,})")

                if lang_sum < total_loc:
                    difference = total_loc - lang_sum
                    yearly_languages[year]["Unknown"] += difference
                elif lang_sum > total_loc:
                    scaling_factor = total_loc / lang_sum
                    for lang in yearly_languages[year]:
                        yearly_languages[year][lang] = int(yearly_languages[year][lang] * scaling_factor)

    @staticmethod
    def _get_top_languages(yearly_languages: Dict) -> List[str]:
        """Get top 5 languages overall"""
        all_lang_totals = defaultdict(int)
        for year_data in yearly_languages.values():
            for lang, loc in year_data.items():
                all_lang_totals[lang] += loc

        top_languages = sorted(all_lang_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        return [lang for lang, _ in top_languages]

    @staticmethod
    def _prepare_evolution_data(yearly_languages: Dict, top_languages: List[str]) -> tuple:
        """Prepare data for the evolution chart"""
        years = sorted(yearly_languages.keys())
        lang_data = {lang: [] for lang in top_languages}

        for year in years:
            year_total = sum(yearly_languages[year].values()) or 1
            for lang in top_languages:
                percentage = (yearly_languages[year][lang] / year_total) * 100
                lang_data[lang].append(percentage)

        return years, lang_data

    @staticmethod
    def _create_evolution_figure(years: List[int], lang_data: Dict, top_languages: List[str]) -> go.Figure:
        """Create the language evolution figure"""
        fig = go.Figure()

        for lang in top_languages:
            fig.add_trace(go.Scatter(
                x=years,
                y=lang_data[lang],
                mode='lines',
                stackgroup='one',
                name=lang,
                hovertemplate='Year: %{x}<br>' + lang + ': %{y:.1f}%<extra></extra>'
            ))

        fig.update_layout(
            title='Language Usage Evolution Over Time',
            xaxis_title='Year',
            yaxis_title='Percentage of Code (%)',
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

        return fig


class MaintenanceQualityHeatmapCreator:
    """Class responsible for creating maintenance quality heatmap visualizations"""

    def __init__(self, non_empty_repos: List[RepoStats], reports_dir: Path):
        self.non_empty_repos = non_empty_repos
        self.reports_dir = reports_dir
        self.quality_factors = ['Has Docs', 'Has Tests', 'Is Active', 'Has License', 'Low Issues']

    def create_heatmap(self) -> None:
        """Create heatmap showing maintenance quality factors for top repositories"""
        if not self.non_empty_repos:
            return

        top_repos = self._select_top_repositories()
        quality_matrix = self._build_quality_matrix(top_repos)

        if quality_matrix:
            fig = self._create_heatmap_figure(quality_matrix, top_repos)
            save_figure(fig, 'quality_heatmap', self.reports_dir)

    def _select_top_repositories(self) -> List[RepoStats]:
        """Select top repositories by maintenance score"""
        return sorted(self.non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:20]

    def _build_quality_matrix(self, top_repos: List[RepoStats]) -> List[List[int]]:
        """Build the quality matrix for the heatmap"""
        quality_matrix = []
        for stats in top_repos:
            row = self._evaluate_quality_factors(stats)
            quality_matrix.append(row)
        return quality_matrix

    @staticmethod
    def _evaluate_quality_factors(stats: RepoStats) -> List[int]:
        """Evaluate quality factors for a single repository"""
        return [
            1 if stats.has_docs else 0,
            1 if stats.has_tests else 0,
            1 if stats.is_active else 0,
            1 if stats.license_name else 0,
            1 if stats.open_issues < 5 else 0
        ]

    def _create_heatmap_figure(self, quality_matrix: List[List[int]], top_repos: List[RepoStats]) -> go.Figure:
        """Create the heatmap figure"""
        repo_names = [stats.name[:20] for stats in top_repos]
        # noinspection PyTypeChecker
        z_data = list(map(list, zip(*quality_matrix)))
        hover_text = self._create_hover_text(z_data, repo_names)

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=repo_names,
            y=self.quality_factors,
            colorscale=[[0, 'red'], [1, 'green']],
            showscale=False,
            text=z_data,
            texttemplate="%{text}",
            hoverinfo='text',
            hovertext=hover_text
        ))

        self._configure_heatmap_layout(fig)
        return fig

    def _create_hover_text(self, z_data: List[List[int]], repo_names: List[str]) -> List[List[str]]:
        """Create hover text for the heatmap"""
        hover_text = []
        for i, factor in enumerate(self.quality_factors):
            hover_row = []
            for j, repo in enumerate(repo_names):
                value = "Yes" if z_data[i][j] == 1 else "No"
                hover_row.append(f"Repository: {repo}<br>{factor}: {value}")
            hover_text.append(hover_row)
        return hover_text

    @staticmethod
    def _configure_heatmap_layout(fig: go.Figure) -> None:
        """Configure the layout for the heatmap"""
        fig.update_layout(
            title='Repository Maintenance Quality Matrix',
            xaxis=dict(
                title='Repositories',
                tickangle=-45,
            ),
            yaxis=dict(
                title='Quality Factors',
                autorange='reversed'
            ),
            height=600,
            width=900,
            margin=dict(l=150, r=20, t=50, b=150)
        )


class CorrelationScorer:
    """Class responsible for creating correlation matrix visualizations"""

    def __init__(self, non_empty_repos: List[RepoStats], reports_dir: Path):
        self.non_empty_repos = non_empty_repos
        self.reports_dir = reports_dir

    def create_correlation_matrix(self) -> None:
        """Create a correlation matrix of various metrics"""
        if len(self.non_empty_repos) < 5:  # Need sufficient data for correlations
            return

        data = self._extract_metrics_data()
        self._add_top_language_data(data)

        corr_matrix = self._calculate_correlation_matrix(data)
        fig = self._create_correlation_heatmap(corr_matrix)
        save_figure(fig, 'metrics_correlation', self.reports_dir)

    def _extract_metrics_data(self) -> Dict[str, List]:
        """Extract relevant metrics for correlation analysis"""
        return {
            "Total LOC": [repo.total_loc for repo in self.non_empty_repos],
            "Stars": [repo.stars for repo in self.non_empty_repos],
            "Forks": [repo.forks for repo in self.non_empty_repos],
            "Age (Days)": [(datetime.now().replace(tzinfo=timezone.utc) - repo.created_at).days for repo in
                           self.non_empty_repos],
            "Maintenance": [repo.maintenance_score for repo in self.non_empty_repos],
            "Open Issues": [repo.open_issues for repo in self.non_empty_repos]
        }

    def _add_top_language_data(self, data: Dict[str, List]) -> None:
        """Add top language percentage data to metrics"""
        all_languages = self._get_consistent_language_data()
        if not all_languages:
            return

        top_language = max(all_languages.items(), key=lambda x: x[1])[0]
        data[f"{top_language} %"] = []

        for repo in self.non_empty_repos:
            percentage = self._calculate_language_percentage(repo, top_language)
            data[f"{top_language} %"].append(percentage)

    @staticmethod
    def _calculate_language_percentage(repo: RepoStats, language: str) -> float:
        """Calculate percentage of specific language in repository"""
        total_lang_loc = sum(repo.languages.values())
        if total_lang_loc > 0:
            return (repo.languages.get(language, 0) / total_lang_loc) * 100
        return 0

    @staticmethod
    def _calculate_correlation_matrix(data: Dict[str, List]):
        """Calculate correlation matrix from metrics data"""
        import pandas as pd
        corr_data = pd.DataFrame(data)
        return corr_data.corr()

    def _create_correlation_heatmap(self, corr_matrix) -> go.Figure:
        """Create plotly heatmap figure from correlation matrix"""
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        labels = corr_matrix.columns.tolist()
        z_values = corr_matrix.values
        z_masked = z_values.copy()
        z_masked[mask] = None

        hover_text = self._create_correlation_hover_text(labels, z_values, mask)

        fig = go.Figure(data=go.Heatmap(
            z=z_masked,
            x=labels,
            y=labels,
            colorscale='RdBu_r',
            zmid=0,
            text=hover_text,
            hoverinfo='text',
            colorbar=dict(title='Correlation')
        ))

        fig.update_layout(
            title='Correlation Between Repository Metrics',
            width=700,
            height=700,
            xaxis=dict(ticks='', showticklabels=True, side='bottom'),
            yaxis=dict(ticks='', showticklabels=True),
        )

        return fig

    @staticmethod
    def _create_correlation_hover_text(labels: List[str], z_values, mask) -> List[List[str]]:
        """Create hover text for correlation heatmap"""
        hover_text = []
        for i, row_label in enumerate(labels):
            hover_row = []
            for j, col_label in enumerate(labels):
                if mask[i, j]:
                    hover_row.append(None)
                else:
                    corr_value = z_values[i, j]
                    hover_row.append(f"{row_label} x {col_label}<br>Correlation: {corr_value:.2f}")
            hover_text.append(hover_row)
        return hover_text

    def _get_consistent_language_data(self) -> Dict[str, int]:
        """Process language data with consistency checks to avoid inflated LOC counts"""
        total_loc_sum = self._calculate_total_loc()
        all_languages = defaultdict(int)
        scaled_repos = 0

        for repo in self.non_empty_repos:
            scaled_repos += self._process_repository_languages(repo, all_languages)

        self._log_scaling_summary(scaled_repos)
        self._adjust_language_totals(all_languages, total_loc_sum)
        return all_languages

    def _calculate_total_loc(self) -> int:
        """Calculate total lines of code across all repositories"""
        total_loc_sum = sum(repo.total_loc for repo in self.non_empty_repos)
        logger.info(f"Total LOC across repositories: {total_loc_sum:,}")
        return total_loc_sum

    def _process_repository_languages(self, repo: RepoStats, all_languages: Dict[str, int]) -> int:
        """Process language data for a single repository, returning 1 if scaling was applied, 0 otherwise"""
        lang_sum = sum(repo.languages.values())

        if lang_sum == 0:
            self._handle_missing_language_data(repo, all_languages)
            return 0

        if self._needs_scaling(repo, lang_sum):
            self._apply_language_scaling(repo, all_languages, lang_sum)
            return 1
        else:
            self._add_unscaled_languages(repo, all_languages)
            return 0

    @staticmethod
    def _handle_missing_language_data(repo: RepoStats, all_languages: Dict[str, int]) -> None:
        """Handle repositories with no language data but positive LOC"""
        if repo.total_loc > 0:
            all_languages["Unknown"] += repo.total_loc
            logger.info(
                f"Adding {repo.total_loc} LOC from {repo.name} to 'Unknown' language (no language data)")

    @staticmethod
    def _needs_scaling(repo: RepoStats, lang_sum: int) -> bool:
        """Check if repository language data needs scaling due to inconsistency"""
        return lang_sum > repo.total_loc * 1.1

    @staticmethod
    def _apply_language_scaling(repo: RepoStats, all_languages: Dict[str, int], lang_sum: int) -> None:
        """Apply scaling factor to repository language data"""
        scaling_factor = repo.total_loc / lang_sum
        logger.info(
            f"Repository {repo.name} has inconsistent language data. Scaling by factor {scaling_factor:.4f}")

        for lang, loc in repo.languages.items():
            all_languages[lang] += int(loc * scaling_factor)

    @staticmethod
    def _add_unscaled_languages(repo: RepoStats, all_languages: Dict[str, int]) -> None:
        """Add repository language data without scaling"""
        for lang, loc in repo.languages.items():
            all_languages[lang] += loc

    @staticmethod
    def _log_scaling_summary(scaled_repos: int) -> None:
        """Log summary of scaling operations"""
        if scaled_repos > 0:
            logger.info(f"Scaled language data for {scaled_repos} repositories with inconsistent totals")

    @staticmethod
    def _adjust_language_totals(all_languages: Dict[str, int], total_loc_sum: int) -> None:
        """Adjust language totals to match expected LOC sum"""
        lang_loc_sum = sum(all_languages.values())
        logger.info(f"Sum of language-specific LOC: {lang_loc_sum:,}")

        if lang_loc_sum != total_loc_sum:
            logger.info(f"Adjusting language data to match total LOC: {total_loc_sum:,}")
            if lang_loc_sum < total_loc_sum:
                difference = total_loc_sum - lang_loc_sum
                all_languages["Unknown"] = all_languages.get("Unknown", 0) + difference
                logger.info(f"Added {difference:,} missing LOC to 'Unknown' language")
            elif lang_loc_sum > total_loc_sum:
                scaling_factor = total_loc_sum / lang_loc_sum
                logger.info(f"Scaling all language LOC by factor of {scaling_factor:.4f} to match total LOC")
                for lang in all_languages:
                    all_languages[lang] = int(all_languages[lang] * scaling_factor)


# noinspection PyTypeChecker
class CreateDetailedCharts:
    """Class responsible for creating detailed charts for the visualization dashboard"""

    def __init__(self, all_stats: List[RepoStats], theme: ThemeConfig, reports_dir: Optional[Path] = None):
        """Initialize the detailed charts with all repository statistics"""
        self.all_stats = all_stats
        self.theme = theme
        self.reports_dir = reports_dir if reports_dir is not None else Path("reports/static")

        # Ensure the reports directory exists
        os.makedirs(self.reports_dir, exist_ok=True)

    def create(self) -> None:
        """Create all detailed charts"""
        # Filter out empty repositories for most visualizations
        empty_repos = [s for s in self.all_stats if "Empty repository with no files" in s.anomalies]
        non_empty_repos = [s for s in self.all_stats if "Empty repository with no files" not in s.anomalies]

        # Set colors from theme
        chart_colors = self.theme["chart_palette"]

        # Skip visualizations if not enough data
        if len(non_empty_repos) == 0:
            logger.warning("No non-empty repositories to visualize")
            return

        # Create all detailed visualizations
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
        timeline_creator = RepositoryTimelineCreator(self.all_stats, self.reports_dir)
        timeline_creator.create_timeline()

    def _create_language_evolution(self, non_empty_repos: List[RepoStats]) -> None:
        """Create language evolution chart showing how language usage has changed over time"""
        evolution_creator = LanguageEvolutionCreator(non_empty_repos, self.reports_dir)
        evolution_creator.create_evolution_chart()

    def _create_maintenance_quality_heatmap(self, non_empty_repos: List[RepoStats]) -> None:
        """Create heatmap showing maintenance quality factors for top repositories"""
        heatmap_creator = MaintenanceQualityHeatmapCreator(non_empty_repos, self.reports_dir)
        heatmap_creator.create_heatmap()

    def _create_empty_vs_nonempty_pie(self, empty_repos: List[RepoStats], non_empty_repos: List[RepoStats]) -> None:
        """Create pie chart showing empty vs non-empty repository distribution"""
        if not empty_repos:
            return

        labels = ['Non-Empty Repositories', 'Empty Repositories']
        sizes = [len(non_empty_repos), len(empty_repos)]
        colors = ['#66b3ff', '#ff9999']

        # Calculate percentages for hover text
        total = sum(sizes)
        percentages = [f"{(size / total) * 100:.1f}%" for size in sizes]

        # Create hover text
        hover_text = [f"{label}<br>{size} repos<br>{percentage}"
                      for label, size, percentage in zip(labels, sizes, percentages)]

        # Create plotly figure
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=sizes,
            marker=dict(colors=colors),
            textinfo='percent',
            hoverinfo='text',
            hovertext=hover_text,
            hole=0.3,  # Create a donut chart for modern look
            pull=[0.05, 0]  # Slightly pull out the first slice
        )])

        # Update layout
        fig.update_layout(
            title='Empty vs Non-Empty Repositories',
            height=600,
            width=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5
            )
        )

        # Save the figure using the utility function
        save_figure(fig, 'empty_repos_chart', self.reports_dir)

    def _create_repository_types_distribution(self) -> None:
        """Create chart showing distribution of repository types"""
        # Count different repository types
        repo_types = {
            'Regular': sum(1 for s in self.all_stats if not (s.is_fork or s.is_archived or s.is_template)),
            'Forks': sum(1 for s in self.all_stats if s.is_fork),
            'Archived': sum(1 for s in self.all_stats if s.is_archived),
            'Templates': sum(1 for s in self.all_stats if s.is_template),
            'Private': sum(1 for s in self.all_stats if s.is_private),
            'Public': sum(1 for s in self.all_stats if not s.is_private)
        }

        # Extract data for the bar chart
        types = list(repo_types.keys())
        counts = list(repo_types.values())

        # Create plotly figure
        fig = go.Figure(data=[go.Bar(
            x=types,
            y=counts,
            marker_color=self.theme["chart_palette"][:len(repo_types)],
            text=counts,  # Show counts on bars
            textposition='auto',
            hovertemplate='Type: %{x}<br>Count: %{y}<extra></extra>'
        )])

        # Update layout
        fig.update_layout(
            title='Repository Types Distribution',
            xaxis_title='Repository Type',
            yaxis_title='Count',
            height=600,
            width=800
        )

        # Add grid lines
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

        # Save the figure using the utility function
        save_figure(fig, 'repo_types_distribution', self.reports_dir)

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

        # Create z values for the heatmap (commits count)
        z_data = []
        for year in years:
            row = [commit_data.get((year, month), 0) for month in range(12)]
            z_data.append(row)

        # Create custom hover text
        hover_text = []
        for year in years:
            hover_row = []
            for month in range(12):
                count = commit_data.get((year, month), 0)
                hover_row.append(f"Year: {year}<br>Month: {month_names[month]}<br>Commits: {count}")
            hover_text.append(hover_row)

        # Create plotly figure
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=month_names,
            y=years,
            colorscale='YlGnBu',
            text=z_data,  # Show commit counts as text
            texttemplate="%{text}",
            hoverinfo='text',
            hovertext=hover_text,
            colorbar=dict(title='Commit Count')
        ))

        # Update layout
        fig.update_layout(
            title='Repository Commit Activity by Month',
            xaxis_title='Month',
            yaxis_title='Year',
            xaxis=dict(side='top'),  # Show month names at the top like in seaborn
            height=max(500, len(years) * 40 + 150)  # Dynamic height based on number of years
        )

        # Save the figure using the utility function
        save_figure(fig, 'commit_activity_heatmap', self.reports_dir)

    def _create_top_repositories_by_metrics(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create charts showing top 10 repositories by various metrics"""
        if len(non_empty_repos) < 3:
            return

        # Create subplot with 2x2 grid
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                'Top 10 Repositories by Size (LOC)',
                'Top 10 Repositories by Stars',
                'Top 10 Repositories by Maintenance Score',
                'Top 10 Repositories by Contributors'
            ),
            vertical_spacing=0.12
        )

        # Top 10 by Size (LOC)
        top_by_loc = sorted(non_empty_repos, key=lambda x: x.total_loc, reverse=True)[:10]
        names_loc = [r.name for r in top_by_loc]
        locs = [r.total_loc for r in top_by_loc]

        fig.add_trace(
            go.Bar(
                x=locs,
                y=names_loc,
                orientation='h',
                marker_color=chart_colors[0],
                text=[f"{loc:,}" for loc in locs],
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Lines of Code: %{x:,}<extra></extra>'
            ),
            row=1, col=1
        )

        # Top 10 by Stars
        top_by_stars = sorted(non_empty_repos, key=lambda x: x.stars, reverse=True)[:10]
        names_stars = [r.name for r in top_by_stars]
        stars = [r.stars for r in top_by_stars]

        fig.add_trace(
            go.Bar(
                x=stars,
                y=names_stars,
                orientation='h',
                marker_color=chart_colors[1],
                text=stars,
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Stars: %{x}<extra></extra>'
            ),
            row=1, col=2
        )

        # Top 10 by Maintenance Score
        top_by_maint = sorted(non_empty_repos, key=lambda x: x.maintenance_score, reverse=True)[:10]
        names_maint = [r.name for r in top_by_maint]
        maint_scores = [r.maintenance_score for r in top_by_maint]

        fig.add_trace(
            go.Bar(
                x=maint_scores,
                y=names_maint,
                orientation='h',
                marker_color=chart_colors[2],
                text=[f"{score:.1f}" for score in maint_scores],
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Maintenance Score: %{x:.1f}<extra></extra>'
            ),
            row=2, col=1
        )

        # Top 10 by Contributors
        top_by_contrib = sorted(non_empty_repos, key=lambda x: x.contributors_count, reverse=True)[:10]
        names_contrib = [r.name for r in top_by_contrib]
        contribs = [r.contributors_count for r in top_by_contrib]

        fig.add_trace(
            go.Bar(
                x=contribs,
                y=names_contrib,
                orientation='h',
                marker_color=chart_colors[3],
                text=contribs,
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Contributors: %{x}<extra></extra>'
            ),
            row=2, col=2
        )

        # Update layout
        fig.update_layout(
            height=800,
            width=1000,
            showlegend=False,
            title_text="Repository Metrics Comparison"
        )

        # Update axes
        fig.update_xaxes(title_text="Lines of Code", row=1, col=1)
        fig.update_xaxes(title_text="Stars", row=1, col=2)
        fig.update_xaxes(title_text="Maintenance Score", row=2, col=1)
        fig.update_xaxes(title_text="Contributors Count", row=2, col=2)

        # Save the figure using the utility function
        save_figure(fig, 'top_repos_metrics', self.reports_dir)

    def _create_score_correlation_matrix(self, non_empty_repos: List[RepoStats]) -> None:
        """Create a correlation matrix of various metrics"""
        correlation_scorer = CorrelationScorer(non_empty_repos, self.reports_dir)
        correlation_scorer.create_correlation_matrix()

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

        # Create a temporary file for the wordcloud image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            wordcloud.to_file(tmp.name)
            tmp_filename = tmp.name

        # Convert the wordcloud image to a format plotly can use
        img = Image.open(tmp_filename)

        # Create a plotly figure with the wordcloud image
        fig = go.Figure()

        # Add the image
        fig.add_layout_image(
            dict(
                source=img,
                x=0,
                y=1,
                xref="paper",
                yref="paper",
                sizex=1,
                sizey=1,
                sizing="stretch",
                opacity=1,
                layer="below"
            )
        )

        # Update layout to make it look nice
        fig.update_layout(
            title='Repository Topics WordCloud',
            width=800,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
        )

        # Remove axes and grid
        fig.update_xaxes(visible=False, showticklabels=False, showgrid=False, zeroline=False)
        fig.update_yaxes(visible=False, showticklabels=False, showgrid=False, zeroline=False)

        # Save the figure using the utility function
        save_figure(fig, 'topics_wordcloud', self.reports_dir)

        # Clean up the temporary file
        os.unlink(tmp_filename)

    def _create_active_inactive_age_distribution(self, non_empty_repos: List[RepoStats],
                                                 chart_colors: List[str]) -> None:
        """Create histogram showing age distribution of active vs inactive repositories"""
        if not non_empty_repos:
            return

        # Separate active and inactive repos
        active_repos = [r for r in non_empty_repos if r.is_active]
        inactive_repos = [r for r in non_empty_repos if not r.is_active]

        # Calculate ages in years
        active_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in active_repos]
        inactive_ages = [(datetime.now().replace(tzinfo=timezone.utc) - r.created_at).days / 365.25 for r in
                         inactive_repos]

        # Create figure
        fig = go.Figure()

        # Add histograms
        if active_ages:
            fig.add_trace(go.Histogram(
                x=active_ages,
                nbinsx=15,
                opacity=0.7,
                name='Active',
                marker_color=chart_colors[0],
                hovertemplate='Age: %{x:.1f} years<br>Count: %{y}<extra>Active Repositories</extra>'
            ))

        if inactive_ages:
            fig.add_trace(go.Histogram(
                x=inactive_ages,
                nbinsx=15,
                opacity=0.7,
                name='Inactive',
                marker_color=chart_colors[1],
                hovertemplate='Age: %{x:.1f} years<br>Count: %{y}<extra>Inactive Repositories</extra>'
            ))

        # Update layout
        fig.update_layout(
            title='Age Distribution: Active vs Inactive Repositories',
            xaxis_title='Repository Age (Years)',
            yaxis_title='Count',
            barmode='overlay',  # Overlay histograms
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Add grid lines
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

        # Save the figure using the utility function
        save_figure(fig, 'active_inactive_age', self.reports_dir)

    def _create_stars_vs_issues_scatter(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create scatter plot showing relationship between stars and open issues"""
        if not non_empty_repos:
            return

        scatter_data = self._extract_scatter_data(non_empty_repos, chart_colors)
        fig = self._create_scatter_figure(scatter_data)
        self._add_scatter_annotations(fig, scatter_data)
        self._configure_scatter_layout(fig, scatter_data)
        save_figure(fig, 'stars_vs_issues', self.reports_dir)

    @staticmethod
    def _extract_scatter_data(non_empty_repos: List[RepoStats], chart_colors: List[str]) -> Dict:
        """Extract and prepare data for the scatter plot"""
        stars = [r.stars for r in non_empty_repos]
        issues = [r.open_issues for r in non_empty_repos]
        names = [r.name for r in non_empty_repos]
        is_active = [r.is_active for r in non_empty_repos]

        # Create a list of colors based on active status
        colors = [chart_colors[0] if active else chart_colors[1] for active in is_active]

        # Determine if we need logarithmic scales
        use_log_x = max(stars) > 100 * min([s for s in stars if s > 0] or [1])
        use_log_y = max(issues) > 100 * min([i for i in issues if i > 0] or [1])

        # Create custom hover text
        hover_texts = [
            f"Repository: {name}<br>Stars: {star}<br>Issues: {issue}<br>Status: {'Active' if active else 'Inactive'}"
            for name, star, issue, active in zip(names, stars, issues, is_active)]

        return {
            'stars': stars,
            'issues': issues,
            'names': names,
            'is_active': is_active,
            'colors': colors,
            'use_log_x': use_log_x,
            'use_log_y': use_log_y,
            'hover_texts': hover_texts
        }

    @staticmethod
    def _create_scatter_figure(scatter_data: Dict) -> go.Figure:
        """Create the scatter plot figure"""
        fig = go.Figure()

        # Add scatter plot
        fig.add_trace(go.Scatter(
            x=scatter_data['stars'],
            y=scatter_data['issues'],
            mode='markers',
            marker=dict(
                size=12,
                color=scatter_data['colors'],
                opacity=0.7,
                line=dict(width=1, color='DarkSlateGrey')
            ),
            text=scatter_data['hover_texts'],
            hoverinfo='text'
        ))

        return fig

    @staticmethod
    def _add_scatter_annotations(fig: go.Figure, scatter_data: Dict) -> None:
        """Add annotations for repositories with many stars or issues"""
        stars = scatter_data['stars']
        issues = scatter_data['issues']
        names = scatter_data['names']

        threshold_stars = np.percentile(stars, 90) if len(stars) > 10 else 0
        threshold_issues = np.percentile(issues, 90) if len(issues) > 10 else 0

        for i, (name, s, iss) in enumerate(zip(names, stars, issues)):
            if s > threshold_stars or iss > threshold_issues:
                fig.add_annotation(
                    x=s,
                    y=iss,
                    text=name,
                    showarrow=False,
                    font=dict(size=10),
                    xshift=10,
                    yshift=10
                )

    @staticmethod
    def _configure_scatter_layout(fig: go.Figure, scatter_data: Dict) -> None:
        """Configure the layout for the scatter plot"""
        fig.update_layout(
            title='Repository Popularity vs. Maintenance Burden',
            xaxis_title='Stars',
            yaxis_title='Open Issues',
            hovermode='closest',
            xaxis=dict(
                type='log' if scatter_data['use_log_x'] else 'linear',
                showgrid=True
            ),
            yaxis=dict(
                type='log' if scatter_data['use_log_y'] else 'linear',
                showgrid=True
            )
        )

    def _create_repository_creation_timeline(self, chart_colors: List[str]) -> None:
        """Create timeline showing repository creation over time"""
        if not self.all_stats:
            return

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

        # Create plotly figure
        fig = go.Figure()

        # Add bar chart
        fig.add_trace(go.Bar(
            x=plot_dates,
            y=counts,
            marker_color=chart_colors[0],
            opacity=0.8,
            hovertemplate='Date: %{x|%Y-%m}<br>New Repositories: %{y}<extra></extra>'
        ))

        # Add trend line (smoothed moving average) if enough data points
        if len(counts) > 3:
            from scipy.ndimage import gaussian_filter1d
            smoothed = gaussian_filter1d(counts, sigma=1.5)

            fig.add_trace(go.Scatter(
                x=plot_dates,
                y=smoothed,
                mode='lines',
                line=dict(color='red', width=2),
                opacity=0.7,
                name='Trend',
                hovertemplate='Date: %{x|%Y-%m}<br>Trend: %{y:.1f}<extra></extra>'
            ))

        # Update layout
        fig.update_layout(
            title='Repository Creation Timeline',
            xaxis_title='Date',
            yaxis_title='New Repositories',
            hovermode='closest',
            showlegend=False
        )

        # Format x-axis with dates
        fig.update_xaxes(
            tickformat='%Y-%m',
            tickangle=45,
            tickmode='auto',
            nticks=20
        )

        # Add grid
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)')

        # Save the figure using the utility function
        save_figure(fig, 'repo_creation_timeline', self.reports_dir)

    def _create_documentation_quality_distribution(self, non_empty_repos: List[RepoStats],
                                                   chart_colors: List[str]) -> None:
        """Create charts showing distribution of documentation and README quality"""
        if not non_empty_repos:
            return

        # Create subplots with 1 row and 2 columns
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=('Documentation Size Distribution', 'README Comprehensiveness Distribution')
        )

        # Documentation Size Distribution
        docs_categories = Counter(r.docs_size_category for r in non_empty_repos)
        # Sort categories in logical order
        category_order = ["None", "Small", "Intermediate", "Big"]
        docs_data = [docs_categories.get(cat, 0) for cat in category_order]

        # Add bar chart for documentation size
        fig.add_trace(
            go.Bar(
                x=category_order,
                y=docs_data,
                marker_color=chart_colors[:len(category_order)],
                text=docs_data,  # Show counts on bars
                textposition='auto',
                hovertemplate='Category: %{x}<br>Count: %{y}<extra></extra>'
            ),
            row=1, col=1
        )

        # README Comprehensiveness Distribution
        readme_categories = Counter(r.readme_comprehensiveness for r in non_empty_repos)
        # Sort categories in logical order
        readme_order = ["None", "Small", "Good", "Comprehensive"]
        readme_data = [readme_categories.get(cat, 0) for cat in readme_order]

        # Add bar chart for README comprehensiveness
        fig.add_trace(
            go.Bar(
                x=readme_order,
                y=readme_data,
                marker_color=chart_colors[3:3 + len(readme_order)],
                text=readme_data,  # Show counts on bars
                textposition='auto',
                hovertemplate='Category: %{x}<br>Count: %{y}<extra></extra>'
            ),
            row=1, col=2
        )

        # Update layout
        fig.update_layout(
            height=500,
            width=1000,
            showlegend=False,
        )

        # Update y-axis titles
        fig.update_yaxes(title_text="Number of Repositories", row=1, col=1)
        fig.update_yaxes(title_text="Number of Repositories", row=1, col=2)

        # Save the figure using the utility function
        save_figure(fig, 'documentation_quality', self.reports_dir)

    def _create_infrastructure_quality_metrics(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create charts for infrastructure quality and other detailed metrics"""
        if not non_empty_repos:
            return

        # Create individual metric charts using the DetailedChartCreator class
        chart_creator = InfrastructureQualityMetricsCreator(non_empty_repos, chart_colors, self.reports_dir,
                                                            self.all_stats)

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

    def _create_release_counts(self, non_empty_repos: List[RepoStats], chart_colors: List[str]) -> None:
        """Create bar chart showing repositories with most releases"""
        repos_with_releases = [r for r in non_empty_repos if r.has_releases and r.release_count > 0]
        if len(repos_with_releases) >= 3:  # Only create if we have at least 3 repos with releases
            # Sort by release count
            top_by_releases = sorted(repos_with_releases, key=lambda x: x.release_count, reverse=True)[:15]

            names = [r.name for r in top_by_releases]
            release_counts = [r.release_count for r in top_by_releases]

            # Create horizontal bar chart using plotly
            fig = go.Figure(data=go.Bar(
                x=release_counts,
                y=names,
                orientation='h',
                marker_color=chart_colors[2],
                text=release_counts,  # Show counts on bars
                textposition='auto',
                hovertemplate='Repository: %{y}<br>Releases: %{x}<extra></extra>'
            ))

            # Update layout
            fig.update_layout(
                title='Repositories with Most Releases',
                xaxis_title='Number of Releases',
                height=max(600, len(top_by_releases) * 30),  # Dynamic height based on number of repos
                margin=dict(l=150, r=20, t=50, b=50),  # Add margin for long repo names
                yaxis=dict(
                    autorange="reversed"  # Show highest count at the top
                )
            )

            # Save the figure using the utility function
            save_figure(fig, 'release_counts', self.reports_dir)
