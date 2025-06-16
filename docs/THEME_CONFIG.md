# 🎨 Theme Configuration

GHRepoLens provides extensive customization options through its ThemeConfig system, allowing you to create personalized visualization dashboards that match your style and preferences.

## 🎯 Core Configuration Options

### 🎨 Color Schemes
- `primary_color` - Main brand color (hex format)
- `secondary_color` - Secondary brand color (hex format)
- `accent_color` - Accent color for highlights (hex format)

### ☀️ Light Mode Colors
- `light_bg_color` - Light mode background color
- `light_text_color` - Light mode text color
- `light_card_bg` - Light mode card background color
- `light_chart_bg` - Light mode chart background color

### 🌙 Dark Mode Colors
- `dark_bg_color` - Dark mode background color 
- `dark_text_color` - Dark mode text color
- `dark_card_bg` - Dark mode card background color
- `dark_chart_bg` - Dark mode chart background color

### 📝 Typography
- `font_family` - Main font family string (CSS format)
- `heading_font` - Font for headings (CSS format)
- `code_font` - Font for code sections (CSS format)

### 🎯 UI Elements
- `border_radius` - Border radius for cards/buttons
- `shadow_style` - Shadow style for elements

### 📊 Chart Colors
- `chart_palette` - List of colors for charts (hex format)

### 🔝 Header
- `header_gradient` - CSS gradient for header

### 👤 User Information
- `user_avatar` - Path to user avatar image
- `user_name` - User's name to display
- `user_title` - User's title/role
- `user_bio` - User's bio

### 🛠️ Skills & Social Media
- `skills` - Dictionary of skills with name and URL
- `social_links` - Dictionary of social media links with name, URL, icon, and color

### 🎬 Custom Background
- `background_html_path` - Path to HTML file for custom background

## 🚀 Implementation Guide

### 1️⃣ Basic Theme Configuration
```python
from config import DefaultTheme

# Get default theme
theme = DefaultTheme.get_default_theme()

# Set basic colors
theme["primary_color"] = "#4f46e5"
theme["secondary_color"] = "#8b5cf6"
theme["accent_color"] = "#f97316"
```

### 2️⃣ User Profile Customization
```python
# Add user information
theme["user_name"] = "Jane Doe"
theme["user_title"] = "Senior Data Scientist"
theme["user_bio"] = "GitHub Analytics Expert" 
theme["user_avatar"] = "static/assets/profile.jpg"
```

### 3️⃣ Skills Configuration
```python
# Define skills with links
theme["skills"] = {
    "Python": "https://www.python.org",
    "Data Science": "https://en.wikipedia.org/wiki/Data_science",
    "Machine Learning": "https://en.wikipedia.org/wiki/Machine_learning"
}
```

### 4️⃣ Social Links Setup
```python
# Configure social media presence
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
```

### 5️⃣ Custom Background
```python
# Set custom HTML background
theme["background_html_path"] = "path/to/background.html"
```

## 🎨 HTML Background Guide

### Structure
Your HTML background file should include:
```html
<!DOCTYPE html>
<html>
<head>
    <!-- CSS Styles -->
    <style>
        /* Your styles here */
    </style>
</head>
<body>
    <!-- Visual Elements -->
    <div id="background-content"></div>
    
    <!-- JavaScript -->
    <script>
        // Your interactive code here
    </script>
</body>
</html>
```

### Example: Particle Background
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

## 🔌 Available Icons

### Social Media Icons
- `github` - GitHub icon
- `linkedin` - LinkedIn icon
- `globe` - Website/Portfolio icon

### Custom Icons
To add more icons:
1. Modify `_html.py`
2. Add icon SVG definition
3. Update `create_creator_section` method

## 💡 Best Practices

### Color Selection
- Use accessible color combinations
- Maintain sufficient contrast ratios
- Consider color-blind users
- Test in both light and dark modes

### Typography
- Use web-safe font stacks
- Include fallback fonts
- Consider font loading performance
- Test different screen sizes

### Performance
- Optimize background animations
- Minimize CSS complexity
- Use efficient selectors
- Test on various devices

## 🔍 Troubleshooting

### Common Issues
1. **Missing Assets**
   - Verify file paths
   - Check file permissions
   - Use relative paths when possible

2. **Style Conflicts**
   - Check specificity
   - Use unique class names
   - Test style inheritance

3. **Background Issues**
   - Verify HTML syntax
   - Check script loading
   - Test in multiple browsers

## 📚 Related Documentation
- [Quick Start Guide](QUICK_START.md)
- [Colab Usage](COLAB_USAGE.md)
- [Recent Changes](CHANGES.md)

---

Happy theming! 🎨
