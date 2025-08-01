#!/usr/bin/env python3
"""
Data Models for GitHub Repository RunnerAnalyzer

This module defines the data structures used to store and manipulate repository 
information and statistics. The module uses dataclasses to create a clean, 
type-hinted data model with proper composition for analyzing GitHub repositories.

Key components:
- BaseRepoInfo: Basic repository metadata
- CodeStats: Code statistics and language information
- QualityIndicators: Code quality metrics
- ActivityMetrics: Repository activity data
- CommunityMetrics: Community engagement metrics
- AnalysisScores: Calculated scores and anomaly detection
- RepoStats: Comprehensive repository statistics (composition of above classes)
- MediaMetrics: Media file metrics for a repository
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class BaseRepoInfo:
    """
    Base repository information containing core metadata.
    
    Stores fundamental attributes of a GitHub repository including name,
    visibility, branch information, and timestamps.
    """
    name: str
    is_private: bool
    default_branch: str
    is_fork: bool
    is_archived: bool
    is_template: bool
    created_at: datetime
    last_pushed: datetime
    description: Optional[str] = None
    homepage: Optional[str] = None


@dataclass
class CodeStats:
    """
    Code statistics for a repository.
    
    Stores metrics related to the codebase including language distribution,
    file counts, lines of code, and project structure information.
    """
    languages: Dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_loc: int = 0
    avg_loc_per_file: float = 0.0
    file_types: Dict[str, int] = field(default_factory=dict)
    size_kb: int = 0
    excluded_file_count: int = 0
    primary_language: Optional[str] = None
    project_structure: Dict[str, int] = field(default_factory=dict)
    is_monorepo: bool = False
    
    # Game repository information
    is_game_repo: bool = False
    game_engine: str = "None"  # Unity, Unreal Engine, Godot, or Other/Unknown
    game_confidence: float = 0.0  # Confidence level 0.0-1.0

    def calculate_primary_language(self) -> None:
        """
        Determine the primary language of the repository based on lines of code.
        
        Sets the primary_language field to the language with the most lines of code,
        or "Unknown" if no language data is available.
        """
        if not self.languages:
            self.primary_language = "Unknown"
            return

        # Recalculate total_loc as the sum of all language LOCs
        self.total_loc = sum(self.languages.values())

        # Filter out non-programming languages if there are actual programming languages
        programming_languages = {
            lang: loc for lang, loc in self.languages.items()
            if lang not in ('Other', 'Text', 'Markdown', 'JSON', 'YAML', 'TOML', 'INI')
        }

        # If we have programming languages, use those for determining primary language
        if programming_languages:
            primary_lang = max(programming_languages.items(), key=lambda x: x[1])
            self.primary_language = primary_lang[0]
        else:
            # Otherwise fall back to using all languages including documentation/config
            primary_lang = max(self.languages.items(), key=lambda x: x[1])
            self.primary_language = primary_lang[0]

    def detect_monorepo(self) -> None:
        """
        Detect if this is likely a monorepo based on language distribution.
        
        Sets is_monorepo to True if the repository has at least 3 languages
        with each having a significant share (>10%) of the codebase.
        """
        if len(self.languages) >= 3:
            # Ensure total_loc is calculated correctly
            total_loc = self.total_loc
            if total_loc == 0:
                # Recalculate if needed
                total_loc = sum(self.languages.values())
                self.total_loc = total_loc

            if total_loc == 0:
                return

            sorted_langs = sorted(self.languages.items(), key=lambda x: x[1], reverse=True)

            # If at least 3 languages with significant share (>10%)
            significant_langs = [lang for lang, loc in sorted_langs if (loc / total_loc) > 0.1]
            if len(significant_langs) >= 3:
                self.is_monorepo = True


@dataclass
class QualityIndicators:
    """
    Code quality indicators for a repository.
    
    Tracks metrics related to documentation, testing, continuous integration,
    and dependency management.
    """
    has_docs: bool = False
    has_readme: bool = False
    has_tests: bool = False
    test_files_count: int = 0
    test_coverage_percentage: Optional[float] = None
    has_cicd: bool = False
    cicd_files: List[str] = field(default_factory=list)
    dependency_files: List[str] = field(default_factory=list)

    # Package management
    has_packages: bool = False
    package_files: List[str] = field(default_factory=list)

    # Deployment and release info
    has_deployments: bool = False
    deployment_files: List[str] = field(default_factory=list)
    has_releases: bool = False
    release_count: int = 0

    # Documentation quality indicators
    docs_size_category: str = "None"  # None, Small, Intermediate, Big
    docs_files_count: int = 0

    # README quality
    readme_comprehensiveness: str = "None"  # None, Small, Good, Comprehensive
    readme_line_count: int = 0


@dataclass
class ActivityMetrics:
    """
    Activity metrics for a repository.
    
    Tracks time-based activity metrics including commit history and frequency.
    """
    last_commit_date: Optional[datetime] = None
    is_active: bool = False
    commit_frequency: Optional[float] = None
    commits_last_month: int = 0
    commits_last_year: int = 0


@dataclass
class CommunityMetrics:
    """
    Community engagement metrics for a repository.
    
    Tracks metrics related to community engagement, including stars, forks,
    issues, pull requests, and licensing information.
    """
    license_name: Optional[str] = None
    license_spdx_id: Optional[str] = None
    contributors_count: int = 0
    open_issues: int = 0
    open_prs: int = 0
    closed_issues: int = 0
    topics: List[str] = field(default_factory=list)
    stars: int = 0
    forks: int = 0
    watchers: int = 0


@dataclass
class AnalysisScores:
    """
    Analysis scores for a repository.
    
    Contains calculated scores based on various metrics and tracks
    detected anomalies in the repository.
    """
    maintenance_score: float = 0.0
    popularity_score: float = 0.0
    code_quality_score: float = 0.0
    documentation_score: float = 0.0
    anomalies: List[str] = field(default_factory=list)

    def add_anomaly(self, anomaly: str) -> None:
        """
        Add an anomaly to the repository's list of anomalies.
        
        Args:
            anomaly: Description of the anomaly to add
        """
        self.anomalies.append(anomaly)


@dataclass
class MediaMetrics:
    """
    Media file metrics for a repository.
    
    Tracks the presence and quantity of different types of media files
    like images, audio, video, and 3D models.
    """
    # Counters for different media types
    image_count: int = 0
    audio_count: int = 0
    video_count: int = 0
    model_3d_count: int = 0
    
    # File paths by category
    image_files: List[str] = field(default_factory=list)
    audio_files: List[str] = field(default_factory=list)
    video_files: List[str] = field(default_factory=list)
    model_3d_files: List[str] = field(default_factory=list)
    
    # Total size in KB by category
    image_size_kb: int = 0
    audio_size_kb: int = 0
    video_size_kb: int = 0
    model_3d_size_kb: int = 0
    
    # Summary properties
    @property
    def has_media(self) -> bool:
        """Whether the repository has any media files."""
        return (self.image_count > 0 or self.audio_count > 0 or 
                self.video_count > 0 or self.model_3d_count > 0)
    
    @property
    def total_media_count(self) -> int:
        """Total number of media files."""
        return self.image_count + self.audio_count + self.video_count + self.model_3d_count
    
    @property
    def total_media_size_kb(self) -> int:
        """Total size of media files in KB."""
        return self.image_size_kb + self.audio_size_kb + self.video_size_kb + self.model_3d_size_kb
    
    def add_media_file(self, file_path: str, media_type: str, size_kb: int) -> None:
        """
        Add a media file to the appropriate category.
        
        Args:
            file_path: Path to the media file
            media_type: Type of media ('image', 'audio', 'video', 'model_3d')
            size_kb: Size of the file in KB
        """
        if media_type == 'image':
            self.image_count += 1
            self.image_files.append(file_path)
            self.image_size_kb += size_kb
        elif media_type == 'audio':
            self.audio_count += 1
            self.audio_files.append(file_path)
            self.audio_size_kb += size_kb
        elif media_type == 'video':
            self.video_count += 1
            self.video_files.append(file_path)
            self.video_size_kb += size_kb
        elif media_type == 'model_3d':
            self.model_3d_count += 1
            self.model_3d_files.append(file_path)
            self.model_3d_size_kb += size_kb


@dataclass
class RepoStats:
    """
    Data class to hold comprehensive repository statistics.
    
    This is the main data structure used throughout the analyzer, combining
    all other data classes through composition for a complete repository analysis.
    """
    # Composition of focused data classes
    base_info: BaseRepoInfo
    code_stats: CodeStats = field(default_factory=CodeStats)
    quality: QualityIndicators = field(default_factory=QualityIndicators)
    activity: ActivityMetrics = field(default_factory=ActivityMetrics)
    community: CommunityMetrics = field(default_factory=CommunityMetrics)
    scores: AnalysisScores = field(default_factory=AnalysisScores)
    media: MediaMetrics = field(default_factory=MediaMetrics)

    # Convenience properties to maintain backward compatibility
    @property
    def name(self) -> str:
        """Repository name."""
        return self.base_info.name

    @property
    def is_private(self) -> bool:
        """Whether the repository is private."""
        return self.base_info.is_private

    @property
    def default_branch(self) -> str:
        """Default branch of the repository."""
        return self.base_info.default_branch

    @property
    def is_fork(self) -> bool:
        """Whether the repository is a fork."""
        return self.base_info.is_fork

    @property
    def is_archived(self) -> bool:
        """Whether the repository is archived."""
        return self.base_info.is_archived

    @property
    def is_template(self) -> bool:
        """Whether the repository is a template."""
        return self.base_info.is_template

    @property
    def created_at(self) -> datetime:
        """Repository creation date."""
        return self.base_info.created_at

    @property
    def last_pushed(self) -> datetime:
        """Date of last push to the repository."""
        return self.base_info.last_pushed

    @property
    def languages(self) -> Dict[str, int]:
        """Dictionary of languages used in the repository with lines of code."""
        return self.code_stats.languages

    @property
    def total_files(self) -> int:
        """Total number of files in the repository."""
        return self.code_stats.total_files

    @property
    def total_loc(self) -> int:
        """Total lines of code in the repository."""
        return self.code_stats.total_loc

    @property
    def primary_language(self) -> Optional[str]:
        """Primary language of the repository based on lines of code."""
        return self.code_stats.primary_language

    @property
    def is_monorepo(self) -> bool:
        """Whether the repository is detected as a monorepo."""
        return self.code_stats.is_monorepo

    @property
    def is_game_repo(self) -> bool:
        """Whether the repository is detected as a game project."""
        return self.code_stats.is_game_repo

    @property
    def game_engine(self) -> str:
        """The detected game engine (Unity, Unreal Engine, Godot, or Other/Unknown)."""
        return self.code_stats.game_engine

    @property
    def game_confidence(self) -> float:
        """Confidence level (0.0-1.0) in the game repository detection."""
        return self.code_stats.game_confidence

    @property
    def last_commit_date(self) -> Optional[datetime]:
        """Date of the last commit to the repository."""
        return self.activity.last_commit_date

    @property
    def is_active(self) -> bool:
        """Whether the repository is actively maintained."""
        return self.activity.is_active

    @property
    def stars(self) -> int:
        """Number of stars the repository has."""
        return self.community.stars

    @property
    def anomalies(self) -> List[str]:
        """List of detected anomalies in the repository."""
        return self.scores.anomalies

    @property
    def avg_loc_per_file(self) -> float:
        """Average lines of code per file."""
        return self.code_stats.avg_loc_per_file

    @property
    def file_types(self) -> Dict[str, int]:
        """Dictionary of file types with counts."""
        return self.code_stats.file_types

    @property
    def size_kb(self) -> int:
        """Repository size in kilobytes."""
        return self.code_stats.size_kb

    @property
    def description(self) -> Optional[str]:
        """Repository description."""
        return self.base_info.description

    @property
    def homepage(self) -> Optional[str]:
        """Repository homepage URL."""
        return self.base_info.homepage

    @property
    def has_docs(self) -> bool:
        """Whether the repository has documentation."""
        return self.quality.has_docs

    @property
    def has_readme(self) -> bool:
        """Whether the repository has a README file."""
        return self.quality.has_readme

    @property
    def has_tests(self) -> bool:
        """Whether the repository has tests."""
        return self.quality.has_tests

    @property
    def test_files_count(self) -> int:
        """Number of test files in the repository."""
        return self.quality.test_files_count

    @property
    def test_coverage_percentage(self) -> Optional[float]:
        """Test coverage percentage if available."""
        return self.quality.test_coverage_percentage

    @property
    def has_cicd(self) -> bool:
        """Whether the repository has CI/CD configuration."""
        return self.quality.has_cicd

    @property
    def cicd_files(self) -> List[str]:
        """List of CI/CD configuration files."""
        return self.quality.cicd_files

    @property
    def dependency_files(self) -> List[str]:
        """List of dependency management files."""
        return self.quality.dependency_files

    @property
    def commit_frequency(self) -> Optional[float]:
        """Average commits per week."""
        return self.activity.commit_frequency

    @property
    def commits_last_month(self) -> int:
        """Number of commits in the last month."""
        return self.activity.commits_last_month

    @property
    def commits_last_year(self) -> int:
        """Number of commits in the last year."""
        return self.activity.commits_last_year

    @property
    def license_name(self) -> Optional[str]:
        """Name of the repository license."""
        return self.community.license_name

    @property
    def license_spdx_id(self) -> Optional[str]:
        """SPDX identifier of the repository license."""
        return self.community.license_spdx_id

    @property
    def contributors_count(self) -> int:
        """Number of contributors to the repository."""
        return self.community.contributors_count

    @property
    def open_issues(self) -> int:
        """Number of open issues in the repository."""
        return self.community.open_issues

    @property
    def open_prs(self) -> int:
        """Number of open pull requests in the repository."""
        return self.community.open_prs

    @property
    def closed_issues(self) -> int:
        """Number of closed issues in the repository."""
        return self.community.closed_issues

    @property
    def topics(self) -> List[str]:
        """List of repository topics."""
        return self.community.topics

    @property
    def forks(self) -> int:
        """Number of forks of the repository."""
        return self.community.forks

    @property
    def watchers(self) -> int:
        """Number of watchers of the repository."""
        return self.community.watchers

    @property
    def maintenance_score(self) -> float:
        """Calculated maintenance score for the repository."""
        return self.scores.maintenance_score

    @property
    def popularity_score(self) -> float:
        """Calculated popularity score for the repository."""
        return self.scores.popularity_score

    @property
    def code_quality_score(self) -> float:
        """Calculated code quality score for the repository."""
        return self.scores.code_quality_score

    @property
    def documentation_score(self) -> float:
        """Calculated documentation score for the repository."""
        return self.scores.documentation_score

    @property
    def project_structure(self) -> Dict[str, int]:
        """Dictionary representing the project directory structure."""
        return self.code_stats.project_structure

    @property
    def has_packages(self) -> bool:
        """Whether the repository has package management."""
        return self.quality.has_packages

    @property
    def package_files(self) -> List[str]:
        """List of package management files."""
        return self.quality.package_files

    @property
    def has_deployments(self) -> bool:
        """Whether the repository has deployment configuration."""
        return self.quality.has_deployments

    @property
    def deployment_files(self) -> List[str]:
        """List of deployment configuration files."""
        return self.quality.deployment_files

    @property
    def has_releases(self) -> bool:
        """Whether the repository has releases."""
        return self.quality.has_releases

    @property
    def release_count(self) -> int:
        """Number of releases in the repository."""
        return self.quality.release_count

    @property
    def docs_size_category(self) -> str:
        """Size category of documentation (None, Small, Intermediate, Big)."""
        return self.quality.docs_size_category

    @property
    def docs_files_count(self) -> int:
        """Number of documentation files."""
        return self.quality.docs_files_count

    @property
    def readme_comprehensiveness(self) -> str:
        """Comprehensiveness of README (None, Small, Good, Comprehensive)."""
        return self.quality.readme_comprehensiveness

    @property
    def readme_line_count(self) -> int:
        """Line count of README file."""
        return self.quality.readme_line_count

    @property
    def has_media(self) -> bool:
        """Whether the repository has any media files."""
        return self.media.has_media
    
    @property
    def image_count(self) -> int:
        """Number of image files in the repository."""
        return self.media.image_count
    
    @property
    def audio_count(self) -> int:
        """Number of audio files in the repository."""
        return self.media.audio_count
    
    @property
    def video_count(self) -> int:
        """Number of video files in the repository."""
        return self.media.video_count
    
    @property
    def model_3d_count(self) -> int:
        """Number of 3D model files in the repository."""
        return self.media.model_3d_count
    
    @property
    def total_media_count(self) -> int:
        """Total number of media files."""
        return self.media.total_media_count
    
    @property
    def total_media_size_kb(self) -> int:
        """Total size of media files in KB."""
        return self.media.total_media_size_kb

    def add_anomaly(self, anomaly: str) -> None:
        """
        Add an anomaly to the repository's list of anomalies.
        
        Args:
            anomaly: Description of the anomaly to add
        """
        self.scores.add_anomaly(anomaly)

    def calculate_primary_language(self) -> None:
        """
        Determine the primary language of the repository based on lines of code.
        
        Delegates to the CodeStats component to calculate the primary language.
        """
        self.code_stats.calculate_primary_language()

    def detect_monorepo(self) -> None:
        """
        Detect if this is likely a monorepo based on language distribution and structure.
        
        Delegates to the CodeStats component to detect if this is a monorepo, and
        adds an anomaly if a monorepo is detected.
        """
        self.code_stats.detect_monorepo()
        if self.code_stats.is_monorepo:
            self.add_anomaly("Possible monorepo detected with multiple major languages")
