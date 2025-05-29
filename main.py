from pathlib import Path
from venv import logger
from typing import Optional

from config import DEFAULT_CONFIG, Configuration
from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from tqdm.auto import tqdm
from collections import Counter
import re
import os

from reports import GithubLens
from config import create_sample_config, load_config_from_file


def run_demo(token: str, username: str, config: Optional[Configuration] = None) -> None:
    """Run a demonstration analysis on only 10 repositories for quick testing"""
    logger.info("🔮 Starting GitHub Repository Analyzer in DEMO mode (10 repos max)")
    
    # Create configuration with default settings
    demo_config: Configuration = DEFAULT_CONFIG.copy()
    demo_config["GITHUB_TOKEN"] = token
    demo_config["USERNAME"] = username
    # Set demo-specific checkpoint file to avoid mixing with full analysis
    demo_config["CHECKPOINT_FILE"] = "github_analyzer_demo_checkpoint.pkl"
    
    # Use provided config if available
    if config:
        demo_config.update(config)
    
    try:
        # Initialize analyzer
        analyzer = GithubLens(demo_config["GITHUB_TOKEN"], demo_config["USERNAME"], demo_config)
        
        # Check for existing checkpoint
        checkpoint_exists = Path(demo_config["CHECKPOINT_FILE"]).exists()
        if checkpoint_exists and demo_config["RESUME_FROM_CHECKPOINT"]:
            print(f"\n📋 Found existing demo checkpoint file")
            print(f"🔄 Will resume demo analysis from checkpoint")
            print(f"🔍 Using checkpoint threshold: {demo_config['CHECKPOINT_THRESHOLD']}")
        
        # Get repositories but limit to 10
        try:
            github = Github(token)
            user = github.get_user(username)
            all_repos = list(user.get_repos())[:10]  # Strictly limit to 10 repos here
        except GithubException as e:
            if e.status == 403:
                error_msg = f"Access forbidden (403). Check your token permissions: {e.data.get('message', '')}"
                logger.error(error_msg)
                
                # Check if the message contains backoff information
                message = str(e)
                backoff_match = re.search(r"Setting next backoff to (\d+\.\d+)s", message)
                if backoff_match:
                    wait_time = float(backoff_match.group(1))
                    print(f"⚠️ GitHub API requires a cooldown period ({wait_time/60:.1f} minutes)")
                    print(f"Do you want to wait for the cooldown? (y/n)")
                    response = input("> ").strip().lower()
                    if response == 'y':
                        analyzer._visualize_wait(wait_time, "GitHub API backoff")
                        # Try again after wait
                        github = Github(token)
                        user = github.get_user(username)
                        all_repos = list(user.get_repos())[:10]  # Limit to 10 repos
                    else:
                        print("Analysis canceled.")
                        return
                else:
                    print("Cannot proceed with analysis due to access restrictions.")
                    return
            else:
                logger.error(f"GitHub API error: {e}")
                print(f"GitHub API error: {e}")
                return
                
        # Override analyze_all_repositories method for demo mode
        # This ensures we don't process more than 10 repositories
        demo_stats = []
        
        print("\n🔬 Running demo analysis on up to 10 repositories...")
        print(f"🔍 Using checkpoint threshold: {demo_config['CHECKPOINT_THRESHOLD']} remaining requests")
        
        # Display initial rate status
        print("\n--- Initial API Rate Status ---")
        analyzer.rate_display.display_once()
        print("-------------------------------")
        
        with tqdm(total=min(10, len(all_repos)), desc="Analyzing repositories", leave=True, colour='green') as pbar:
            for repo in all_repos[:10]:  # Ensure we stay within 10 repos
                try:
                    stats = analyzer.analyze_single_repository(repo)
                    demo_stats.append(stats)
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"Failed to analyze {repo.name}: {e}")
                    continue
                    
                # Check rate limit after each repository
                if analyzer.check_rate_limit_and_checkpoint(demo_stats, [s.name for s in demo_stats], []):
                    logger.warning("Pausing demo analysis due to approaching API rate limit")
                    print("\n⚠️ Pausing demo analysis - approaching API rate limit")
                    break

        if not demo_stats:
            logger.error("❌ No repositories analyzed in demo mode")
            return
        
        # Generate reports with demo indicator
        with tqdm(total=4, desc="Generating demo reports", colour='blue') as pbar:
            # 1. Detailed report
            analyzer.generate_detailed_report(demo_stats)
            pbar.update(1)
            
            # 2. Aggregated report
            analyzer.generate_aggregated_report(demo_stats)
            pbar.update(1)
            
            # 3. Visual report
            analyzer.create_visualizations(demo_stats)
            pbar.update(1)
            
            # 4. JSON report
            analyzer.save_json_report(demo_stats)
            pbar.update(1)
        
        # Summary
        print(f"\n🎉 Demo Analysis Complete!")
        print(f"📊 Analyzed {len(demo_stats)} repositories (demo mode)")
        print(f"📁 Reports saved to: {analyzer.reports_dir.absolute()}")
        print(f"📄 Files generated:")
        print(f"   • repo_details.md - Detailed per-repository analysis")
        print(f"   • aggregated_stats.md - Summary statistics")
        print(f"   • visual_report.html - Interactive dashboard")
        print(f"   • repository_data.json - Raw data for programmatic use")
        print(f"   • *.png - Individual charts and visualizations")
        
        # Print API usage stats
        print(f"\n📊 GitHub API Usage:")
        print(f"   • Total API requests used: {analyzer.api_requests_made}")
        
        print(f"\n⚠️ NOTE: This is a DEMO analysis limited to 10 repositories. Run without demo mode for full analysis.")
        
    except RateLimitExceededException:
        logger.error("❌ GitHub API rate limit exceeded during demo. Please try again later.")
        print("\n⏰ GitHub API rate limit exceeded. Run the demo again later to resume from checkpoint.")
    except GithubException as e:
        logger.error(f"❌ GitHub API error during demo: {e}")
        print(f"\n❌ GitHub API error during demo: {e}")
        print(f"💾 Your demo progress has been saved to checkpoint - run again later to resume")
    except Exception as e:
        logger.error(f"❌ Error during demo analysis: {e}")
        print(f"\n❌ Error during demo analysis: {e}")
        print(f"💾 Your demo progress has been saved to checkpoint - run again later to resume")
        raise

def main(demo_mode=False):
    """Main function to run the GitHub repository analyzer"""
    logger.info("🔮 Starting GitHub Repository Analyzer")
    
    # Create sample config if needed
    create_sample_config()
    
    # Configuration - Edit these values directly
    # GitHub API token with repo access permissions
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    
    # GitHub username to analyze
    USERNAME = "alaamer12"
    
    # Output directories
    REPORTS_DIR = "reports"
    CLONE_DIR = "temp_repos"
    
    # Analysis settings
    MAX_WORKERS = 4               # Number of parallel workers (1 for sequential processing)
    SKIP_FORKS = False            # Whether to skip analyzing forked repositories
    SKIP_ARCHIVED = False         # Whether to skip analyzing archived repositories
    INCLUDE_PRIVATE = True        # Whether to include private repositories in analysis
    ANALYZE_CLONES = False        # Whether to clone repositories for deeper analysis
    
    # Checkpoint settings
    ENABLE_CHECKPOINTING = True   # Whether to enable checkpoint feature
    CHECKPOINT_FILE = "github_analyzer_checkpoint.pkl"  # Checkpoint file location
    CHECKPOINT_THRESHOLD = 4280   # Updated: Create checkpoint when remaining API requests falls below this
    RESUME_FROM_CHECKPOINT = True # Whether to resume from checkpoint if it exists
    
    # Try to load from config file (will be overridden by the variables above)
    config_file = 'config.ini'
    if os.path.exists(config_file):
        logger.info(f"Loading configuration from {config_file}")
        file_config = load_config_from_file(config_file)
        
        # Only use file config if the script variables are not set
        if GITHUB_TOKEN == "your_github_token_here":
            GITHUB_TOKEN = file_config["GITHUB_TOKEN"]
        if USERNAME == "your_username_here":
            USERNAME = file_config["USERNAME"]
    
    # Validate configuration
    if GITHUB_TOKEN == "your_github_token_here" or USERNAME == "your_username_here":
        logger.error("❌ Please update GITHUB_TOKEN and USERNAME in the main function")
        print("\n🔧 Configuration Required:")
        print("1. Create a GitHub personal access token at https://github.com/settings/tokens")
        print("2. Specify your GitHub username")
        print("3. Edit the variables at the top of the main() function")
        return
    
    # If demo mode is requested, run the demo function instead
    if demo_mode:
        # Create demo config with proper threshold
        demo_config: Configuration = DEFAULT_CONFIG.copy()
        demo_config["GITHUB_TOKEN"] = GITHUB_TOKEN
        demo_config["USERNAME"] = USERNAME
        demo_config["CHECKPOINT_THRESHOLD"] = CHECKPOINT_THRESHOLD
        demo_config["REPORTS_DIR"] = REPORTS_DIR
        demo_config["CLONE_DIR"] = CLONE_DIR
        demo_config["MAX_WORKERS"] = MAX_WORKERS
        demo_config["ENABLE_CHECKPOINTING"] = ENABLE_CHECKPOINTING
        demo_config["RESUME_FROM_CHECKPOINT"] = RESUME_FROM_CHECKPOINT
        
        # Pass the config to the demo function
        print(f"🔍 Starting demo with checkpoint threshold: {CHECKPOINT_THRESHOLD}")
        run_demo(GITHUB_TOKEN, USERNAME, demo_config)
        return
    
    # Create the final configuration dictionary
    config: Configuration = {
        "GITHUB_TOKEN": GITHUB_TOKEN,
        "USERNAME": USERNAME,
        "REPORTS_DIR": REPORTS_DIR,
        "CLONE_DIR": CLONE_DIR,
        "MAX_WORKERS": MAX_WORKERS,
        "INACTIVE_THRESHOLD_DAYS": 180,  # Days after which a repo is considered inactive
        "LARGE_REPO_LOC_THRESHOLD": 1000,  # LOC threshold for "large" repositories
        "SKIP_FORKS": SKIP_FORKS,
        "SKIP_ARCHIVED": SKIP_ARCHIVED,
        "INCLUDE_PRIVATE": INCLUDE_PRIVATE,
        "ANALYZE_CLONES": ANALYZE_CLONES,
        "ENABLE_CHECKPOINTING": ENABLE_CHECKPOINTING,
        "CHECKPOINT_FILE": CHECKPOINT_FILE,
        "CHECKPOINT_THRESHOLD": CHECKPOINT_THRESHOLD,
        "RESUME_FROM_CHECKPOINT": RESUME_FROM_CHECKPOINT
    }
    
    try:
        # Initialize analyzer
        analyzer = GithubLens(config['GITHUB_TOKEN'], config['USERNAME'], config)
        
        # Check for checkpoint
        checkpoint_exists = Path(CHECKPOINT_FILE).exists()
        if checkpoint_exists and RESUME_FROM_CHECKPOINT:
            print(f"\n📋 Found existing checkpoint file at {CHECKPOINT_FILE}")
            if RESUME_FROM_CHECKPOINT:
                print(f"🔄 Will resume analysis from checkpoint")
            else:
                print(f"⚠️ Resume from checkpoint is disabled - starting fresh analysis")
        
        # Analyze all repositories
        logger.info("📊 Starting repository analysis...")
        all_stats = analyzer.analyze_all_repositories()
        
        if not all_stats:
            logger.error("❌ No repositories found or analyzed")
            return
        
        logger.info(f"✅ Successfully analyzed {len(all_stats)} repositories")
        
        # Generate reports
        print("\n📝 Generating reports...")
        
        with tqdm(total=4, desc="Generating reports", colour='blue') as pbar:
            # 1. Detailed report
            analyzer.generate_detailed_report(all_stats)
            pbar.update(1)
            
            # 2. Aggregated report
            analyzer.generate_aggregated_report(all_stats)
            pbar.update(1)
            
            # 3. Visual report
            analyzer.create_visualizations(all_stats)
            pbar.update(1)
            
            # 4. JSON report
            analyzer.save_json_report(all_stats)
            pbar.update(1)
        
        # Summary
        print(f"\n🎉 Analysis Complete!")
        print(f"📊 Analyzed {len(all_stats)} repositories")
        print(f"📁 Reports saved to: {analyzer.reports_dir.absolute()}")
        print(f"📄 Files generated:")
        print(f"   • repo_details.md - Detailed per-repository analysis")
        print(f"   • aggregated_stats.md - Summary statistics")
        print(f"   • visual_report.html - Interactive dashboard")
        print(f"   • repository_data.json - Raw data for programmatic use")
        print(f"   • *.png - Individual charts and visualizations")
        
        # Print API usage stats
        print(f"\n📊 GitHub API Usage:")
        print(f"   • Total API requests used: {analyzer.api_requests_made}")
        
        # Check if checkpoint file still exists
        if checkpoint_exists and Path(CHECKPOINT_FILE).exists():
            print(f"✅ Analysis completed successfully - checkpoint file is kept for reference")
            print(f"   You can delete it manually or disable checkpointing in config")
        
        # Print some quick stats
        total_loc = sum(s.total_loc for s in all_stats)
        total_stars = sum(s.stars for s in all_stats)
        active_repos = sum(1 for s in all_stats if s.is_active)
        
        print(f"\n📈 Quick Stats:")
        print(f"   • Total Lines of Code: {total_loc:,}")
        print(f"   • Total Stars: {total_stars:,}")
        print(f"   • Active Repositories: {active_repos}/{len(all_stats)}")
        print(f"   • Average Maintenance Score: {sum(s.maintenance_score for s in all_stats)/len(all_stats):.1f}/100")
        
        # Anomaly summary
        all_anomalies = [a for s in all_stats for a in s.anomalies]
        if all_anomalies:
            print(f"\n🚨 Detected {len(all_anomalies)} potential issues across repositories")
            anomaly_counts = Counter(all_anomalies)
            for anomaly, count in anomaly_counts.most_common(5):
                print(f"   • {anomaly}: {count} repos")
        
        logger.info("🎉 GitHub Repository Analyzer completed successfully")
        
    except RateLimitExceededException:
        logger.error("❌ GitHub API rate limit exceeded. Please try again later.")
        print("\n⏰ GitHub API rate limit exceeded. Options:")
        print("1. Wait for the rate limit to reset (usually 1 hour)")
        print("2. Use a different GitHub token")
        print("3. Run again later to resume from checkpoint")
        
    except GithubException as e:
        logger.error(f"❌ GitHub API error: {e}")
        print(f"\n❌ GitHub API error: {e}")
        print(f"💾 Your progress has been saved to checkpoint - run again later to resume")
        
    except Exception as e:
        logger.error(f"❌ Error during analysis: {e}")
        print(f"\n❌ Error during analysis: {e}")
        print(f"💾 Your progress has been saved to checkpoint - run again later to resume")
        raise

if __name__ == "__main__":
    # To run in demo mode, uncomment the next line:
    main(demo_mode=True)
    
    # For full analysis:
    # main()