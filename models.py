#!/usr/bin/env python3
"""
Data models for GitHub Repository Analyzer.
Contains all dataclasses used to store repository information and statistics.
"""

from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class BaseRepoInfo:
    """Base repository information"""
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
    """Code statistics for a repository"""
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
        """Determine the primary language of the repository based on LOC"""
        if not self.languages:
            self.primary_language = "Unknown"
            return
            
        primary_lang = max(self.languages.items(), key=lambda x: x[1])
        self.primary_language = primary_lang[0]
    
    def detect_monorepo(self) -> None:
        """Detect if this is likely a monorepo based on language distribution"""
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
    """Code quality indicators for a repository"""
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
    """Activity metrics for a repository"""
    last_commit_date: Optional[datetime] = None
    is_active: bool = False
    commit_frequency: Optional[float] = None
    commits_last_month: int = 0
    commits_last_year: int = 0

@dataclass
class CommunityMetrics:
    """Community engagement metrics for a repository"""
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
    """Analysis scores for a repository"""
    maintenance_score: float = 0.0
    popularity_score: float = 0.0
    code_quality_score: float = 0.0
    documentation_score: float = 0.0
    anomalies: List[str] = field(default_factory=list)
    
    def add_anomaly(self, anomaly: str) -> None:
        """Add an anomaly to the repository's list of anomalies"""
        self.anomalies.append(anomaly)

@dataclass
class RepoStats:
    """Data class to hold comprehensive repository statistics"""
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
        return self.base_info.name
    
    @property
    def is_private(self) -> bool:
        return self.base_info.is_private
    
    @property
    def default_branch(self) -> str:
        return self.base_info.default_branch
    
    @property
    def is_fork(self) -> bool:
        return self.base_info.is_fork
    
    @property
    def is_archived(self) -> bool:
        return self.base_info.is_archived
    
    @property
    def is_template(self) -> bool:
        return self.base_info.is_template
    
    @property
    def created_at(self) -> datetime:
        return self.base_info.created_at
    
    @property
    def last_pushed(self) -> datetime:
        return self.base_info.last_pushed
    
    @property
    def languages(self) -> Dict[str, int]:
        return self.code_stats.languages
    
    @property
    def total_files(self) -> int:
        return self.code_stats.total_files
    
    @property
    def total_loc(self) -> int:
        return self.code_stats.total_loc
    
    @property
    def primary_language(self) -> Optional[str]:
        return self.code_stats.primary_language
    
    @property
    def is_monorepo(self) -> bool:
        return self.code_stats.is_monorepo
    
    @property
    def last_commit_date(self) -> Optional[datetime]:
        return self.activity.last_commit_date
    
    @property
    def is_active(self) -> bool:
        return self.activity.is_active
    
    @property
    def stars(self) -> int:
        return self.community.stars
    
    @property
    def anomalies(self) -> List[str]:
        return self.scores.anomalies
    
    @property
    def avg_loc_per_file(self) -> float:
        return self.code_stats.avg_loc_per_file
    
    @property
    def file_types(self) -> Dict[str, int]:
        return self.code_stats.file_types
    
    @property
    def size_kb(self) -> int:
        return self.code_stats.size_kb
    
    @property
    def description(self) -> Optional[str]:
        return self.base_info.description
    
    @property
    def homepage(self) -> Optional[str]:
        return self.base_info.homepage
    
    @property
    def has_docs(self) -> bool:
        return self.quality.has_docs
    
    @property
    def has_readme(self) -> bool:
        return self.quality.has_readme
    
    @property
    def has_tests(self) -> bool:
        return self.quality.has_tests
    
    @property
    def test_files_count(self) -> int:
        return self.quality.test_files_count
    
    @property
    def test_coverage_percentage(self) -> Optional[float]:
        return self.quality.test_coverage_percentage
    
    @property
    def has_cicd(self) -> bool:
        return self.quality.has_cicd
    
    @property
    def cicd_files(self) -> List[str]:
        return self.quality.cicd_files
    
    @property
    def dependency_files(self) -> List[str]:
        return self.quality.dependency_files
    
    @property
    def commit_frequency(self) -> Optional[float]:
        return self.activity.commit_frequency
    
    @property
    def commits_last_month(self) -> int:
        return self.activity.commits_last_month
    
    @property
    def commits_last_year(self) -> int:
        return self.activity.commits_last_year
    
    @property
    def license_name(self) -> Optional[str]:
        return self.community.license_name
    
    @property
    def license_spdx_id(self) -> Optional[str]:
        return self.community.license_spdx_id
    
    @property
    def contributors_count(self) -> int:
        return self.community.contributors_count
    
    @property
    def open_issues(self) -> int:
        return self.community.open_issues
    
    @property
    def open_prs(self) -> int:
        return self.community.open_prs
    
    @property
    def closed_issues(self) -> int:
        return self.community.closed_issues
    
    @property
    def topics(self) -> List[str]:
        return self.community.topics
    
    @property
    def forks(self) -> int:
        return self.community.forks
    
    @property
    def watchers(self) -> int:
        return self.community.watchers
    
    @property
    def maintenance_score(self) -> float:
        return self.scores.maintenance_score
    
    @property
    def popularity_score(self) -> float:
        return self.scores.popularity_score
    
    @property
    def code_quality_score(self) -> float:
        return self.scores.code_quality_score
    
    @property
    def documentation_score(self) -> float:
        return self.scores.documentation_score
    
    @property
    def project_structure(self) -> Dict[str, int]:
        return self.code_stats.project_structure
    
    def add_anomaly(self, anomaly: str) -> None:
        """Add an anomaly to the repository's list of anomalies"""
        self.scores.add_anomaly(anomaly)
    
    def calculate_primary_language(self) -> None:
        """Determine the primary language of the repository based on LOC"""
        self.code_stats.calculate_primary_language()
    
    def detect_monorepo(self) -> None:
        """Detect if this is likely a monorepo based on language distribution and structure"""
        self.code_stats.detect_monorepo()
        if self.code_stats.is_monorepo:
            self.add_anomaly("Possible monorepo detected with multiple major languages") 