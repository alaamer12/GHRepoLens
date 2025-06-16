# 📘 GHRepoLens Usage Guide

## 🚀 Getting Started

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/alaamer12/GHRepoLens.git
cd GHRepoLens
```

## 🔑 Configuring GitHub Access

There are three ways to configure your GitHub credentials:

### Method 1: Environment Variables
Set the required environment variables in your system:
```bash
# Windows (Command Prompt)
set GITHUB_TOKEN=your_personal_access_token
set GITHUB_USERNAME=your_github_username

# Windows (PowerShell)
$env:GITHUB_TOKEN="your_personal_access_token"
$env:GITHUB_USERNAME="your_github_username"

# macOS/Linux
export GITHUB_TOKEN="your_personal_access_token"
export GITHUB_USERNAME="your_github_username"
```

### Method 2: .env File
Create a `.env` file in the project root directory:
```ini
GITHUB_TOKEN=your_personal_access_token
GITHUB_USERNAME=your_github_username
```

### Method 3: Google Colab Secrets (Colab Only)
When using Google Colab:
1. Go to Colab's left sidebar
2. Click on the key 🔑 icon to open "Secrets"
3. Add your credentials:
   - Name: `GITHUB_TOKEN`, Value: your token
   - Name: `GITHUB_USERNAME`, Value: your username

### Method 4: Configuration File
Create a `config.ini` file in the project root directory to customize the analysis behavior and output. You can copy the sample configuration from `config.ini.sample`:

```ini
[github]
token = your_github_token_here
username = your_username_here

[analysis]
reports_dir = reports              # Directory for generated reports
clone_dir = temp_repos            # Directory for temporary clones
max_workers = 4                   # Number of parallel workers
inactive_threshold_days = 180     # Days to consider a repo inactive
large_repo_loc_threshold = 1000   # Lines of code threshold for large repos

[filters]
skip_forks = false               # Whether to skip forked repositories
skip_archived = false            # Whether to skip archived repositories
include_private = true           # Include private repositories
visibility = all                 # Repository visibility (all/public/private)
analyze_clones = false           # Whether to clone repos for deeper analysis
include_orgs =                   # Comma-separated list of organizations

[checkpointing]
enable_checkpointing = true      # Enable checkpoint saving
checkpoint_file = github_analyzer_checkpoint.pkl
checkpoint_threshold = 100       # Number of repos before checkpoint
resume_from_checkpoint = true    # Resume from last checkpoint

[theme]
# Visual customization options
primary_color = #4f46e5         # Main brand color
secondary_color = #8b5cf6       # Secondary brand color
accent_color = #f97316         # Accent color for highlights
light_bg_color = #f9fafb       # Light mode background
light_text_color = #111827     # Light mode text
light_card_bg = #ffffff        # Light mode card background
light_chart_bg = #ffffff       # Light mode chart background
dark_bg_color = #111827        # Dark mode background
dark_text_color = #f9fafb      # Dark mode text
dark_card_bg = #1f2937         # Dark mode card background
dark_chart_bg = #1f2937        # Dark mode chart background
font_family = Inter, system-ui, sans-serif
heading_font = Inter, system-ui, sans-serif
code_font = Fira Code, monospace
border_radius = 0.5rem
shadow_style = 0 10px 15px -3px rgba(0, 0, 0, 0.1)
header_gradient = linear-gradient(135deg, #4f46e5 0%, #8b5cf6 50%, #f97316 100%)
chart_palette = ["#6366f1", "#a855f7", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"]

# User profile customization
user_avatar = static/assets/alaamer.jpg
user_name = Your Name
user_title = Your Title
user_bio = Your short bio here

# Custom background (optional)
background_html_path = 

# Skills and social links
skills = {"Python": "https://www.python.org", "Data Science": "https://en.wikipedia.org/wiki/Data_science"}
social_links = {
    "GitHub": {"url": "https://github.com/yourusername", "icon": "github", "color": "bg-gray-800"},
    "LinkedIn": {"url": "https://www.linkedin.com/in/yourusername/", "icon": "linkedin", "color": "bg-blue-600"}
}
```

#### Configuration Sections Explained:

1. **[github]**: Basic GitHub authentication settings
2. **[analysis]**: Core analysis parameters controlling report generation and processing
3. **[filters]**: Repository filtering options to control which repos are analyzed
4. **[checkpointing]**: Settings for saving progress during long analysis runs
5. **[theme]**: Visual customization options for the generated reports and dashboard
   - Color schemes for light/dark modes
   - Typography settings
   - UI element styling
   - User profile customization
   - Skills and social media links

To use a custom configuration file:

```bash
python main.py --config your_config.ini
```

Or when running in interactive mode, select "Yes" when prompted for using a custom config file.

## 🎯 Running the Tool

### Method 1: Command Line Interface
Run directly from the command line with various options:

```bash
# Basic usage (interactive mode)
python main.py

# Demo mode (analyze up to 10 repositories)
python main.py --mode demo

# Full analysis mode
python main.py --mode full

# Test mode (single repository)
python main.py --mode test

# With custom configuration file
python main.py --config custom_config.ini

# Resume from checkpoint
python main.py --resume

# Quick test mode (for development)
python main.py --quicktest
```

### Method 2: Module Import
You can also use GHRepoLens programmatically in your Python code:

```python
import asyncio
from main import main as run_analysis

# Run the analysis
if __name__ == "__main__":
    asyncio.run(run_analysis())
```

## 🔧 Configuration Options

### Method 1: Environment Variables
The following environment variables are supported:

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |
| `GITHUB_USERNAME` | GitHub Username | Yes |
| `GITHUB_VISIBILITY` | Repository visibility (all/public/private) | No |

### Method 2: .env File
Create a `.env` file in the project root directory:
```ini
GITHUB_TOKEN=your_personal_access_token
GITHUB_USERNAME=your_github_username
```

### Method 3: Google Colab Secrets (Colab Only)
When using Google Colab:
1. Go to Colab's left sidebar
2. Click on the key 🔑 icon to open "Secrets"
3. Add your credentials:
   - Name: `GITHUB_TOKEN`, Value: your token
   - Name: `GITHUB_USERNAME`, Value: your username

To use a custom configuration file:

```bash
python main.py --config your_config.ini
```

Or when running in interactive mode, select "Yes" when prompted for using a custom config file.

## 🎯 Running the Tool

### Method 1: Command Line Interface
Run directly from the command line with various options:

```bash
# Basic usage (interactive mode)
python main.py

# Demo mode (analyze up to 10 repositories)
python main.py --mode demo

# Full analysis mode
python main.py --mode full

# Test mode (single repository)
python main.py --mode test

# With custom configuration file
python main.py --config custom_config.ini

# Resume from checkpoint
python main.py --resume

# Quick test mode (for development)
python main.py --quicktest
```

### Method 2: Module Import
You can also use GHRepoLens programmatically in your Python code:

```python
import asyncio
from main import main as run_analysis

# Run the analysis
if __name__ == "__main__":
    asyncio.run(run_analysis())
```

## 📊 Output and Reports

After analysis completion, check the `reports` directory for:
- `repo_details.md` - Detailed repository insights
- `aggregated_stats.md` - Summary statistics
- `visual_report.html` - Interactive visualizations
- `repository_data.json` - Raw analysis data
- Generated charts and visualizations

## 🔍 Troubleshooting

### Common Issues
1. **Token Invalid/Expired**
   - Verify token has required scopes
   - Generate new token if expired
   - Check environment variables

2. **Rate Limiting**
   - Wait for rate limit reset
   - Use different token
   - Enable checkpointing

3. **Network Issues**
   - Check internet connection
   - Verify GitHub API accessibility
   - Try using a VPN if needed

For more detailed information, check the logs in the `logs` directory.
