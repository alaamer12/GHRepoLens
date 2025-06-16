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
from typing import List, TypedDict, Dict, Set, Literal, Any

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
    '.tex': 'LaTeX', '.ltx': 'LaTeX', '.latex': 'LaTeX', '.adoc': 'AsciiDoc', '.wiki': 'Wiki',

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
    'Procfile': 'YAML',

 
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

# Game engine binary files and formats to help identify game repositories
GAME_ENGINE_FILES: Set[str] = {
    # Unity
    '.unity', '.unitypackage', '.asset', '.prefab', '.mat', '.meta',
    '.cubemap', '.flare', '.fontsettings', '.guiskin', 
    '.physicMaterial', '.physicsMaterial2D', '.renderTexture',
    '.mixer', '.shadervariants', '.spriteatlas', '.terrainlayer',
     
    # Godot
    '.pck', '.gdc', '.res', '.scn', '.godot',
    
    # Unreal Engine
    '.pak', '.ubulk', '.uexp', '.umeta',
    
    # Other game engines and formats
    '.bsp', '.vtf', '.vmt', '.vpk', '.pgm', '.dem',
    '.sav', '.lmp', '.bik', '.smk', '.usm',
    '.fnt', '.ttarch', '.pbb', '.lvl'
}

# Common game engine directories
GAME_ENGINE_DIRECTORIES: Set[str] = {
    # Unity
    'Assets', 'ProjectSettings', 'Packages', 'Library/PackageCache',
    
    # Unreal Engine
    'Content', 'Config', 'Binaries', 'Intermediate', 'Saved',
    
    # Godot
    '.godot', 'addons', 'bin', 'scenes'
}

def is_game_repo(file_types: Dict[str, int], project_structure: Dict[str, int]) -> Dict[str, Any]:
    """
    Determine if a repository is likely a game project and which engine it uses.
    
    Args:
        file_types: Dictionary of file extensions with counts
        project_structure: Dictionary of top-level directories with counts
        
    Returns:
        Dictionary with game repository information: {
            'is_game_repo': bool,
            'engine_type': str,  # 'Unity', 'Unreal Engine', 'Godot', or 'Other/Unknown'
            'confidence': float  # 0.0-1.0
        }
    """
    result = {
        'is_game_repo': False,
        'engine_type': 'Other/Unknown',
        'confidence': 0.0
    }
    
    # Check for game engine file extensions
    game_file_count = 0
    total_files = sum(file_types.values())
    
    if total_files == 0:
        return result
    
    # Count game files by extension
    for ext, count in file_types.items():
        if ext.lower() in GAME_ENGINE_FILES:
            game_file_count += count
    
    # Check directory structure
    unity_dirs = 0
    unreal_dirs = 0
    godot_dirs = 0
    
    for directory in project_structure:
        dir_lower = directory.lower()
        # Unity-specific directories
        if directory in ['Assets', 'ProjectSettings', 'Packages']:
            unity_dirs += 1
        # Unreal Engine-specific directories
        elif directory in ['Content', 'Config', 'Binaries', 'Intermediate', 'Saved']:
            unreal_dirs += 1
        # Godot-specific directories
        elif directory in ['.godot', 'addons'] or dir_lower.endswith('.godot'):
            godot_dirs += 1
    
    # Calculate confidence based on file types and directory structure
    game_file_ratio = game_file_count / total_files if total_files > 0 else 0
    
    # Determine engine type based on strongest signals
    if unity_dirs >= 2:
        result['engine_type'] = 'Unity'
        result['confidence'] = 0.7 + (unity_dirs * 0.1) + (game_file_ratio * 0.2)
    elif unreal_dirs >= 2:
        result['engine_type'] = 'Unreal Engine'
        result['confidence'] = 0.7 + (unreal_dirs * 0.1) + (game_file_ratio * 0.2)
    elif godot_dirs >= 1:
        result['engine_type'] = 'Godot'
        result['confidence'] = 0.7 + (godot_dirs * 0.15) + (game_file_ratio * 0.2)
    else:
        # Check for engines based primarily on file types
        unity_files = sum(count for ext, count in file_types.items() if ext.lower() in ['.unity', '.prefab', '.asset', '.meta'])
        unreal_files = sum(count for ext, count in file_types.items() if ext.lower() in ['.uasset', '.umap', '.upk', '.uproject'])
        godot_files = sum(count for ext, count in file_types.items() if ext.lower() in ['.godot', '.tscn', '.gd', '.tres'])
        
        if unity_files > unreal_files and unity_files > godot_files and unity_files > 5:
            result['engine_type'] = 'Unity'
            result['confidence'] = 0.5 + (unity_files / total_files * 0.5)
        elif unreal_files > unity_files and unreal_files > godot_files and unreal_files > 5:
            result['engine_type'] = 'Unreal Engine'
            result['confidence'] = 0.5 + (unreal_files / total_files * 0.5)
        elif godot_files > unity_files and godot_files > unreal_files and godot_files > 3:
            result['engine_type'] = 'Godot'
            result['confidence'] = 0.5 + (godot_files / total_files * 0.5)
    
    # Make final determination
    result['is_game_repo'] = result['confidence'] > 0.5
    result['confidence'] = min(1.0, result['confidence'])  # Cap at 1.0
    
    return result


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

        # Process the theme section as well
        if 'theme' in parser:
            theme_section = parser['theme']
            # Store theme configuration for later use by DefaultTheme and HTMLVisualizer
            # We'll store it as a global so it can be accessed by the theme loading function
            global LOADED_THEME_CONFIG
            LOADED_THEME_CONFIG = {}

            # Process all keys in the theme section
            for key, value in theme_section.items():
                LOADED_THEME_CONFIG[key] = value

            # Special handling for JSON fields
            try:
                import json
                if 'skills' in theme_section:
                    LOADED_THEME_CONFIG['skills'] = json.loads(theme_section['skills'])
                if 'social_links' in theme_section:
                    LOADED_THEME_CONFIG['social_links'] = json.loads(theme_section['social_links'])
                if 'chart_palette' in theme_section:
                    LOADED_THEME_CONFIG['chart_palette'] = json.loads(theme_section['chart_palette'])
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON in theme section: {e}")

            logger.info(f"Loaded theme configuration from {config_file}")

        logger.info(f"Loaded configuration from {config_file}")
        return config

    except Exception as e:
        logger.error(f"Error loading config file {config_file}: {e}")
        return config


# Global variable to store theme configuration loaded from config file
LOADED_THEME_CONFIG = None


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

    # Add theme configuration section
    config['theme'] = {
        # Color Schemes
        'primary_color': '#4f46e5',
        'secondary_color': '#8b5cf6',
        'accent_color': '#f97316',

        # Light Mode Colors
        'light_bg_color': '#f9fafb',
        'light_text_color': '#111827',
        'light_card_bg': '#ffffff',
        'light_chart_bg': '#ffffff',

        # Dark Mode Colors
        'dark_bg_color': '#111827',
        'dark_text_color': '#f9fafb',
        'dark_card_bg': '#1f2937',
        'dark_chart_bg': '#1f2937',

        # Typography
        'font_family': 'Inter, system-ui, sans-serif',
        'heading_font': 'Inter, system-ui, sans-serif',
        'code_font': 'Fira Code, monospace',

        # UI Elements
        'border_radius': '0.5rem',
        'shadow_style': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',

        # Header - escape % with %% for ConfigParser
        'header_gradient': 'linear-gradient(135deg, #4f46e5 0%%, #8b5cf6 50%%, #f97316 100%%)',

        # Chart palette as JSON array
        'chart_palette': '["#6366f1", "#a855f7", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"]',

        # User Information
        'user_avatar': 'static/assets/alaamer.jpg',
        'user_name': 'Your Name',
        'user_title': 'Your Title',
        'user_bio': 'Your short bio here',

        # Custom HTML Background
        'background_html_path': '',

        # The following are JSON-formatted fields that will need to be parsed
        # Skills: Dictionary of skill name -> URL
        'skills': '{"Python": "https://www.python.org", "Data Science": "https://en.wikipedia.org/wiki/Data_science"}',

        # Social links: Dictionary with name -> {url, icon, color}
        'social_links': '{"GitHub": {"url": "https://github.com/yourusername", "icon": "github", "color": "bg-gray-800"}, "LinkedIn": {"url": "https://www.linkedin.com/in/yourusername/", "icon": "linkedin", "color": "bg-blue-600"}}'
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

    # User information
    user_avatar: str  # Path to user avatar image
    user_name: str  # User's name to display
    user_title: str  # User's title/role
    user_bio: str  # User's bio

    # Skills and social media as dictionaries
    skills: Dict[str, str]  # Dict of skills with name and URL
    social_links: Dict[str, str]  # Dict of social media links with name and URL

    # Custom HTML background
    background_html_path: str  # Path to HTML file for custom background, will be parsed at _html.py


class DefaultTheme:
    """Default theme configuration for visualization"""

    @staticmethod
    def get_default_theme() -> ThemeConfig:
        """Return the default theme configuration"""
        return {
            # Color schemes
            "primary_color": "#6366f1",  # Indigo color
            "secondary_color": "#a855f7",  # Purple color
            "accent_color": "#ec4899",  # Pink color

            # Light mode colors
            "light_bg_color": "#f9fafb",
            "light_text_color": "#1f2937",
            "light_card_bg": "#ffffff",
            "light_chart_bg": "#ffffff",

            # Dark mode colors
            "dark_bg_color": "#111827",
            "dark_text_color": "#f9fafb",
            "dark_card_bg": "#1f2937",
            "dark_chart_bg": "#1f2937",

            # Typography
            "font_family": "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            "heading_font": "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            "code_font": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",

            # UI Elements
            "border_radius": "0.75rem",
            "shadow_style": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",

            # Chart colors - a pleasant color palette
            "chart_palette": ["#6366f1", "#a855f7", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444"],

            # Header gradient - note this is used differently than in the sample config
            # This is used directly in Python code, not in ConfigParser
            "header_gradient": "linear-gradient(to right, #6366f1, #a855f7, #ec4899)",

            # Default user information
            "user_avatar": "static/assets/alaamer.jpg",  # Default avatar
            "user_name": "Amr Muhamed",  # Default name
            "user_title": "Full Stack Dev",  # Default title
            "user_bio": "Creator of GHRepoLens 😄",

            # Default skills and social links
            "skills": {
                "Python": "https://www.python.org",
                "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
                "React": "https://reactjs.org",
                "Data Analysis": "https://en.wikipedia.org/wiki/Data_analysis",
                "ML": "https://en.wikipedia.org/wiki/Machine_learning",
                "GitHub API": "https://docs.github.com/en/rest"
            },

            "social_links": {
                "GitHub": {
                    "url": "https://github.com/alaamer12",
                    "icon": "github",
                    "color": "bg-gray-800"
                },
                "LinkedIn": {
                    "url": "https://www.linkedin.com/in/amr-muhamed-0b0709265/",
                    "icon": "linkedin",
                    "color": "bg-blue-600"
                },
                "Portfolio": {
                    "url": "https://portfolio-qiw8.vercel.app/",
                    "icon": "globe",
                    "color": "bg-emerald-600"
                }
            },

            # Default empty HTML background
            "background_html_path": "",
        }


def load_theme_config() -> ThemeConfig:
    """
    Load theme configuration from config file or return default theme.
    
    Returns:
        ThemeConfig: A dictionary containing theme configuration settings
    """
    # Check if we already loaded the theme config in load_config_from_file
    global LOADED_THEME_CONFIG
    if LOADED_THEME_CONFIG is not None:
        logger.info("Using previously loaded theme configuration")
        theme = DefaultTheme.get_default_theme()

        # Update theme with loaded values
        for key, value in LOADED_THEME_CONFIG.items():
            if key in theme and isinstance(value, str) and not key in ['skills', 'social_links', 'chart_palette']:
                theme[key] = value

        # Handle special fields that should already be parsed
        for key in ['skills', 'social_links', 'chart_palette']:
            if key in LOADED_THEME_CONFIG:
                theme[key] = LOADED_THEME_CONFIG[key]

        return theme

    # Fall back to old method if LOADED_THEME_CONFIG is not populated
    config_file = 'config.ini'
    theme = DefaultTheme.get_default_theme()

    if not os.path.exists(config_file):
        logger.warning(f"Config file {config_file} not found, using default theme")
        return theme

    try:
        parser = configparser.ConfigParser()
        parser.read(config_file)

        if 'theme' not in parser:
            logger.info(f"No theme section in {config_file}, using default theme")
            return theme

        theme_section = parser['theme']

        # Load basic string values
        for key in ['primary_color', 'secondary_color', 'accent_color',
                    'light_bg_color', 'light_text_color', 'light_card_bg', 'light_chart_bg',
                    'dark_bg_color', 'dark_text_color', 'dark_card_bg', 'dark_chart_bg',
                    'font_family', 'heading_font', 'code_font',
                    'border_radius', 'shadow_style', 'header_gradient',
                    'user_avatar', 'user_name', 'user_title', 'user_bio',
                    'background_html_path']:
            if key in theme_section:
                theme[key] = theme_section[key]

        # Handle JSON fields
        if 'skills' in theme_section:
            import json
            try:
                skills_json = theme_section['skills']
                theme['skills'] = json.loads(skills_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for skills in {config_file}, using default skills")

        if 'social_links' in theme_section:
            import json
            try:
                links_json = theme_section['social_links']
                theme['social_links'] = json.loads(links_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for social_links in {config_file}, using default social links")

        # Handle chart_palette list
        if 'chart_palette' in theme_section:
            import json
            try:
                palette_json = theme_section['chart_palette']
                theme['chart_palette'] = json.loads(palette_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for chart_palette in {config_file}, using default palette")

        logger.info(f"Loaded theme configuration from {config_file}")
        return theme

    except Exception as e:
        logger.error(f"Error loading theme from {config_file}: {e}")
        return theme


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
