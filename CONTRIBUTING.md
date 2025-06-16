# 🤝 Contributing to GHRepoLens

Thank you for your interest in contributing to GHRepoLens! This guide will help you get started with contributing to the project.

## 🎯 Ways to Contribute

### 🐛 Bug Reports
- Use the GitHub Issues page to report bugs
- Include detailed steps to reproduce
- Add system information and logs
- Tag with appropriate labels

### 💡 Feature Requests
- Check existing issues first
- Describe the feature clearly
- Explain the use case
- Provide examples if possible

### 📝 Code Contributions
- Fork the repository
- Create a feature branch
- Write clean, documented code
- Submit a pull request

## 🚀 Development Setup

### 1️⃣ Environment Setup
```bash
# Clone your fork
git clone https://github.com/yourusername/GHRepoLens.git
cd GHRepoLens

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2️⃣ Development Dependencies
```bash
pip install -r requirements-dev.txt
```

## 💻 Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/amazing-feature
```

### 2. Make Changes
- Follow coding standards
- Add/update tests
- Update documentation

### 3. Test Changes
```bash
# Run test suite
python -m pytest

# Run specific test
python -m pytest tests/test_specific.py
```

### 4. Commit Changes
```bash
git add .
git commit -m "feat: add amazing feature"
```

Use conventional commit messages:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring
- `style:` Code style
- `chore:` Maintenance

### 5. Push Changes
```bash
git push origin feature/amazing-feature
```

### 6. Submit Pull Request
- Fill out PR template
- Link related issues
- Add screenshots if relevant
- Request review

## 📋 Code Standards

### Python Style Guide
- Follow PEP 8
- Use type hints
- Maximum line length: 88 characters
- Use f-strings for formatting

### Documentation
- Update README.md if needed
- Add docstrings to functions
- Keep docs consistent with code
- Follow documentation style guide

### Testing
- Write unit tests for new features
- Maintain test coverage
- Test edge cases
- Update test documentation

## 🔍 Code Review Process

### Reviewer Guidelines
- Check code style
- Verify test coverage
- Validate documentation
- Test functionality

### Author Guidelines
- Respond to feedback promptly
- Make requested changes
- Update based on reviews
- Keep PR up to date

## 🏗️ Project Structure

### Core Modules
```
GHRepoLens/
├── analyzer.py      # Repository analysis
├── config.py       # Configuration handling
├── console.py      # Terminal interface
├── lens.py         # Core functionality
├── models.py       # Data models
├── reporter.py     # Report generation
└── utilities.py    # Helper functions
```

### Documentation
```
docs/
├── QUICK_START.md     # Getting started guide
├── THEME_CONFIG.md    # Theme customization
├── CHANGES.md         # Change log
└── COLAB_USAGE.md     # Google Colab guide
```

### Visualization
```
visualize/
├── charts.py          # Chart generation
├── repo_analyzer.py   # Data analysis
├── visualizer.py      # HTML generation
└── static/           # Static assets
```

## 🎨 Style Guide

### Code Formatting
```python
# Good
def calculate_metrics(repo: Repository) -> Dict[str, float]:
    """Calculate repository metrics.
    
    Args:
        repo: Repository object to analyze
        
    Returns:
        Dictionary of calculated metrics
    """
    metrics = {}
    return metrics

# Bad
def calculate_metrics(repo):
    metrics = {}
    return metrics
```

### Documentation Style
```python
# Good
class RepoAnalyzer:
    """Repository analysis functionality.
    
    Provides methods for analyzing GitHub repositories and generating
    metrics about code quality, activity, and structure.
    
    Attributes:
        client: GitHub API client instance
        config: Analysis configuration
    """

# Bad
class RepoAnalyzer:
    # Analyze repos
    pass
```

## 📦 Release Process

### Version Numbering
- Follow Semantic Versioning
- Format: MAJOR.MINOR.PATCH
- Update version in setup.py

### Release Steps
1. Update CHANGES.md
2. Create release branch
3. Update version number
4. Create GitHub release
5. Publish to PyPI

## ⚡ Performance Tips

### Optimization
- Use async/await for I/O
- Implement caching
- Optimize database queries
- Profile slow operations

### Memory Usage
- Close file handles
- Use generators for large data
- Implement cleanup handlers
- Monitor memory usage

## 🤝 Community

### Communication
- GitHub Issues for bugs
- Discussions for questions
- Pull Requests for changes
- Wiki for documentation

### Code of Conduct
We follow the [Contributor Covenant](https://www.contributor-covenant.org/):
- Be respectful and inclusive
- Accept constructive criticism
- Focus on what is best for the community
- Show empathy towards others

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to GHRepoLens! 🚀
