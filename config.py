"""
Configuration Module for GitHub Repository Analyzer

This module provides configuration settings and constants used
throughout the GitHub Repository Analyzer. It handles loading configuration from
files and defines constants for file categorization.

Key components:
- Configuration: TypedDict for strongly typed configuration
- Constants and mappings for file categorization
- Configuration loading and sample creation functions
"""

import configparser
import os
from pathlib import Path
from typing import List, TypedDict, Dict, Set, Literal

from console import console, logger


class Configuration(TypedDict):
    """
    TypedDict defining the structure and types of configuration parameters.
    
    Provides strong typing for configuration settings throughout the application.
    """
    GITHUB_TOKEN: str
    USERNAME: str
    REPORTS_DIR: str
    CLONE_DIR: str
    MAX_WORKERS: int
    INACTIVE_THRESHOLD_DAYS: int
    LARGE_REPO_LOC_THRESHOLD: int
    SKIP_FORKS: bool
    SKIP_ARCHIVED: bool
    INCLUDE_PRIVATE: bool  # Legacy option, maintained for backwards compatibility
    VISIBILITY: Literal["all", "public", "private"]  # New option that supersedes INCLUDE_PRIVATE
    ANALYZE_CLONES: bool
    ENABLE_CHECKPOINTING: bool
    CHECKPOINT_FILE: str
    CHECKPOINT_THRESHOLD: int
    RESUME_FROM_CHECKPOINT: bool
    INCLUDE_ORGS: List[str]  # List of organization names to include in analysis


# Configuration - these will be replaced by command line args or config file
DEFAULT_CONFIG: Configuration = {
    "GITHUB_TOKEN": "your_github_token_here",
    "USERNAME": "your_username_here",
    "REPORTS_DIR": "reports",
    "CLONE_DIR": "temp_repos",
    "MAX_WORKERS": 4,
    "INACTIVE_THRESHOLD_DAYS": 180,  # 6 months
    "LARGE_REPO_LOC_THRESHOLD": 1000,
    "SKIP_FORKS": False,
    "SKIP_ARCHIVED": False,
    "INCLUDE_PRIVATE": True,  # Legacy option, maintained for backwards compatibility
    "VISIBILITY": "all",  # New option: "all", "public", or "private"
    "ANALYZE_CLONES": False,  # Whether to clone repos for deeper analysis
    "ENABLE_CHECKPOINTING": True,  # Whether to enable checkpoint feature
    "CHECKPOINT_FILE": "github_analyzer_checkpoint.pkl",  # Checkpoint file location
    "CHECKPOINT_THRESHOLD": 100,  # Create checkpoint when remaining API requests falls below this
    "RESUME_FROM_CHECKPOINT": True,  # Whether to resume from checkpoint if it exists
    "INCLUDE_ORGS": [],  # Empty list means don't include any organization repositories
}

# File type mappings for better categorization
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    # Python and related
    '.py': 'Python', '.pyx': 'Cython', '.pyd': 'Python', '.pyi': 'Python', '.ipynb': 'Jupyter',

    # JavaScript/TypeScript ecosystem
    '.js': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript', '.jsx': 'JavaScript',
    '.vue': 'Vue', '.svelte': 'Svelte', '.astro': 'Astro',

    # Web technologies
    '.html': 'HTML', '.htm': 'HTML', '.xhtml': 'HTML',
    '.css': 'CSS', '.scss': 'SCSS', '.sass': 'Sass', '.less': 'Less',
    '.json': 'JSON', '.jsonc': 'JSON', '.json5': 'JSON',
    '.xsl': 'XML', '.xslt': 'XML', '.svg': 'SVG',

    # JVM languages
    '.java': 'Java', '.kts': 'Kotlin', '.groovy': 'Groovy',
    '.scala': 'Scala', '.sc': 'Scala', '.clj': 'Clojure', '.cljs': 'ClojureScript',

    # C-family languages
    '.c': 'C', '.h': 'C', '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++',
    '.hpp': 'C++', '.hxx': 'C++', '.hh': 'C++',
    '.cs': 'C#', '.vb': 'Visual Basic', '.fs': 'F#', '.fsx': 'F#',

    # Mobile development
    '.swift': 'Swift', '.m': 'Objective-C', '.mm': 'Objective-C++',
    '.dart': 'Dart', '.kt': 'Kotlin',

    # Other programming languages
    '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.erb': 'Ruby',
    '.php': 'PHP', '.phtml': 'PHP', '.phps': 'PHP',
    '.lua': 'Lua', '.ex': 'Elixir', '.exs': 'Elixir',
    '.erl': 'Erlang', '.hrl': 'Erlang',
    '.hs': 'Haskell', '.lhs': 'Haskell',
    '.pl': 'Perl', '.pm': 'Perl', '.t': 'Perl',
    '.jl': 'Julia', '.r': 'R', '.rmd': 'R Markdown',
    '.coffee': 'CoffeeScript', '.litcoffee': 'CoffeeScript',
    '.elm': 'Elm', '.purs': 'PureScript',
    '.ml': 'OCaml', '.mli': 'OCaml',
    '.nim': 'Nim', '.crystal': 'Crystal',

    # Shell and scripting
    '.sh': 'Shell', '.bash': 'Bash', '.zsh': 'Zsh', '.fish': 'Fish',
    '.ps1': 'PowerShell', '.psm1': 'PowerShell', '.psd1': 'PowerShell',
    '.bat': 'Batch', '.cmd': 'Batch',
    '.awk': 'AWK', '.sed': 'Sed',

    # Configuration and data formats
    '.yml': 'YAML', '.yaml': 'YAML', '.toml': 'TOML', '.ini': 'INI',
    '.xml': 'XML', '.sql': 'SQL', '.graphql': 'GraphQL', '.gql': 'GraphQL',
    '.proto': 'Protocol Buffers', '.thrift': 'Thrift',

    # Infrastructure and DevOps
    '.dockerfile': 'Docker', '.containerfile': 'Docker',
    '.tf': 'Terraform', '.tfvars': 'Terraform',
    '.hcl': 'HCL', '.nomad': 'Nomad',
    '.bicep': 'Bicep', '.cdk': 'CDK',

    # Documentation
    '.md': 'Markdown', '.mdx': 'MDX', '.rst': 'reStructuredText',
    '.tex': 'LaTeX', '.adoc': 'AsciiDoc', '.wiki': 'Wiki',

    # Other
    '.csv': 'CSV', '.tsv': 'TSV',
    '.zig': 'Zig', '.v': 'V', '.vlang': 'V',
    '.wasm': 'WebAssembly', '.wat': 'WebAssembly Text'
}

BINARY_EXTENSIONS: Set[str] = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp', '.tiff', '.tif',
    '.psd', '.ai', '.eps', '.indd', '.raw', '.cr2', '.nef', '.heif', '.heic',

    # Documents and PDFs
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.odt', '.ods', '.odp', '.pages', '.numbers', '.key',

    # Archives and compressed files
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.iso',
    '.tgz', '.tbz2', '.txz', '.lz', '.lzma', '.lzo', '.zst',

    # Executables and libraries
    '.exe', '.dll', '.so', '.dylib', '.a', '.lib', '.o', '.obj',
    '.bin', '.com', '.msi', '.app', '.dmg', '.deb', '.rpm',

    # Compiled code
    '.pyc', '.pyd', '.pyo', '.class', '.jar', '.war', '.ear',
    '.whl', '.egg', '.dex', '.apk', '.aab', '.ipa',

    # Data and databases
    '.dat', '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',
    '.frm', '.myd', '.myi', '.ibd', '.dbf', '.bak',

    # Media files
    '.mp3', '.mp4', '.wav', '.flac', '.ogg', '.m4a', '.aac',
    '.avi', '.mov', '.wmv', '.mkv', '.webm', '.flv', '.m4v',

    # Fonts
    '.ttf', '.otf', '.woff', '.woff2', '.eot',

    # Other binary formats
    '.blend', '.fbx', '.3ds', '.obj', '.stl', '.glb', '.gltf',
    '.swf', '.fla', '.xcf', '.sketch', '.fig'
}

# Special filenames without extensions that should be properly categorized
SPECIAL_FILENAMES: Dict[str, str] = {
    # Documentation files
    'README': 'Markdown',
    'LICENSE': 'Text',
    'COPYING': 'Text',
    'CONTRIBUTORS': 'Text',
    'AUTHORS': 'Text',
    'CHANGELOG': 'Markdown',
    'CHANGES': 'Text',
    'HISTORY': 'Text',
    'NEWS': 'Text',
    'NOTICE': 'Text',
    'PATENTS': 'Text',
    'VERSION': 'Text',
    'INSTALL': 'Text',

    # Configuration files
    'Dockerfile': 'Docker',
    'Makefile': 'Makefile',
    'Jenkinsfile': 'Jenkinsfile',
    'Vagrantfile': 'Ruby',
    '.gitignore': 'GitIgnore',
    '.gitattributes': 'GitConfig',
    '.gitmodules': 'GitConfig',
    '.babelrc': 'JSON',
    '.eslintrc': 'JSON',
    '.prettierrc': 'JSON',
    '.stylelintrc': 'JSON',
    '.eslintignore': 'GitIgnore',
    '.prettierignore': 'GitIgnore',
    '.npmrc': 'INI',
    '.yarnrc': 'YAML',
    '.editorconfig': 'INI',
    '.browserslistrc': 'Text',

    # Go files
    'go.mod': 'Go',
    'go.sum': 'Go',

    # Python files
    'Pipfile': 'TOML',
    'pyproject.toml': 'TOML',
    'requirements': 'Text',

    # JavaScript/Node files
    'package.json': 'JSON',
    'package-lock.json': 'JSON',
    'yarn.lock': 'YAML',
    'tsconfig.json': 'JSON',

    # Ruby files
    'Gemfile': 'Ruby',
    'Rakefile': 'Ruby',

    # Shell scripts
    'configure': 'Shell',

    # Other
    'CODEOWNERS': 'Text',
    '.mailmap': 'Text',
    '.htaccess': 'Apache',
    'Procfile': 'YAML'
}

CONFIG_FILES: Set[str] = {
    # Python
    'requirements.txt', 'requirements-dev.txt', 'requirements-test.txt',
    'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'setup.py', 'setup.cfg',
    'poetry.lock', 'conda-env.yml', 'environment.yml', 'tox.ini',

    # JavaScript/TypeScript
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'bun.lockb', 'npm-shrinkwrap.json', 'bower.json', 'lerna.json',
    'tsconfig.json', 'jsconfig.json', '.babelrc', '.eslintrc', '.prettierrc',
    'webpack.config.js', 'rollup.config.js', 'vite.config.js', 'next.config.js',
    'svelte.config.js', 'nuxt.config.js', 'astro.config.mjs',

    # Ruby
    'Gemfile', 'Gemfile.lock', '.ruby-version', '.ruby-gemset',

    # Go
    'go.mod', 'go.sum', 'glide.yaml', 'glide.lock', 'Gopkg.toml', 'Gopkg.lock',

    # Rust
    'Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml',

    # Java/JVM
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle',
    'settings.gradle.kts', 'gradle.properties', 'build.sbt', 'ivy.xml',
    'maven-wrapper.properties', 'gradle-wrapper.properties',

    # PHP
    'composer.json', 'composer.lock', '.htaccess',

    # .NET
    'packages.config', '*.csproj', '*.vbproj', '*.fsproj', 'nuget.config',
    'project.json', 'global.json', 'paket.dependencies', 'paket.lock',

    # Docker and containers
    'dockerfile', 'docker-compose.yml', 'docker-compose.yaml', '.dockerignore',
    'containerfile', 'docker-compose.override.yml',

    # Infrastructure as Code
    'terraform.tfstate', 'terraform.tfvars', 'terragrunt.hcl',
    'cloudformation.yaml', 'cloudformation.json', 'serverless.yml',
    'kubernetes.yaml', 'kustomization.yaml', 'helm.yaml',

    # Build systems
    'CMakeLists.txt', 'Makefile', 'makefile', 'Rakefile', 'Gruntfile.js',
    'Gulpfile.js', 'build.xml', 'ant.xml', 'meson.build', 'ninja.build',
    'WORKSPACE', 'BUILD', 'bazel.rc',

    # Version control
    '.gitignore', '.gitattributes', '.gitmodules', '.gitkeep',
    '.hgignore', '.svnignore', '.bzrignore', '.cvsignore',

    # Editor configs
    '.editorconfig', '.vscode/settings.json', '.idea/workspace.xml',
    '.sublime-project', '.sublime-workspace',

    # Linting and formatting
    '.eslintrc.js', '.eslintrc.json', '.eslintrc.yml',
    '.prettierrc.js', '.prettierrc.json', '.prettierrc.yml',
    '.stylelintrc', '.pylintrc', '.flake8', 'mypy.ini',
    'rustfmt.toml', 'clippy.toml', '.golangci.yml',

    # Environment and secrets
    '.env', '.env.example', '.env.local', '.env.development', '.env.production',
    '.env.test', '.envrc', '.direnv'
}

# CI/CD configuration files to detect project quality
CICD_FILES: Set[str] = {
    # GitHub
    '.github/workflows', '.github/actions', '.github/CODEOWNERS',
    '.github/dependabot.yml', '.github/dependabot.yaml',

    # GitLab
    '.gitlab-ci.yml', '.gitlab/agents', '.gitlab/issue_templates',
    '.gitlab/merge_request_templates',

    # Other CI systems
    '.travis.yml', '.circleci/config.yml', 'circle.yml',
    'Jenkinsfile', 'jenkins.yml', 'jenkins.yaml',
    'azure-pipelines.yml', 'azure-pipelines.yaml',
    'appveyor.yml', 'appveyor.yaml',
    '.drone.yml', '.drone.yaml',
    'bitbucket-pipelines.yml', 'bitbucket-pipelines.yaml',
    '.teamcity', 'buildkite.yml', 'buildkite.yaml',

    # Testing and quality
    '.codecov.yml', '.coveralls.yml', 'sonar-project.properties',
    'codecov.yml', 'jest.config.js', 'karma.conf.js',
    'cypress.json', 'cypress.config.js', 'playwright.config.js',
    'phpunit.xml', 'pytest.ini', '.nycrc', 'vitest.config.js',

    # Deployment
    '.netlify.toml', 'vercel.json', 'now.json',
    'firebase.json', 'fly.toml', 'railway.json',
    'heroku.yml', 'Procfile', 'app.yaml', 'app.json',
    'k8s', 'kubernetes', 'helm', 'charts',

    # Release management
    '.releaserc', '.releaserc.json', '.releaserc.js',
    'release.config.js', '.goreleaser.yml', '.goreleaser.yaml',
    'CHANGELOG.md', 'RELEASES.md', 'VERSION'
}

# Directories to exclude from analysis (build artifacts, generated code, etc.)
EXCLUDED_DIRECTORIES: Set[str] = {
    # Build artifacts and compiled outputs
    'bin', 'obj', 'build', 'dist', 'target', 'out',
    'Debug', 'Release', 'x64', 'x86', 'Win32', 'ARM',
    'x64/Debug', 'x64/Release', 'x86/Debug', 'x86/Release',
    'cmake-build-debug', 'cmake-build-release',

    # Package management
    'node_modules', 'bower_components', 'jspm_packages', 'package',
    'vendor', '.nuget', '.pub-cache', 'site-packages',
    '.venv', 'venv', 'env', 'ENV', 'virtualenv',
    '.gradle', '.m2', '.ivy2', '.cargo', 'node_modules',

    # IDE and editor specific
    '.vs', '.vscode', '.idea', '.fleet',
    '.project', '.settings', '.classpath', '.metadata',
    '__pycache__', '.ipynb_checkpoints',

    # Documentation and generated content
    'docs/_build', '_site', 'public', 'coverage', 'htmlcov', '.nyc_output',
    'swagger-ui', 'apidoc',

    # Version control
    '.git', '.hg', '.svn', '.bzr', 'CVS',

    # OS specific
    '.DS_Store', 'Thumbs.db', '__MACOSX',

    # Temporary files
    'tmp', 'temp', 'cache', '.cache',

    # Unity specific
    'Library', 'Temp', 'Obj', 'Logs', 'UserSettings',

    # Custom
    'Dependencies', 'dependencies', 'deps',
}

# Package management files to detect
PACKAGE_FILES: Set[str] = {
    # Python
    'setup.py', 'pyproject.toml', 'setup.cfg', 'requirements.txt',
    'Pipfile', 'Pipfile.lock', 'poetry.lock', 'conda-env.yml',
    'environment.yml',

    # JavaScript/Node.js
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'bun.lockb', 'npm-shrinkwrap.json', 'lerna.json',

    # Ruby
    'Gemfile', 'Gemfile.lock',

    # PHP
    'composer.json', 'composer.lock',

    # .NET
    'packages.config', '.csproj', '.vbproj', '.fsproj', '.nupkg',

    # Java
    'pom.xml', 'build.gradle', 'gradle.properties', 'build.sbt',
    'maven-wrapper.properties',

    # Go
    'go.mod', 'go.sum',

    # Rust
    'Cargo.toml', 'Cargo.lock'
}

# Deployment configuration files to detect
DEPLOYMENT_FILES: Set[str] = {
    # Docker and containers
    'dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
    'containerfile', 'docker-compose.override.yml',

    # Kubernetes
    'kubernetes.yaml', 'kubernetes.yml', 'kustomization.yaml',
    'helm.yaml', 'chart.yaml', 'values.yaml',

    # Cloud providers
    'appveyor.yml', 'azure-pipelines.yml', '.travis.yml',
    '.circleci/config.yml', 'cloudbuild.yaml', 'buildspec.yml',
    'serverless.yml', 'cloudformation.yaml', 'cloudformation.json',

    # Platform specific
    'Procfile', 'app.yaml', 'app.json', '.platform.app.yaml',
    'fly.toml', 'railway.json', 'heroku.yml',
    'vercel.json', 'netlify.toml', 'now.json',

    # Infrastructure as code
    'terraform.tfstate', 'terraform.tfvars', 'terragrunt.hcl',
    'main.tf', 'variables.tf', 'outputs.tf',

    # Deployment scripts
    'deploy.sh', 'deploy.py', 'deploy.js', 'deploy.ps1',
    'deploy-production.sh', 'deploy-staging.sh'
}

# Release files and directories to detect
RELEASE_FILES: Set[str] = {
    # Release management
    '.github/releases', 'releases/',
    '.releaserc', '.releaserc.json', '.releaserc.js', '.releaserc.yaml',
    'release.config.js', '.goreleaser.yml', '.goreleaser.yaml',
    'CHANGELOG.md', 'CHANGELOG', 'CHANGES.md', 'CHANGES',
    'RELEASES.md', 'RELEASES', 'VERSION', 'version.txt',
    'semver.txt', 'semantic-release.config.js'
}


def load_config_from_file(config_file: str) -> Configuration:
    """
    Load configuration from a file.
    
    Reads configuration settings from an INI file and updates the default
    configuration with values from the file.
    
    Args:
        config_file: Path to the configuration file to load
        
    Returns:
        Updated configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    if not os.path.exists(config_file):
        logger.warning(f"Config file {config_file} not found, using defaults")
        return config

    try:
        parser = configparser.ConfigParser()
        parser.read(config_file)

        if 'github' in parser:
            github_section = parser['github']
            if 'token' in github_section:
                config['GITHUB_TOKEN'] = github_section['token']
            if 'username' in github_section:
                config['USERNAME'] = github_section['username']

        if 'analysis' in parser:
            analysis_section = parser['analysis']
            if 'reports_dir' in analysis_section:
                config['REPORTS_DIR'] = analysis_section['reports_dir']
            if 'clone_dir' in analysis_section:
                config['CLONE_DIR'] = analysis_section['clone_dir']
            if 'max_workers' in analysis_section:
                config['MAX_WORKERS'] = int(analysis_section['max_workers'])
            if 'inactive_threshold_days' in analysis_section:
                config['INACTIVE_THRESHOLD_DAYS'] = int(analysis_section['inactive_threshold_days'])
            if 'large_repo_loc_threshold' in analysis_section:
                config['LARGE_REPO_LOC_THRESHOLD'] = int(analysis_section['large_repo_loc_threshold'])

        if 'filters' in parser:
            filters_section = parser['filters']
            if 'skip_forks' in filters_section:
                config['SKIP_FORKS'] = filters_section.getboolean('skip_forks')
            if 'skip_archived' in filters_section:
                config['SKIP_ARCHIVED'] = filters_section.getboolean('skip_archived')
            if 'include_private' in filters_section:
                config['INCLUDE_PRIVATE'] = filters_section.getboolean('include_private')
            if 'visibility' in filters_section:
                visibility_value = filters_section['visibility'].lower()
                if visibility_value in ["all", "public", "private"]:
                    config['VISIBILITY'] = visibility_value
            if 'analyze_clones' in filters_section:
                config['ANALYZE_CLONES'] = filters_section.getboolean('analyze_clones')
            if 'include_orgs' in filters_section:
                # Parse comma-separated list of organization names
                orgs_str = filters_section['include_orgs']
                if orgs_str.strip():
                    config['INCLUDE_ORGS'] = [org.strip() for org in orgs_str.split(',')]

        if 'checkpointing' in parser:
            checkpoint_section = parser['checkpointing']
            if 'enable_checkpointing' in checkpoint_section:
                config['ENABLE_CHECKPOINTING'] = checkpoint_section.getboolean('enable_checkpointing')
            if 'checkpoint_file' in checkpoint_section:
                config['CHECKPOINT_FILE'] = checkpoint_section['checkpoint_file']
            if 'checkpoint_threshold' in checkpoint_section:
                config['CHECKPOINT_THRESHOLD'] = int(checkpoint_section['checkpoint_threshold'])
            if 'resume_from_checkpoint' in checkpoint_section:
                config['RESUME_FROM_CHECKPOINT'] = checkpoint_section.getboolean('resume_from_checkpoint')

        logger.info(f"Loaded configuration from {config_file}")
        return config

    except Exception as e:
        logger.error(f"Error loading config file {config_file}: {e}")
        return config


def create_sample_config() -> None:
    """
    Create a sample configuration file if it doesn't exist.
    
    Generates a sample INI configuration file with default settings
    as a template for users to customize.
    """
    config_file = 'config.ini.sample'

    if os.path.exists(config_file):
        return

    config = configparser.ConfigParser()
    config['github'] = {
        'token': 'your_github_token_here',
        'username': 'your_username_here'
    }

    config['analysis'] = {
        'reports_dir': 'reports',
        'clone_dir': 'temp_repos',
        'max_workers': '4',
        'inactive_threshold_days': '180',
        'large_repo_loc_threshold': '1000'
    }

    config['filters'] = {
        'skip_forks': 'false',
        'skip_archived': 'false',
        'include_private': 'true',
        'visibility': 'all',  # "all", "public", or "private"
        'analyze_clones': 'false',
        'include_orgs': ''  # Empty string for no organizations
    }

    config['checkpointing'] = {
        'enable_checkpointing': 'true',
        'checkpoint_file': 'github_analyzer_checkpoint.pkl',
        'checkpoint_threshold': '100',
        'resume_from_checkpoint': 'true'
    }

    with open(config_file, 'w') as f:
        config.write(f)

    console.print(f"[green]Created sample configuration file: {config_file}[/green]")
    console.print("[yellow]Rename to config.ini and update with your settings.[/yellow]")


class ThemeConfig(TypedDict, total=False):
    """Theme configuration for the visualization dashboard"""
    # Color schemes
    primary_color: str  # Main brand color
    secondary_color: str  # Secondary brand color
    accent_color: str  # Accent color for highlights

    # Light mode colors
    light_bg_color: str  # Light mode background
    light_text_color: str  # Light mode text color
    light_card_bg: str  # Light mode card background
    light_chart_bg: str  # Light mode chart background

    # Dark mode colors
    dark_bg_color: str  # Dark mode background
    dark_text_color: str  # Dark mode text color
    dark_card_bg: str  # Dark mode card background
    dark_chart_bg: str  # Dark mode chart background

    # Typography
    font_family: str  # Main font family
    heading_font: str  # Font for headings
    code_font: str  # Font for code sections

    # UI Elements
    border_radius: str  # Border radius for cards/buttons
    shadow_style: str  # Shadow style for elements

    # Chart colors
    chart_palette: List[str]  # Colors for charts

    # Header gradient
    header_gradient: str  # CSS gradient for header


class DefaultTheme:
    """Default theme configuration for visualization"""

    @staticmethod
    def get_default_theme() -> ThemeConfig:
        """Return the default theme configuration"""
        return {
            # Color schemes
            "primary_color": "#4f46e5",  # Indigo
            "secondary_color": "#7c3aed",  # Violet
            "accent_color": "#f97316",  # Orange

            # Light mode colors
            "light_bg_color": "#f9fafb",
            "light_text_color": "#111827",
            "light_card_bg": "#ffffff",
            "light_chart_bg": "#ffffff",

            # Dark mode colors
            "dark_bg_color": "#111827",
            "dark_text_color": "#f9fafb",
            "dark_card_bg": "#1f2937",
            "dark_chart_bg": "#1f2937",

            # Typography
            "font_family": "'Inter', sans-serif",
            "heading_font": "'Inter', sans-serif",
            "code_font": "'Fira Code', monospace",

            # UI Elements
            "border_radius": "0.375rem",
            "shadow_style": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",

            # Chart colors
            "chart_palette": [
                "#4f46e5", "#7c3aed", "#f97316", "#06b6d4",
                "#10b981", "#ec4899", "#f59e0b", "#6366f1",
                "#ef4444", "#64748b"
            ],

            # Header gradient
            "header_gradient": "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #f97316 100%)"
        }


def load_theme_config() -> ThemeConfig:
    """
    Load theme configuration from config file or return default theme.
    
    Returns:
        ThemeConfig: A dictionary containing theme configuration settings
    """
    # TODO: In the future, add functionality to load custom theme from file
    return DefaultTheme.get_default_theme()


def get_config() -> configparser.ConfigParser:
    """
    Get configuration from .env file or environment variables.
    
    Returns:
        configparser.ConfigParser: A ConfigParser object with configuration settings
    """
    config = configparser.ConfigParser()

    # Default configuration
    config['github'] = {
        'username': 'your_github_username',
        'token': 'your_github_token',
    }

    # Check for .env file
    env_file = Path('.env')
    if env_file.exists():
        # Parse .env file
        env_config = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_config[key.strip()] = value.strip().strip('"\'')

        # Update config with values from .env
        if 'GITHUB_USERNAME' in env_config:
            config['github']['username'] = env_config['GITHUB_USERNAME']
        if 'GITHUB_TOKEN' in env_config:
            config['github']['token'] = env_config['GITHUB_TOKEN']

    # Environment variables override .env file
    if 'GITHUB_USERNAME' in os.environ:
        config['github']['username'] = os.environ['GITHUB_USERNAME']
    if 'GITHUB_TOKEN' in os.environ:
        config['github']['token'] = os.environ['GITHUB_TOKEN']

    return config


def shutdown_logging() -> None:
    """
    This function is kept for backwards compatibility.
    The actual logging shutdown is now handled in console.py
    """
    # Nothing to do, just import to ensure proper references
    pass
