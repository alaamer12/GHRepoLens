#!/usr/bin/env python3
"""
Data Models for GitHub Repository Analyzer

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
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Union

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
    
    def calculate_primary_language(self) -> None:
        """
        Determine the primary language of the repository based on lines of code.
        
        Sets the primary_language field to the language with the most lines of code,
        or "Unknown" if no language data is available.
        """
        if not self.languages:
            self.primary_language = "Unknown"
            return
            
        primary_lang = max(self.languages.items(), key=lambda x: x[1])
        self.primary_language = primary_lang[0]
    
    def detect_monorepo(self) -> None:
        """
        Detect if this is likely a monorepo based on language distribution.
        
        Sets is_monorepo to True if the repository has at least 3 languages
        with each having a significant share (>10%) of the codebase.
        """
        if len(self.languages) >= 3:
            # Calculate distribution of top languages
            total_loc = sum(self.languages.values())
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