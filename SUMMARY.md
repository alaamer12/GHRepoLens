# ThemeConfig Enhancements Summary

## Changes Made

1. **Extended ThemeConfig**
   - Added support for user information (avatar, name, title, bio)
   - Added support for skills dictionary (name and URL)
   - Added support for social links dictionary (name, URL, icon, color)
   - Added support for custom HTML backgrounds via `background_html_path`

2. **Updated HTMLVisualizer**
   - Added HTML background loading and parsing
   - Modified the creator section to use theme data
   - Maintained backward compatibility
   - Added CSS and JavaScript injection for backgrounds

3. **Created Support Files**
   - `assets/background.html`: Example HTML background with particle animations
   - `test_theme.py`: Demonstration script for custom theme usage
   - `THEME_CONFIG.md`: Documentation for the theme configuration options

## New Features

### Custom User Information
Users can now customize their profile in the visualization dashboard:
```python
theme["user_name"] = "Jane Doe"
theme["user_title"] = "Data Scientist"
theme["user_bio"] = "GitHub Analytics Expert"
theme["user_avatar"] = "path/to/avatar.jpg"
```

### Skills and Technologies
Users can add their skills with links:
```python
theme["skills"] = {
    "Python": "https://www.python.org",
    "Data Science": "https://en.wikipedia.org/wiki/Data_science",
    "Machine Learning": "https://en.wikipedia.org/wiki/Machine_learning",
}
```

### Social Links
Users can add custom social links with icons:
```python
theme["social_links"] = {
    "GitHub": {
        "url": "https://github.com/username",
        "icon": "github",
        "color": "bg-gray-800"
    },
    "LinkedIn": {
        "url": "https://www.linkedin.com/in/username/",
        "icon": "linkedin",
        "color": "bg-blue-600"
    }
}
```

### HTML Backgrounds
Users can create custom animated HTML backgrounds:
```python
theme["background_html_path"] = "path/to/background.html"
```

## How to Use

1. Get the default theme:
```python
from config import DefaultTheme
theme = DefaultTheme.get_default_theme()
```

2. Customize the theme options:
```python
# Customize user information
theme["user_name"] = "Your Name"

# Set HTML background
theme["background_html_path"] = "path/to/background.html"
```

3. Use the theme with the visualizer:
```python
visualizer = GithubVisualizer(username, reports_dir, theme)
visualizer.create_visualizations(all_stats)
```

## Example

For a complete example, see `test_theme.py` in the repository.

## Documentation

For detailed documentation on all available theme options, see `THEME_CONFIG.md`. 