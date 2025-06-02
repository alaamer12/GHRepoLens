# GHRepoLens Quick Start Guide

This quick start guide will walk you through setting up and running GHRepoLens with its latest features including environment variable management, asynchronous processing, and multiple analysis modes.

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/alaamer12/GHRepoLens.git
   cd GHRepoLens
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root with your GitHub credentials:
   ```
   GITHUB_TOKEN=your_personal_access_token
   GITHUB_USERNAME=your_github_username
   ```
   
   You can obtain a personal access token from [GitHub Settings](https://github.com/settings/tokens).
   Required scopes: `repo`

## Running GHRepoLens

Simply run the main script:

```bash
python main.py
```

The tool will automatically:
1. Load environment variables from your `.env` file
2. Display a welcome banner
3. Prompt you to select an analysis mode

### Analysis Modes

GHRepoLens offers three analysis modes:

1. **Demo Mode** 
   - Analyzes up to 10 repositories
   - Perfect for getting a quick overview
   - Good for testing the functionality
   - Select by entering `1` or `demo`

2. **Full Analysis** 
   - Analyzes all repositories for the specified user
   - Provides comprehensive results
   - May take significant time for users with many repositories
   - Select by entering `2` or `full`

3. **Test Mode** 
   - Analyzes only 1 repository
   - Designed for rapid testing and validation
   - Select by entering `3` or `test`

### Configuration Options

During execution, you will be asked if you want to use a custom configuration file. This allows you to override default settings for:

- Reports directory location
- Maximum workers for parallel processing
- Filtering options (forks, archived repos)
- Checkpointing behavior

For full details on configuration options, refer to the [README.md](README.md).

## Viewing Results

After running the analysis, you'll find the following in your `reports` directory:

- `repo_details.md` - Detailed per-repository analysis
- `aggregated_stats.md` - Summary statistics
- `visual_report.html` - Interactive dashboard with visualizations
- `repository_data.json` - Raw data for custom analysis
- Various chart images

## Troubleshooting

If you encounter GitHub API rate limit issues:
1. Wait for the rate limit to reset (usually 1 hour)
2. Use a different GitHub token
3. Run again later - the tool will resume from checkpoint

If you have other issues, check for error messages in the console and in the `logs` directory.

---

Happy analyzing! 🚀 