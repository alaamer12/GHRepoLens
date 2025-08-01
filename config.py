"""
Configuration Module for GitHub Repository RunnerAnalyzer

This module provides configuration settings and constants used
throughout the GitHub Repository RunnerAnalyzer. It handles loading configuration from
files and defines constants for file categorization.

Key components:
- Configuration: TypedDict for strongly typed configuration
- Constants and mappings for file categorization
- Configuration loading and sample creation functions
"""

import configparser
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, TypedDict, Dict, Set, Literal, Any, Optional
import json
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
    IFRAME_EMBEDDING: Literal["disabled", "partial", "full"]  # Option for iframe embedding
    VERCEL_TOKEN: str  # Vercel API token for deployment
    VERCEL_PROJECT_NAME: str  # Unique project name for Vercel


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
    "IFRAME_EMBEDDING": "disabled",  # Default: No iframe embedding
    "VERCEL_TOKEN": "",  # Empty by default, must be provided for deployment
    "VERCEL_PROJECT_NAME": "",  # Empty by default, must be provided for deployment
}


_STRING_KEYS = [
    'primary_color', 'secondary_color', 'accent_color',
    'light_bg_color', 'light_text_color', 'light_card_bg', 'light_chart_bg',
    'dark_bg_color', 'dark_text_color', 'dark_card_bg', 'dark_chart_bg',
    'font_family', 'heading_font', 'code_font',
    'border_radius', 'shadow_style', 'header_gradient',
    'user_avatar', 'user_name', 'user_title', 'user_bio',
    'background_html_path'
]

_SPECIAL_KEYS = ['skills', 'social_links', 'chart_palette']


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

    # Game engine specific binary and meta files
    '.meta', '.uasset', '.asset', '.unity', '.unitypackage', '.prefab',
    '.controller', '.anim', '.physicMaterial', '.physicsMaterial2D',
    '.mat', '.fbx', '.blend', '.3ds', '.max', '.dae', '.mb', '.ma',
    '.tga', '.cubemap', '.rendertexture', '.spriteatlas',
    '.umap', '.uproject', '.upk', '.pak', '.ubulk', '.uexp', '.umeta',
    '.scn', '.res', '.tres', '.tscn', '.material', '.shader',
    '.pck', '.gdc', '.import',

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
    'ProjectSettings', 'AssetBundles', 'Builds', 'Assets/Plugins',
    'Assets/StreamingAssets', 'Assets/Editor', 'Assets/ThirdParty',

    # Unity specific third-party SDKs
    'Assets/Oculus', 'Assets/MetaQuest', 'Assets/Meta', 'Assets/FacebookSDK',
    'Assets/Firebase', 'Assets/GooglePlayPlugins', 'Assets/Plugins/Demigiant',
    'Assets/TextMesh Pro', 'Assets/Plugins/DOTween', 'Assets/Plugins/FMOD',
    'Assets/Photon', 'Assets/Gizmosplus', 'Assets/AmplifyShaderEditor',

    # Common Unity asset store plugins
    'Assets/Plugins/CW', 'Assets/Assets/JMO Assets', 'Assets/PuppetMaster',
    'Assets/ProCore', 'Assets/AssetStoreTools',

    # Unreal Engine specific
    'Saved', 'Intermediate', 'Binaries', 'DerivedDataCache',
    'Build', 'Plugins/*/Intermediate', 'Plugins/*/Binaries',

    # Unreal specific third-party SDKs
    'Plugins/Online', 'Plugins/FMODStudio', 'Plugins/Wwise',
    'Plugins/Runtime/Oculus', 'Plugins/Runtime/Meta',

    # Godot specific
    '.import', 'addons', '.godot',

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

# Media file extensions for specific media types
IMAGE_FILE_EXTENSIONS: Set[str] = {
    # Common image formats
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp', '.tiff', '.tif',
    '.psd', '.ai', '.eps', '.indd', '.raw', '.cr2', '.nef', '.heif', '.heic', '.exr',
    '.hdr', '.dds', '.ktx', '.astc'
}

AUDIO_FILE_EXTENSIONS: Set[str] = {
    # Common audio formats
    '.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.aiff', '.alac',
    '.opus', '.midi', '.mid', '.mod', '.xm', '.it', '.s3m', '.voc', '.adpcm',
    '.aif', '.aifc', '.amr',

    # Game-specific audio formats
    '.bank', '.bnk', '.sound', '.snd', '.sfx', '.cue', '.wem', '.fsb',
    '.audio', '.msadpcm', '.dls', '.sf2', '.sfz',

    # Unity specific audio formats
    '.asset_audio', '.audioclip',

    # Audio metadata formats
    '.mtb', '.cue',

    # Raw audio data
    '.pcm', '.raw', '.smp'
}

VIDEO_FILE_EXTENSIONS: Set[str] = {
    # Common video formats
    '.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.flv', '.m4v', '.mpg', '.mpeg',
    '.3gp', '.ogv', '.vob', '.divx', '.xvid', '.asf', '.m2v', '.m2ts', '.mts',
    '.rmvb', '.ts', '.yuv'
}

MODEL_3D_FILE_EXTENSIONS: Set[str] = {
    # Common 3D model formats
    '.fbx', '.obj', '.blend', '.3ds', '.max', '.c4d', '.maya', '.ma', '.mb',
    '.stl', '.dae', '.glb', '.gltf', '.ply', '.x3d', '.abc', '.wrl', '.vrml', '.usd',
    '.usda', '.usdc'
}

# Combined set of all media file extensions
MEDIA_FILE_EXTENSIONS: Set[str] = (
        IMAGE_FILE_EXTENSIONS |
        AUDIO_FILE_EXTENSIONS |
        VIDEO_FILE_EXTENSIONS |
        MODEL_3D_FILE_EXTENSIONS
)


class GameEngine(Enum):
    """Supported game engines."""
    UNITY = "Unity"
    UNREAL_ENGINE = "Unreal Engine"
    GODOT = "Godot"
    UNKNOWN = "Other/Unknown"


@dataclass
class DetectionResult:
    """Result of game repository detection."""
    is_game_repo: bool
    engine_type: str
    confidence: float
    detected_features: List[str]
    file_indicators: Dict[str, int]
    directory_indicators: List[str]


class GameRepoDetector:
    """
    Advanced game repository detector supporting Unity, Unreal Engine, and Godot.

    This class provides enhanced detection capabilities with detailed analysis
    of file types, directory structures, and engine-specific indicators.
    """

    # Game engine file extensions (excluding meta files for counting)
    # Engine-specific file patterns
    ENGINE_FILES = {
        GameEngine.UNITY: {
            '.unity', '.unitypackage', '.asset', '.prefab', '.mat', '.meta',
            '.cubemap', '.flare', '.fontsettings', '.guiskin',
            '.physicMaterial', '.physicsMaterial2D', '.renderTexture',
            '.mixer', '.shadervariants', '.spriteatlas', '.terrainlayer',
        },
        GameEngine.UNREAL_ENGINE: {
            '.uasset', '.umap', '.upk', '.uproject', '.uplugin', '.uclass',
            '.ini', '.pak'
        },
        GameEngine.GODOT: {
            '.godot', '.tscn', '.gd', '.tres', '.import', '.remap', '.cfg'
        }
    }

    # Engine-specific directories
    ENGINE_DIRECTORIES = {
        GameEngine.UNITY: {
            'Assets', 'ProjectSettings', 'Packages', 'Library', 'Temp',
            'UserSettings', 'Logs'
        },
        GameEngine.UNREAL_ENGINE: {
            'Content', 'Config', 'Binaries', 'Intermediate', 'Saved',
            'Source', 'Plugins', 'DerivedDataCache'
        },
        GameEngine.GODOT: {
            '.godot', 'addons', 'scenes', 'scripts', 'assets',
            'autoload', 'project'
        }
    }

    # Strong indicators (project files that definitively identify an engine)
    STRONG_INDICATORS = {
        GameEngine.UNITY: {'.unity', '.asmdef', 'ProjectSettings'},
        GameEngine.UNREAL_ENGINE: {'.uproject', '.uplugin'},
        GameEngine.GODOT: {'.godot', '.tscn', '.gd', 'project.godot'}
    }

    # Programming language indicators
    LANGUAGE_INDICATORS = {
        GameEngine.UNITY: {'C#': 0.2},  # Minimum percentage for confidence boost
        GameEngine.UNREAL_ENGINE: {'C++': 0.2, 'Blueprint': 0.1},
        GameEngine.GODOT: {'GDScript': 0.1, 'C#': 0.1, 'C++': 0.1}
    }

    def __init__(self, min_confidence_threshold: float = 0.5):
        """
        Initialize the GameRepoDetector.

        Args:
            min_confidence_threshold: Minimum confidence to classify as game repo
        """
        self.min_confidence_threshold = min_confidence_threshold
        self._reset_detection_state()

    def _reset_detection_state(self):
        """Reset internal detection state."""
        self._detected_features = []
        self._file_indicators = {}
        self._directory_indicators = []

    def detect(self, file_types: Dict[str, int],
               project_structure: Dict[str, int]) -> DetectionResult:
        """
        Detect if repository is a game project and identify the engine.

        Args:
            file_types: Dictionary of file extensions with counts
            project_structure: Dictionary of top-level directories with counts

        Returns:
            DetectionResult with comprehensive analysis
        """
        self._reset_detection_state()

        if not file_types:
            return self._create_negative_result()

        total_files = sum(file_types.values())
        if total_files == 0:
            return self._create_negative_result()

        # Analyze each engine
        unity_score = self._analyze_engine(GameEngine.UNITY, file_types,
                                           project_structure, total_files)
        unreal_score = self._analyze_engine(GameEngine.UNREAL_ENGINE, file_types,
                                            project_structure, total_files)
        godot_score = self._analyze_engine(GameEngine.GODOT, file_types,
                                           project_structure, total_files)

        # Determine best match
        scores = {
            GameEngine.UNITY: unity_score,
            GameEngine.UNREAL_ENGINE: unreal_score,
            GameEngine.GODOT: godot_score
        }

        best_engine = max(scores, key=scores.get)
        best_confidence = scores[best_engine]

        # Apply language-based confidence boosts
        best_confidence = self._apply_language_boost(
            best_engine, file_types, total_files, best_confidence
        )

        # Cap confidence at 1.0
        best_confidence = min(1.0, best_confidence)

        return DetectionResult(
            is_game_repo=best_confidence >= self.min_confidence_threshold,
            engine_type=best_engine.value,
            confidence=best_confidence,
            detected_features=self._detected_features.copy(),
            file_indicators=self._file_indicators.copy(),
            directory_indicators=self._directory_indicators.copy()
        )

    def _analyze_engine(self, engine: GameEngine, file_types: Dict[str, int],
                        project_structure: Dict[str, int], total_files: int) -> float:
        """Analyze likelihood of specific engine."""
        confidence = 0.0

        # Check for strong indicators (project files)
        strong_indicators = self._check_strong_indicators(
            engine, file_types, project_structure
        )
        if strong_indicators:
            confidence += 0.7
            self._detected_features.extend(strong_indicators)

        # Check directory structure
        dir_score = self._check_directories(engine, project_structure)
        confidence += dir_score

        # Check file types
        file_score = self._check_file_types(engine, file_types, total_files)
        confidence += file_score

        return confidence

    def _check_strong_indicators(self, engine: GameEngine,
                                 file_types: Dict[str, int],
                                 project_structure: Dict[str, int]) -> List[str]:
        """Check for strong engine indicators."""
        indicators = []
        strong_files = self.STRONG_INDICATORS[engine]

        # Check file extensions
        for ext in strong_files:
            if ext.startswith('.') and ext in file_types:
                indicators.append(f"{engine.value} project file: {ext}")
                self._file_indicators[ext] = file_types[ext]

        # Check directories
        for dir_name in strong_files:
            if not dir_name.startswith('.') and dir_name in project_structure:
                indicators.append(f"{engine.value} directory: {dir_name}")
                self._directory_indicators.append(dir_name)

        return indicators

    def _check_directories(self, engine: GameEngine,
                           project_structure: Dict[str, int]) -> float:
        """Check directory structure for engine indicators."""
        engine_dirs = self.ENGINE_DIRECTORIES[engine]
        matched_dirs = 0

        for directory in project_structure:
            dir_lower = directory.lower()

            # Exact match
            if directory in engine_dirs:
                matched_dirs += 1
                self._directory_indicators.append(directory)
            # Case-insensitive or pattern match for Godot
            elif engine == GameEngine.GODOT and (
                    dir_lower.endswith('.godot') or
                    any(d.lower() == dir_lower for d in engine_dirs)
            ):
                matched_dirs += 1
                self._directory_indicators.append(directory)

        # Score based on matched directories
        if matched_dirs >= 2:
            return 0.3 + (matched_dirs * 0.05)
        elif matched_dirs == 1:
            return 0.15
        return 0.0

    def _check_file_types(self, engine: GameEngine,
                          file_types: Dict[str, int], total_files: int) -> float:
        """Check file types for engine indicators."""
        engine_files = self.ENGINE_FILES[engine]
        engine_file_count = 0

        for ext, count in file_types.items():
            if ext.lower() in {e.lower() for e in engine_files}:
                engine_file_count += count
                if ext not in self._file_indicators:
                    self._file_indicators[ext] = count

        # Calculate ratio (excluding meta files for Unity if they dominate)
        effective_total = total_files
        if engine == GameEngine.UNITY and '.meta' in file_types:
            meta_count = file_types['.meta']
            if meta_count > total_files * 0.5:
                effective_total = total_files - meta_count
                engine_file_count -= meta_count

        if effective_total > 0 and engine_file_count > 3:
            ratio = engine_file_count / effective_total
            return min(0.4, ratio * 0.8)  # Cap file type contribution

        return 0.0

    def _apply_language_boost(self, engine: GameEngine,
                              file_types: Dict[str, int],
                              total_files: int, base_confidence: float) -> float:
        """Apply confidence boost based on programming languages."""
        if engine not in self.LANGUAGE_INDICATORS:
            return base_confidence

        boost = 0.0
        language_thresholds = self.LANGUAGE_INDICATORS[engine]

        for language, min_percentage in language_thresholds.items():
            if language in file_types:
                percentage = file_types[language] / total_files
                if percentage >= min_percentage:
                    boost += 0.1
                    self._detected_features.append(
                        f"{language} usage ({percentage:.1%})"
                    )

        return base_confidence + boost

    @staticmethod
    def _create_negative_result() -> DetectionResult:
        """Create result for non-game repositories."""
        return DetectionResult(
            is_game_repo=False,
            engine_type=GameEngine.UNKNOWN.value,
            confidence=0.0,
            detected_features=[],
            file_indicators={},
            directory_indicators=[]
        )


# Backward compatibility function
def is_game_repo(file_types: Dict[str, int], project_structure: Dict[str, int]) -> Dict[str, Any]:
    """
    Determine if a repository is likely a game project and which engine it uses.

    This function maintains backward compatibility with the original implementation.

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

    detector = GameRepoDetector()
    result = detector.detect(file_types, project_structure)

    return {
        'is_game_repo': result.is_game_repo,
        'engine_type': result.engine_type,
        'confidence': result.confidence
    }


class ConfigLoader:
    """
    Class responsible for loading configuration from files and handling configuration errors.
    Follows Single Responsibility Principle by focusing only on configuration loading.
    """

    def __init__(self):
        self.logger = logger

    def load(self, config_file: str) -> Configuration:
        """
        Load configuration from a file and return as Configuration dict.
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            Configuration: Dictionary with loaded configuration values
        """
        cp = configparser.ConfigParser()
        try:
            cp.read(config_file)
            config: Configuration = DEFAULT_CONFIG.copy()

            self._process_github_settings(cp, config)
            self._process_analysis_settings(cp, config)
            self._process_filter_settings(cp, config)
            self._process_checkpointing_settings(cp, config)
            self._process_iframe_settings(cp, config)
            self._process_theme_settings(cp, config_file)

            self.logger.info(f"Configuration loaded from {config_file}")
            return config

        except (configparser.Error, IOError) as e:
            return self._handle_config_error(config_file, e)

    @staticmethod
    def _process_github_settings(cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process GitHub related settings from config parser"""
        if "github" in cp:
            if "token" in cp["github"]:
                config["GITHUB_TOKEN"] = cp["github"]["token"]
            if "username" in cp["github"]:
                config["USERNAME"] = cp["github"]["username"]

    @staticmethod
    def _process_analysis_settings(cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process analysis related settings from config parser"""
        if "analysis" in cp:
            if "reports_dir" in cp["analysis"]:
                config["REPORTS_DIR"] = cp["analysis"]["reports_dir"]
            if "clone_dir" in cp["analysis"]:
                config["CLONE_DIR"] = cp["analysis"]["clone_dir"]
            if "max_workers" in cp["analysis"]:
                config["MAX_WORKERS"] = cp["analysis"].getint("max_workers")
            if "inactive_threshold_days" in cp["analysis"]:
                config["INACTIVE_THRESHOLD_DAYS"] = cp["analysis"].getint("inactive_threshold_days")
            if "large_repo_loc_threshold" in cp["analysis"]:
                config["LARGE_REPO_LOC_THRESHOLD"] = cp["analysis"].getint("large_repo_loc_threshold")

    def _process_filter_settings(self, cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process filter related settings from config parser"""
        if "filters" in cp:
            if "skip_forks" in cp["filters"]:
                config["SKIP_FORKS"] = cp["filters"].getboolean("skip_forks")
            if "skip_archived" in cp["filters"]:
                config["SKIP_ARCHIVED"] = cp["filters"].getboolean("skip_archived")
            if "visibility" in cp["filters"]:
                self._process_visibility_setting(cp, config)
            if "analyze_clones" in cp["filters"]:
                config["ANALYZE_CLONES"] = cp["filters"].getboolean("analyze_clones")
            if "include_orgs" in cp["filters"]:
                self._process_orgs_setting(cp, config)

    def _process_visibility_setting(self, cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process visibility setting with validation"""
        visibility = cp["filters"]["visibility"].lower()
        if visibility in ["all", "public", "private"]:
            # noinspection PyTypedDict
            config["VISIBILITY"] = visibility
            # For backward compatibility
            config["INCLUDE_PRIVATE"] = visibility in ["all", "private"]
        else:
            self.logger.warning(f"Invalid visibility value: {visibility}. Using default: all")

    @staticmethod
    def _process_orgs_setting(cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process organizations list setting"""
        org_list = cp["filters"]["include_orgs"].strip()
        if org_list:
            config["INCLUDE_ORGS"] = [o.strip() for o in org_list.split(",") if o.strip()]

    @staticmethod
    def _process_checkpointing_settings(cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process checkpointing related settings from config parser"""
        if "checkpointing" in cp:
            if "enable_checkpointing" in cp["checkpointing"]:
                config["ENABLE_CHECKPOINTING"] = cp["checkpointing"].getboolean("enable_checkpointing")
            if "checkpoint_file" in cp["checkpointing"]:
                config["CHECKPOINT_FILE"] = cp["checkpointing"]["checkpoint_file"]
            if "checkpoint_threshold" in cp["checkpointing"]:
                config["CHECKPOINT_THRESHOLD"] = cp["checkpointing"].getint("checkpoint_threshold")
            if "resume_from_checkpoint" in cp["checkpointing"]:
                config["RESUME_FROM_CHECKPOINT"] = cp["checkpointing"].getboolean("resume_from_checkpoint")

    def _process_iframe_settings(self, cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process iframe embedding related settings from config parser"""
        if "iframe" in cp:
            if "iframe_embedding" in cp["iframe"]:
                self._process_iframe_embedding_setting(cp, config)
            if "vercel_token" in cp["iframe"]:
                # Clean the token to avoid whitespace issues
                token = cp["iframe"]["vercel_token"].strip()
                config["VERCEL_TOKEN"] = token
            if "vercel_project_name" in cp["iframe"]:
                config["VERCEL_PROJECT_NAME"] = cp["iframe"]["vercel_project_name"].strip()

    def _process_iframe_embedding_setting(self, cp: configparser.ConfigParser, config: Configuration) -> None:
        """Process iframe embedding setting with validation"""
        embedding_mode = cp["iframe"]["iframe_embedding"].lower()
        if embedding_mode in ["disabled", "partial", "full"]:
            # noinspection PyTypedDict
            config["IFRAME_EMBEDDING"] = embedding_mode
        else:
            self.logger.warning(f"Invalid iframe_embedding value: {embedding_mode}. Using default: disabled")

    def _process_theme_settings(self, cp: configparser.ConfigParser, config_file: str) -> None:
        """Process theme related settings from config parser"""
        if 'theme' in cp:
            theme_section = cp['theme']
            # Store theme configuration for later use by DefaultTheme and HTMLVisualizer
            global LOADED_THEME_CONFIG
            LOADED_THEME_CONFIG = {}

            # Process all keys in the theme section
            for key, value in theme_section.items():
                LOADED_THEME_CONFIG[key] = value

            self._process_json_theme_fields(theme_section)
            self.logger.info(f"Loaded theme configuration from {config_file}")

    def _process_json_theme_fields(self, theme_section: configparser.SectionProxy) -> None:
        """Process JSON fields in theme section"""
        try:
            json_fields = ['skills', 'social_links', 'chart_palette']
            for field in json_fields:
                if field in theme_section:
                    LOADED_THEME_CONFIG[field] = json.loads(theme_section[field])
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON in theme section: {e}")

    def _handle_config_error(self, config_file: str, error: Exception) -> Configuration:
        """Handle configuration loading errors"""
        self.logger.error(f"Error loading configuration from {config_file}: {str(error)}")
        self.logger.info("Using default configuration")
        console.print(f"[yellow]Warning:[/yellow] Failed to load config from {config_file}: {error}")
        console.print("[yellow]Using default configuration instead[/yellow]")
        return DEFAULT_CONFIG.copy()


def load_config_from_file(config_file: str) -> Configuration:
    """
    Load configuration from a file and return as Configuration dict.
    
    Args:
        config_file: Path to the configuration file
        
    Returns:
        Configuration: Dictionary with loaded configuration values
    """
    config_loader = ConfigLoader()
    return config_loader.load(config_file)


# Global variable to store theme configuration loaded from config file
LOADED_THEME_CONFIG: Optional[dict] = None


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

    # Add iframe configuration section
    config['iframe'] = {
        'iframe_embedding': 'disabled',  # "disabled", "partial", or "full"
        'vercel_token': 'your_vercel_token_here',
        'vercel_project_name': 'ghrepolens-username'
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


def create_sample_env() -> None:
    """
    Create a sample .env file if it doesn't exist.
    
    Generates a sample .env file with default settings and environment variables
    as a template for users to customize.
    """
    env_file = '.env.sample'

    if os.path.exists(env_file):
        return

    env_content = """# GitHub Authentication
GITHUB_TOKEN=your_github_token_here
GITHUB_USERNAME=your_github_username_here

# Repository Analysis Settings
GITHUB_VISIBILITY=all  # all, public, or private

# Iframe Embedding Settings
IFRAME_EMBEDDING=disabled  # disabled, partial, or full
VERCEL_TOKEN=your_vercel_token_here
VERCEL_PROJECT_NAME=ghrepolens-username

# Optional: Checkpointing
ENABLE_CHECKPOINTING=true
RESUME_FROM_CHECKPOINT=true
"""

    with open(env_file, 'w') as f:
        f.write(env_content)

    console.print(f"[green]Created sample environment file: {env_file}[/green]")
    console.print("[yellow]Rename to .env and update with your settings.[/yellow]")


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
    global LOADED_THEME_CONFIG

    if LOADED_THEME_CONFIG is not None:
        logger.info("Using previously loaded theme configuration")
        return _merge_with_default_theme(LOADED_THEME_CONFIG)

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
        theme = _apply_theme_section(theme, theme_section)
        logger.info(f"Loaded theme configuration from {config_file}")
        return theme

    except Exception as e:
        logger.error(f"Error loading theme from {config_file}: {e}")
        return theme


# noinspection PyTypedDict
def _merge_with_default_theme(loaded: Dict) -> ThemeConfig:
    theme = DefaultTheme.get_default_theme()

    # Simple string fields
    for key, value in loaded.items():
        if key in theme and isinstance(value, str) and key not in _SPECIAL_KEYS:
            theme[key] = value

    # Complex fields (already parsed)
    for key in _SPECIAL_KEYS:
        if key in loaded:
            theme[key] = loaded[key]

    return theme


# noinspection PyTypedDict
def _apply_theme_section(theme: ThemeConfig, section: configparser.SectionProxy) -> ThemeConfig:
    for key in _STRING_KEYS:
        if key in section:
            theme[key] = section[key]

    for key in _SPECIAL_KEYS:
        if key in section:
            try:
                theme[key] = json.loads(section[key])
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for '{key}' in config.ini, using default {key}")

    return theme


def shutdown_logging() -> None:
    """
    This function is kept for backwards compatibility.
    The actual logging shutdown is now handled in console.py
    """
    # Nothing to do, just import to ensure proper references
    pass


def get_media_type(file_path: str) -> Optional[str]:
    """
    Determine the type of media file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Media type as string ('image', 'audio', 'video', 'model_3d') or None if not a media file
    """
    ext = Path(file_path).suffix.lower()

    if ext in IMAGE_FILE_EXTENSIONS:
        return 'image'
    elif ext in AUDIO_FILE_EXTENSIONS:
        return 'audio'
    elif ext in VIDEO_FILE_EXTENSIONS:
        return 'video'
    elif ext in MODEL_3D_FILE_EXTENSIONS:
        return 'model_3d'

    return None
