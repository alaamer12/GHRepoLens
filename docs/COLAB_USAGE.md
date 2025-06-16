# 🌟 Google Colab Integration Guide

Welcome to the Google Colab integration guide for GHRepoLens. This guide explains how to run repository analysis in Google's cloud environment.

## 🚀 Quick Setup

### 1️⃣ Option 1: Direct Repository Clone
```python
# Clone the repository
!git clone https://github.com/alaamer12/GHRepoLens.git
%cd GHRepoLens

# Install dependencies
!pip install -q nest-asyncio PyGithub rich python-dotenv

# Set credentials
import os
os.environ["GITHUB_TOKEN"] = "your-github-token"
os.environ["GITHUB_USERNAME"] = "your-github-username"

# Import and run
from colab_runner import run_colab
run_colab(mode="quicktest")
```

### 2️⃣ Option 2: Upload Project Files
1. Download GHRepoLens from GitHub
2. Upload essential files to Colab:
   - `colab_runner.py`
   - `requirements.txt`
   - Core Python modules

## 🔧 Configuration Options

### Basic Configuration
```python
run_colab(
    github_token="your-token",      # GitHub personal access token
    github_username="your-username", # GitHub username
    mode="demo",                    # Analysis mode
    include_orgs=["org1", "org2"],  # Optional: organizations to analyze
    visibility="all"                # Repository visibility filter
)
```

### Analysis Modes
```python
# Demo Mode (10 repos max)
run_colab(mode="demo")

# Quick Test (1 repo)
run_colab(mode="quicktest")

# Full Analysis
run_colab(mode="full")

# Test Mode
run_colab(mode="test")
```

## 📊 Available Features

### Core Features
- ✅ Repository analysis
- ✅ Language statistics
- ✅ Commit history analysis
- ✅ Code quality metrics

### Colab-Specific Features
- 🔄 Automatic dependency installation
- 💾 Persistent storage support
- 📈 Interactive visualizations
- 🔌 Google Drive integration

### Limitations
- ⚠️ Runtime restrictions
- ⚠️ Memory constraints
- ⚠️ Storage limitations
- ⚠️ API rate limits

## 🛠️ Advanced Usage

### Custom Configuration
```python
from colab_runner import run_colab
import json

# Custom analysis configuration
config = {
    "REPORTS_DIR": "/content/reports",
    "MAX_WORKERS": 4,
    "SKIP_FORKS": True,
    "ANALYZE_CLONES": False
}

# Run with custom config
run_colab(
    config=config,
    mode="full",
    visibility="public"
)
```

### Google Drive Integration
```python
from google.colab import drive

# Mount Google Drive
drive.mount('/content/drive')

# Set custom reports directory
run_colab(
    reports_dir="/content/drive/MyDrive/GHRepoLens/reports",
    mode="full"
)
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Memory Errors
```python
# Reduce memory usage
run_colab(
    mode="demo",
    max_workers=2,
    skip_forks=True
)
```

#### 2. Runtime Disconnection
- Save progress frequently
- Use checkpointing
- Reduce analysis scope

#### 3. Rate Limiting
- Use token with higher limits
- Enable checkpointing
- Resume from last checkpoint

## 💡 Best Practices

### Performance Optimization
1. **Resource Management**
   - Clear output cells regularly
   - Restart runtime if memory high
   - Use appropriate batch sizes

2. **Storage Handling**
   - Clean up temporary files
   - Use Google Drive for persistence
   - Compress results when possible

3. **API Usage**
   - Monitor rate limits
   - Use incremental analysis
   - Enable caching when possible

### Example Notebook
```python
# Complete example with all features
from colab_runner import run_colab
from google.colab import drive
import os

# Setup
drive.mount('/content/drive')
!git clone https://github.com/alaamer12/GHRepoLens.git
%cd GHRepoLens
!pip install -r requirements.txt

# Configuration
os.environ["GITHUB_TOKEN"] = "your-token"
os.environ["GITHUB_USERNAME"] = "your-username"

# Run analysis
run_colab(
    mode="demo",
    reports_dir="/content/drive/MyDrive/GHRepoLens/reports",
    include_orgs=["your-org"],
    visibility="public",
    max_workers=2
)
```

## 📚 Additional Resources

- [Colab Documentation](https://colab.research.google.com/)
- [GitHub API Docs](https://docs.github.com/en/rest)
- [GHRepoLens Wiki](docs/QUICK_START.md)

## 🤝 Support

For issues and questions:
1. Check the [troubleshooting](#-troubleshooting) section
2. Visit our [GitHub Issues](https://github.com/alaamer12/GHRepoLens/issues)
3. Join our [Community Discussions](https://github.com/alaamer12/GHRepoLens/discussions)

---

Happy analyzing in the cloud! 🚀
