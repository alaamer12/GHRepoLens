# Using GitHub Repository Analyzer in Google Colab

This guide explains how to run the GitHub Repository Analyzer in Google Colab.

## Setup Instructions

1. **Upload Project Files to Google Colab**

   You need to upload the project files to Google Colab. You can do this in two ways:

   - **Option 1**: Upload the files directly from your computer
   - **Option 2**: Clone the repository from GitHub

   For Option 2, run the following in a Colab cell:
   ```python
   !git clone https://github.com/your-username/GHRepoLens.git
   %cd GHRepoLens
   ```

2. **Set GitHub Token and Username**

   Set your GitHub token and username as environment variables:
   ```python
   import os
   os.environ["GITHUB_TOKEN"] = "your-github-token"
   os.environ["GITHUB_USERNAME"] = "your-github-username"
   ```

## Running the Analyzer

### Quick Method (Recommended)

Use the `colab_runner.py` script which handles all the necessary setup:

```python
from colab_runner import run_colab

# Run with environment variables
run_colab()

# Or provide token and username directly
run_colab(
    github_token="your-github-token",
    github_username="your-github-username",
    mode="quicktest"  # Choose from: "quicktest", "test", "demo", "full"
)
```

### Alternative Method

If you prefer to run the analyzer directly:

```python
# Install required dependencies
!pip install nest-asyncio PyGithub rich

# Import necessary modules
from main import run_analysis
import asyncio
import nest_asyncio
import os

# Apply nest_asyncio to avoid event loop issues
nest_asyncio.apply()

# Set GitHub credentials
github_token = "your-github-token"  # or use os.environ.get("GITHUB_TOKEN")
github_username = "your-github-username"  # or use os.environ.get("GITHUB_USERNAME")

# Run the analyzer
asyncio.run(
    run_analysis(
        token=github_token,
        username=github_username,
        mode="quicktest",  # Choose from: "quicktest", "test", "demo", "full" 
        include_orgs=["JsonAlchemy", "T2F-Labs"],  # Optional: organizations to include
        visibility="all"  # Choose from: "all", "public", "private"
    )
)
```

## Analysis Modes

- **`quicktest`**: Analyzes 1 personal repository and 1 repository from each predefined organization
- **`test`**: Analyzes a single repository
- **`demo`**: Analyzes up to 10 repositories
- **`full`**: Analyzes all available repositories (may take time)

## Troubleshooting

If you encounter any issues:

1. **Make sure you have a valid GitHub token** with appropriate permissions
2. **Check if the GitHub username exists** and is spelled correctly
3. **Verify network connectivity** in the Colab environment
4. **Check for rate limiting** - GitHub API has usage limits
5. **Look for error messages** in the output for specific issues

## Sample Notebook

Here's a minimal example to run the analyzer:

```python
# Install dependencies if not already installed
try:
    import nest_asyncio
    import github
    from rich.console import Console
except ImportError:
    !pip install nest-asyncio PyGithub rich

# Clone repository if needed
!git clone https://github.com/your-username/GHRepoLens.git
%cd GHRepoLens

# Import runner and run analysis
from colab_runner import run_colab

# Set GitHub credentials
import os
os.environ["GITHUB_TOKEN"] = "your-github-token"
os.environ["GITHUB_USERNAME"] = "your-github-username"

# Run the analyzer in quicktest mode
run_colab(mode="quicktest")
``` 