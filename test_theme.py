#!/usr/bin/env python3
"""
Theme Config Test Script

This script demonstrates how to use the updated ThemeConfig functionality
to customize the visualization dashboard.
"""

from pathlib import Path

from config import DefaultTheme


def main():
    """Test custom theme configuration with HTML background and user info"""
    # Get the default theme as a starting point
    theme = DefaultTheme.get_default_theme()

    # Customize user information
    theme["user_name"] = "Jane Doe"
    theme["user_title"] = "Senior Data Scientist"
    theme["user_bio"] = "GitHub Analytics Expert"
    theme["user_avatar"] = "static/assets/profile.jpg"  # Make sure this file exists

    # Customize skills
    theme["skills"] = {
        "Python": "https://www.python.org",
        "Data Science": "https://en.wikipedia.org/wiki/Data_science",
        "Machine Learning": "https://en.wikipedia.org/wiki/Machine_learning",
        "GitHub API": "https://docs.github.com/en/rest",
        "Visualization": "https://plotly.com/",
    }

    # Customize social links
    theme["social_links"] = {
        "GitHub": {
            "url": "https://github.com/janedoe",
            "icon": "github",
            "color": "bg-gray-800"
        },
        "LinkedIn": {
            "url": "https://www.linkedin.com/in/janedoe/",
            "icon": "linkedin",
            "color": "bg-blue-600"
        },
        "Portfolio": {
            "url": "https://janedoe.dev",
            "icon": "globe",
            "color": "bg-emerald-600"
        }
    }

    # Set HTML background path (use absolute path)
    current_dir = Path(__file__).parent.absolute()
    theme["background_html_path"] = str(current_dir / "assets" / "background.html")

    print("Custom theme configuration:")
    print(f"  User name: {theme['user_name']}")
    print(f"  User title: {theme['user_title']}")
    print(f"  Background HTML: {theme['background_html_path']}")
    print(f"  Skills: {', '.join(theme['skills'].keys())}")
    print(f"  Social links: {', '.join(theme['social_links'].keys())}")

    print("\nYou can use this theme configuration with GithubVisualizer:")
    print("  visualizer = GithubVisualizer(username, reports_dir, theme)")


if __name__ == "__main__":
    main()
