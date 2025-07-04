from pathlib import Path
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from console import console, print_header

# Define the reports directory
reports_dir = Path("reports")

# List of chart names to check
chart_names = [
    "repository_timeline",
    "language_evolution",
    "quality_heatmap",
    "repo_types_distribution",
    "commit_activity_heatmap",
    "top_repos_metrics",
    "score_correlation_matrix",
    "topics_wordcloud",
    "active_inactive_age",
    "stars_vs_issues"
]

# Check each chart
print_header("Testing chart existence:")
for chart_name in chart_names:
    chart_path = reports_dir / f"{chart_name}.png"
    exists = chart_path.exists()
    status = "[green]EXISTS[/green]" if exists else "[red]MISSING[/red]"
    console.print(f"Chart '{chart_name}': {status} at {chart_path}")

# Report summary
print_header("\nSummary:")
console.print(f"Reports directory exists: {reports_dir.exists()}")
console.print(
    f"Total chart files found: {sum(1 for name in chart_names if (reports_dir / f'{name}.png').exists())}/{len(chart_names)}")
