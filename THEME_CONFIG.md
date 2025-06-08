# Theme Configuration

The GitHub Repository Analyzer allows you to customize the appearance and information displayed in the generated visualization dashboard through the `ThemeConfig` system.

## Available Configuration Options

### Color Schemes
- `primary_color` - Main brand color (hex format)
- `secondary_color` - Secondary brand color (hex format)
- `accent_color` - Accent color for highlights (hex format)

### Light Mode Colors
- `light_bg_color` - Light mode background color
- `light_text_color` - Light mode text color
- `light_card_bg` - Light mode card background color
- `light_chart_bg` - Light mode chart background color

### Dark Mode Colors
- `dark_bg_color` - Dark mode background color 
- `dark_text_color` - Dark mode text color
- `dark_card_bg` - Dark mode card background color
- `dark_chart_bg` - Dark mode chart background color

### Typography
- `font_family` - Main font family string (CSS format)
- `heading_font` - Font for headings (CSS format)
- `code_font` - Font for code sections (CSS format)

### UI Elements
- `border_radius` - Border radius for cards/buttons
- `shadow_style` - Shadow style for elements

### Chart Colors
- `chart_palette` - List of colors for charts (hex format)

### Header
- `header_gradient` - CSS gradient for header

### User Information (NEW)
- `user_avatar` - Path to user avatar image
- `user_name` - User's name to display
- `user_title` - User's title/role
- `user_bio` - User's bio

### Skills and Social Media (NEW)
- `skills` - Dictionary of skills with name and URL
- `social_links` - Dictionary of social media links with name, URL, icon, and color

### Custom HTML Background (NEW)
- `background_html_path` - Path to HTML file for custom background

## Using Custom Themes

You can create and use a custom theme by modifying the default theme:

```python
from config import DefaultTheme

# Get default theme as a starting point
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
}

# Customize social links
theme["social_links"] = {
    "GitHub": {
        "url": "https://github.com/yourusername",
        "icon": "github", 
        "color": "bg-gray-800"
    },
    "LinkedIn": {
        "url": "https://www.linkedin.com/in/yourusername/", 
        "icon": "linkedin",
        "color": "bg-blue-600"
    }
}

# Set HTML background path
theme["background_html_path"] = "path/to/background.html"

# Use the theme with the visualizer
visualizer = GithubVisualizer(username, reports_dir, theme)
```

## HTML Background

You can create custom HTML backgrounds to add dynamic elements to your dashboard. The HTML file should be structured with:

1. CSS styles in the `<head>` section
2. Visual content in the `<body>` section
3. JavaScript for interactivity

The HTML will be parsed and split into these components, which will be inserted into the appropriate locations in the dashboard.

Example HTML background file:

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        .particles-container {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        .particle {
            position: absolute;
            background-color: rgba(99, 102, 241, 0.5);
            border-radius: 50%;
            animation: float 15s infinite ease-in-out;
        }
        @keyframes float {
            0% { transform: translateY(0); opacity: 0.1; }
            50% { transform: translateY(-100px); opacity: 0.5; }
            100% { transform: translateY(0); opacity: 0.1; }
        }
    </style>
</head>
<body>
    <div class="particles-container" id="particles-container"></div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Create dynamic background particles
            const container = document.getElementById('particles-container');
            for (let i = 0; i < 20; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.width = '50px';
                particle.style.height = '50px';
                particle.style.left = `${Math.random() * 100}%`;
                particle.style.top = `${Math.random() * 100}%`;
                container.appendChild(particle);
            }
        });
    </script>
</body>
</html>
```

## Available Icons for Social Links

The following icons are available for social links:
- `github` - GitHub icon
- `linkedin` - LinkedIn icon
- `globe` - Website/Portfolio icon

If you need additional icons, you'll need to modify the `create_creator_section` method in the `_html.py` file. 