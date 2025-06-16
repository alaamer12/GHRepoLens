# 🚀 Quick Start Guide

This guide will help you get started with GHRepoLens quickly and efficiently, walking you through the setup process and initial analysis.

## 🔰 Initial Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/alaamer12/GHRepoLens.git
   cd GHRepoLens
   ```

2. **Set Up Virtual Environment**
   ```bash
   # Create virtual environment
   python -m venv .venv

   # Activate virtual environment
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure GitHub Access**

   Create a `.env` file in the project root:
   ```ini
   GITHUB_TOKEN=your_personal_access_token
   GITHUB_USERNAME=your_github_username
   ```
   
   ℹ️ Get your personal access token from [GitHub Settings](https://github.com/settings/tokens)
   Required scope: `repo`

## 🎯 Running Your First Analysis

### Basic Usage
```bash
python main.py
```

The tool will automatically:
1. Load your GitHub credentials
2. Display a welcome message
3. Prompt you to select an analysis mode

### Analysis Modes

#### 1️⃣ Demo Mode
- Analyzes up to 10 repositories
- Perfect for initial testing
- Quick overview of features
- Select with `1` or `demo`

#### 2️⃣ Full Analysis
- Analyzes all accessible repositories
- Comprehensive results
- May take longer for many repos
- Select with `2` or `full`

#### 3️⃣ Test Mode
- Analyzes a single repository
- Rapid testing and validation
- Select with `3` or `test`

## ⚙️ Configuration Options

During execution, you'll be prompted to:

### 1. Choose Repository Visibility
- All repositories (public + private)
- Public repositories only
- Private repositories only

### 2. Use Custom Configuration
If enabled, you can customize:
- Reports directory location
- Maximum parallel workers
- Repository filters
- Checkpointing behavior

## 📊 Generated Reports

After analysis completion, check your `reports` directory for:

- `repo_details.md` - Detailed repository insights
- `aggregated_stats.md` - Summary statistics
- `visual_report.html` - Interactive visualizations
- `repository_data.json` - Raw analysis data
- Generated charts and visualizations

## 🔍 Troubleshooting

### API Rate Limiting
If you hit GitHub API rate limits:
1. Wait for rate limit reset (typically 1 hour)
2. Use a different GitHub token
3. Resume from last checkpoint

### Common Issues
- **Token Issues**: Ensure token has correct permissions
- **Network Problems**: Check internet connectivity
- **Memory Usage**: Close unnecessary applications
- **Disk Space**: Ensure at least 500MB free space

### Logging
- Check `logs` directory for detailed logs
- Latest log format: `ghlens_YYYYMMDD_HHMMSS.log`

## 🎓 Next Steps

- Explore [Theme Configuration](THEME_CONFIG.md) for customization
- Check [Recent Changes](CHANGES.md) for updates
- Try [Google Colab Usage](COLAB_USAGE.md) for cloud analysis

## 💡 Tips

1. **For Large Organizations**
   - Use Full Analysis mode during off-peak hours
   - Enable checkpointing for safety
   - Consider filtering out archived repositories

2. **For Quick Analysis**
   - Use Demo Mode for initial insights
   - Focus on active repositories
   - Filter out forks if needed

3. **For Best Performance**
   - Use a fresh GitHub token
   - Run on a stable internet connection
   - Close resource-intensive applications

Happy analyzing! 🚀
