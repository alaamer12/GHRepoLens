# Contributing to GHRepoLens

Thank you for considering contributing to GHRepoLens! This document provides guidelines and instructions for contributing to this project.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find that the bug has already been reported. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title** for the issue
- **Describe the exact steps which reproduce the problem**
- **Provide specific examples** to demonstrate the steps
- **Describe the behavior you observed**
- **Explain the behavior you expected to see**
- **Include screenshots or animated GIFs** if possible
- **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful**
- **Include mockups or examples** if applicable

### Pull Requests

- Fill in the required PR template
- Follow the Python style guide (PEP 8)
- Include appropriate tests
- Update documentation if needed
- End all files with a newline
- Make sure your code passes all tests and linting

## Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Set up your development environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```
4. Make your changes and write tests
5. Run tests and linting:
   ```bash
   pytest
   black .
   isort .
   flake8
   ```
6. Commit your changes following the [conventional commits](https://www.conventionalcommits.org/) standard
7. Push to your branch
8. Create a Pull Request

## Coding Standards

- Follow PEP 8 style guidelines
- Write docstrings for all functions, classes, and methods
- Include type hints for function parameters and return values
- Write unit tests for new functionality
- Keep functions focused and small (preferably < 20 lines)
- Use descriptive variable names

## Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests after the first line
- Follow the [conventional commits](https://www.conventionalcommits.org/) format:
  - `feat`: A new feature
  - `fix`: A bug fix
  - `docs`: Documentation only changes
  - `style`: Changes that do not affect the meaning of the code
  - `refactor`: A code change that neither fixes a bug nor adds a feature
  - `perf`: A code change that improves performance
  - `test`: Adding missing tests or correcting existing tests
  - `chore`: Changes to the build process or auxiliary tools

## Documentation

- Update README.md with details of changes to the interface
- Update the documentation when you change functionality
- Maintain the project structure documentation

## Questions?

Feel free to contact the project maintainers if you have any questions or need help with the contribution process.

Thank you for contributing to GHRepoLens! 