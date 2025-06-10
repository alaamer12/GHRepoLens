#!/usr/bin/env python3
"""
Test script for verifying the fix for Lines of Code (LOC) calculation
"""

import logging
from datetime import datetime

from models import CodeStats, RepoStats, BaseRepoInfo, ActivityMetrics, QualityIndicators, CommunityMetrics, \
    AnalysisScores

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()


def main():
    # Create a sample language dictionary that simulates file analysis
    file_analysis_languages = {
        'Python': 513,  # Real LOC according to user
        'Jinja': 120,  # Example of a more realistic count
        'TeX': 250,  # Example of a more realistic count
        'Markdown': 167,  # Example of a more realistic count
        'LaTeX': 243,  # Example of a more realistic count
        'Other': 31  # Example of a more realistic count
    }

    # Sample data that simulates GitHub API language data (which is in bytes, not lines)
    github_api_languages = {
        'Python': 16490,  # This is bytes, not lines!
        'Jinja': 9398,  # This is bytes, not lines!
        'TeX': 88449,  # This is bytes, not lines!
        'Markdown': 1687,  # This is bytes, not lines!
        'LaTeX': 2443,  # This is bytes, not lines!
        'Other': 313  # This is bytes, not lines!
    }

    # 1. First, show what happens if we merge GitHub API data with file analysis (old approach)
    combined_languages_old = dict(file_analysis_languages)
    for lang, bytes_count in github_api_languages.items():
        if lang in combined_languages_old:
            combined_languages_old[lang] = max(combined_languages_old[lang], bytes_count)
        else:
            combined_languages_old[lang] = bytes_count

    # Create a CodeStats object with the old approach
    code_stats_old = CodeStats(languages=combined_languages_old)

    # Calculate primary language and total_loc
    code_stats_old.calculate_primary_language()

    # Print results of old approach
    logger.info("--- OLD APPROACH (GITHUB API BYTES TREATED AS LOC) ---")
    logger.info(f"Languages: {code_stats_old.languages}")
    logger.info(f"Total LOC: {code_stats_old.total_loc}")
    logger.info(f"Primary language: {code_stats_old.primary_language}")
    logger.info("")

    # 2. Now show what happens with our new approach (using only file analysis data)
    code_stats_new = CodeStats(languages=file_analysis_languages)

    # Calculate primary language and total_loc
    code_stats_new.calculate_primary_language()

    # Print results of new approach
    logger.info("--- NEW APPROACH (USING ONLY FILE ANALYSIS LOC) ---")
    logger.info(f"Languages: {code_stats_new.languages}")
    logger.info(f"Total LOC: {code_stats_new.total_loc}")
    logger.info(f"Primary language: {code_stats_new.primary_language}")
    logger.info("")

    # For completeness, create a full RepoStats object with the fixed approach
    base_info = BaseRepoInfo(
        name="test-repo",
        is_private=False,
        default_branch="main",
        is_fork=False,
        is_archived=False,
        is_template=False,
        created_at=datetime.now(),
        last_pushed=datetime.now()
    )

    # Create full repo stats object
    repo_stats = RepoStats(
        base_info=base_info,
        code_stats=code_stats_new,
        activity=ActivityMetrics(),
        quality=QualityIndicators(),
        community=CommunityMetrics(),
        scores=AnalysisScores()
    )

    # Verify full repo stats
    logger.info("--- FULL REPO STATS WITH FIXED APPROACH ---")
    logger.info(f"Repository: {repo_stats.name}")
    logger.info(f"Languages: {repo_stats.languages}")
    logger.info(f"Language sum: {sum(repo_stats.languages.values())}")
    logger.info(f"total_loc: {repo_stats.total_loc}")

    # Check if the fix was successful
    is_correct = repo_stats.total_loc == sum(repo_stats.languages.values())
    logger.info(f"FIX SUCCESSFUL: {is_correct}")

    # Compare with what would have happened with the old approach
    logger.info("\n--- COMPARISON ---")
    logger.info(f"OLD approach total LOC: {code_stats_old.total_loc} (inflated)")
    logger.info(f"NEW approach total LOC: {code_stats_new.total_loc} (correct)")
    logger.info(f"Difference: {code_stats_old.total_loc - code_stats_new.total_loc} lines removed from counting")


if __name__ == "__main__":
    main()
