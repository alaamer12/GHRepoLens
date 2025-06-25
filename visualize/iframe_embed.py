"""
GitHub Repository Iframe Embedding Module

This module enables the embedding of generated HTML chart pages into external websites 
via iframe by hosting them on Vercel. It handles the preparation of files for 
deployment, the deployment process itself, and the verification of the deployment.
"""

import json
import os
import shutil
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import requests
from bs4 import BeautifulSoup
from rich.prompt import Confirm

from console import console, logger, print_info, print_success, print_warning, print_error
from config import Configuration

# List of HTML files to deploy in "partial" mode
PARTIAL_DEPLOY_FILES = {
    "active_inactive_age.html",
    "commit_activity_heatmap.html",
    "documentation_quality.html",
    "infrastructure_metrics.html",
    "quality_heatmap.html",
    "repo_creation_timeline.html",
    "repo_types_distribution.html",
    "repository_timeline.html",
    "stars_vs_issues.html",
    "top_repos_metrics.html"
}

# Additional files to deploy in "full" mode
FULL_DEPLOY_FILES = PARTIAL_DEPLOY_FILES.union({"visual_report.html"})


class IframeEmbedder:
    """Class for handling iframe embedding with Vercel deployment"""

    def __init__(self, config: Configuration):
        """
        Initialize the IframeEmbedder with configuration.
        
        Args:
            config: The configuration dictionary containing iframe embedding settings
        """
        self.config = config
        self.reports_dir = Path(config["REPORTS_DIR"])
        self.iframe_mode = config["IFRAME_EMBEDDING"]
        self.vercel_token = config["VERCEL_TOKEN"]
        self.vercel_project_name = config["VERCEL_PROJECT_NAME"]
        self.deployment_url = ""

    def validate_config(self) -> bool:
        """
        Validate that the configuration has all required fields for iframe embedding.
        
        Returns:
            bool: True if valid, False otherwise
        """
        if self.iframe_mode == "disabled":
            return True

        # Check required fields
        if not self.vercel_token:
            print_error("Vercel token is required for iframe embedding")
            logger.error("Missing Vercel token for iframe embedding")
            return False

        if not self.vercel_project_name:
            print_error("Vercel project name is required for iframe embedding")
            logger.error("Missing Vercel project name for iframe embedding")
            return False

        # Check if the reports directory exists
        if not self.reports_dir.exists():
            print_error(f"Reports directory '{self.reports_dir}' does not exist")
            logger.error(f"Reports directory '{self.reports_dir}' does not exist")
            return False

        # Check if required HTML files exist
        files_to_check = PARTIAL_DEPLOY_FILES if self.iframe_mode == "partial" else FULL_DEPLOY_FILES
        missing_files = [f for f in files_to_check if not (self.reports_dir / f).exists()]

        if missing_files:
            print_error(f"Missing required HTML files for deployment: {', '.join(missing_files)}")
            logger.error(f"Missing required HTML files for deployment: {', '.join(missing_files)}")
            return False

        return True

    def deploy_charts(self) -> bool:
        """
        Deploy HTML chart files to Vercel for iframe embedding.
        
        Returns:
            bool: True if deployment was successful, False otherwise
        """
        if self.iframe_mode == "disabled":
            logger.info("Iframe embedding is disabled, skipping deployment")
            return False

        if not self.validate_config():
            return False

        print_info(f"Preparing for {self.iframe_mode} iframe embedding deployment...")

        # Create a temporary directory for deployment
        with ExitStack() as stack:
            # Create temporary directory that will be automatically cleaned up
            temp_dir = stack.enter_context(tempfile.TemporaryDirectory())
            temp_path = Path(temp_dir)

            try:
                # Copy files based on the selected mode
                files_to_deploy = self._prepare_deployment_files(temp_path)

                if not files_to_deploy:
                    print_error("No files to deploy")
                    return False

                # Create Vercel configuration files
                self._create_vercel_config(temp_path)

                # Deploy to Vercel
                success, self.deployment_url = self._deploy_to_vercel(temp_path)

                if not success:
                    print_error("Deployment to Vercel failed")
                    return False

                # Verify deployment
                if not self._verify_deployment(files_to_deploy):
                    print_warning("Deployment verification failed")
                    # We still return True since the deployment might be working

                # Patch the visual_report.html with iframes if in full mode
                if self.iframe_mode == "full" and success:
                    self._patch_visual_report_with_iframes()

                return success

            except Exception as e:
                logger.exception(f"Error during deployment: {str(e)}")
                print_error(f"Error during deployment: {str(e)}")
                return False

    def _prepare_deployment_files(self, temp_path: Path) -> List[str]:
        """
        Copy the necessary HTML files to the temporary deployment directory.
        
        Args:
            temp_path: Path to temporary directory for deployment
            
        Returns:
            List[str]: List of deployed file names
        """
        # Determine which files to deploy based on mode
        files_to_deploy = PARTIAL_DEPLOY_FILES if self.iframe_mode == "partial" else FULL_DEPLOY_FILES
        deployed_files = []

        # Copy the static assets directory if it exists
        static_source = self.reports_dir / "static"
        static_dest = temp_path / "static"

        if static_source.exists():
            shutil.copytree(static_source, static_dest)
            logger.info(f"Copied static assets from {static_source} to {static_dest}")

        # Copy HTML files
        for filename in files_to_deploy:
            source_file = self.reports_dir / filename
            if source_file.exists():
                dest_file = temp_path / filename
                shutil.copy2(source_file, dest_file)
                deployed_files.append(filename)
                logger.info(f"Copied {filename} for deployment")
            else:
                logger.warning(f"File {filename} not found, skipping")

        # Create index.html if visual_report.html is present
        if "visual_report.html" in deployed_files:
            shutil.copy2(temp_path / "visual_report.html", temp_path / "index.html")
            logger.info("Created index.html from visual_report.html")
        elif deployed_files:
            # Otherwise use the first HTML file as index
            first_file = deployed_files[0]
            shutil.copy2(temp_path / first_file, temp_path / "index.html")
            logger.info(f"Created index.html from {first_file}")

        print_info(f"Prepared {len(deployed_files)} files for deployment")
        return deployed_files

    def _create_vercel_config(self, temp_path: Path) -> None:
        """
        Create the necessary Vercel configuration files.
        
        Args:
            temp_path: Path to temporary directory for deployment
        """
        # Create vercel.json for configuration
        vercel_config = {
            "name": self.vercel_project_name,
            "version": 2,
            "builds": [
                {"src": "**/*.html", "use": "@vercel/static"},
                {"src": "static/**", "use": "@vercel/static"}
            ],
            "routes": [
                {"src": "/(.*)", "dest": "/$1"}
            ]
        }

        with open(temp_path / "vercel.json", "w") as f:
            json.dump(vercel_config, f, indent=2)

        # Create .vercel directory and project.json
        vercel_dir = temp_path / ".vercel"
        vercel_dir.mkdir(exist_ok=True)

        project_config = {
            "projectId": "",  # Will be assigned by Vercel
            "orgId": "",  # Will be assigned by Vercel
            "settings": {
                "framework": None,
                "createBuilds": True
            }
        }

        with open(vercel_dir / "project.json", "w") as f:
            json.dump(project_config, f, indent=2)

        logger.info("Created Vercel configuration files")

    def _deploy_to_vercel(self, temp_path: Path) -> Tuple[bool, str]:
        """
        Deploy the project to Vercel.
        
        Args:
            temp_path: Path to temporary directory with files to deploy
            
        Returns:
            Tuple[bool, str]: Success flag and deployment URL
        """
        print_info("Deploying to Vercel...")

        # Check if vercel CLI is available
        if os.system("vercel --version > nul 2>&1" if os.name == 'nt' else "vercel --version &>/dev/null") != 0:
            # Use API approach if CLI is not available
            return self._deploy_to_vercel_api(temp_path)

        # Deploy using CLI
        env = os.environ.copy()
        env["VERCEL_TOKEN"] = self.vercel_token

        # Construct the command
        cmd = f'vercel --token {self.vercel_token} --name {self.vercel_project_name} --prod --confirm --yes'

        # Run the command from the temp directory
        current_dir = os.getcwd()
        try:
            os.chdir(temp_path)
            return_code = os.system(cmd)

            if return_code != 0:
                logger.error(f"Vercel CLI deployment failed with code {return_code}")
                print_error("Vercel deployment failed. Check logs for details.")
                return False, ""

            # Get the deployment URL
            url_cmd = f'vercel --token {self.vercel_token} ls {self.vercel_project_name} -j --limit 1'
            import subprocess
            try:
                result = subprocess.run(url_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    deployments = json.loads(result.stdout)
                    if deployments and len(deployments) > 0:
                        url = deployments[0].get("url", "")
                        if url:
                            url = f"https://{url}"
                            print_success(f"Deployment successful! URL: {url}")
                            return True, url
            except Exception as e:
                logger.error(f"Error getting deployment URL: {str(e)}")

            # Fallback: construct URL based on project name
            url = f"https://{self.vercel_project_name}.vercel.app"
            print_success(f"Deployment successful! URL (estimated): {url}")
            return True, url

        finally:
            os.chdir(current_dir)

    @staticmethod
    def _deploy_to_vercel_api(temp_path: Path) -> Tuple[bool, str]:
        """
        Deploy to Vercel using the API instead of the CLI.
        
        Args:
            temp_path: Path to temporary directory with files to deploy
            
        Returns:
            Tuple[bool, str]: Success flag and deployment URL
        """
        # This is a placeholder for API-based deployment
        # Implementing a full Vercel API client is beyond the scope
        # In a real implementation, this would use the Vercel API to deploy

        print_warning("Vercel CLI not found. API-based deployment not implemented.")
        print_warning("Please install Vercel CLI: npm install -g vercel")
        logger.warning("Vercel CLI not found and API deployment not implemented")
        return False, ""

    def _verify_deployment(self, deployed_files: List[str]) -> bool:
        """
        Verify that the deployment is accessible and HTML files are properly served.
        
        Args:
            deployed_files: List of files that were deployed
            
        Returns:
            bool: True if verification passes, False otherwise
        """
        if not self.deployment_url:
            logger.error("No deployment URL available for verification")
            return False

        print_info("Verifying deployment accessibility...")

        # Wait a moment for the deployment to propagate
        time.sleep(3)

        # Check main URL
        try:
            response = requests.get(self.deployment_url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Main URL returned status code {response.status_code}")
                print_warning(f"Deployment verification: Main URL returned status code {response.status_code}")
            else:
                print_success("Main URL is accessible")
        except Exception as e:
            logger.error(f"Error accessing main URL: {str(e)}")
            print_warning(f"Could not access main URL: {str(e)}")
            return False

        # Check a few sample files
        success_count = 0
        files_to_check = min(3, len(deployed_files))
        files_sample = deployed_files[:files_to_check]

        for file in files_sample:
            file_url = f"{self.deployment_url}/{file}"
            try:
                response = requests.get(file_url, timeout=10)
                if response.status_code == 200:
                    success_count += 1

                    # Verify it looks like valid HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    if soup.title and soup.find('div'):
                        logger.info(f"Successfully verified {file_url}")
                    else:
                        logger.warning(f"File {file} returned 200 but may not be valid HTML")
                else:
                    logger.warning(f"File {file} returned status code {response.status_code}")
            except Exception as e:
                logger.error(f"Error accessing {file}: {str(e)}")

        if success_count == files_to_check:
            print_success(f"Successfully verified all {files_to_check} sample files")
            return True
        else:
            print_warning(f"Verified {success_count}/{files_to_check} sample files")
            return False

    def _patch_visual_report_html(self, deployed_files: Set[str]) -> bool:
        """
        Patch the visual_report.html file with iframes pointing to the deployed files.
        
        Args:
            deployed_files: Set of file names that were deployed
            
        Returns:
            bool: True if patching was successful, False otherwise
        """
        if self.iframe_mode != "full" or not self.deployment_url:
            return False

        visual_report_path = self.reports_dir / "visual_report.html"
        if not visual_report_path.exists():
            logger.error("visual_report.html not found for patching")
            return False

        try:
            # Read the content of the file
            with open(visual_report_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')

            # Find references to local chart files and replace with iframes
            modified = False
            for link in soup.find_all('a', href=True):
                href = link['href']

                # Check if this is a link to a deployed file
                file_name = Path(href).name
                if file_name in deployed_files and file_name != "visual_report.html":
                    iframe_url = f"{self.deployment_url}/{file_name}"

                    # Create iframe element
                    iframe = soup.new_tag("iframe")
                    iframe['src'] = iframe_url
                    iframe['width'] = "100%"
                    iframe['height'] = "500px"
                    iframe['frameborder'] = "0"
                    iframe['title'] = f"Embedded {file_name}"

                    # Replace the link with the iframe
                    if link.parent:
                        link.parent.append(iframe)
                        link.decompose()
                        modified = True

            if modified:
                # Backup the original file
                backup_path = visual_report_path.with_suffix('.html.backup')
                shutil.copy2(visual_report_path, backup_path)
                logger.info(f"Created backup of visual_report.html at {backup_path}")

                # Write the modified content
                with open(visual_report_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))

                logger.info("Updated visual_report.html with iframe embeds")
                print_success("Updated visual_report.html with iframe embeds")
                return True
            else:
                logger.info("No changes needed in visual_report.html")
                return False

        except Exception as e:
            logger.exception(f"Error patching visual_report.html: {str(e)}")
            print_error(f"Error patching visual_report.html: {str(e)}")
            return False

    def _patch_visual_report_with_iframes(self) -> None:
        """
        Ask user if they want to patch visual_report.html with iframes and do it if confirmed.
        """
        if self.iframe_mode != "full" or not self.deployment_url:
            return

        # Ask user if they want to patch visual_report.html
        if Confirm.ask(
                "Would you like to replace local paths in visual_report.html with deployed iframe URLs?",
                default=False
        ):
            deployed_files = FULL_DEPLOY_FILES
            result = self._patch_visual_report_html(deployed_files)
            if result:
                print_success("visual_report.html has been updated with iframe embeds")
            else:
                print_warning("visual_report.html could not be updated with iframe embeds")


def validate_and_deploy_charts(config: Configuration) -> bool:
    """
    Validate iframe configuration and deploy charts if enabled.
    
    Args:
        config: The configuration dictionary containing iframe embedding settings
        
    Returns:
        bool: True if deployment was successful or not needed, False if it failed
    """
    iframe_mode = config.get("IFRAME_EMBEDDING", "disabled")

    if iframe_mode == "disabled":
        return True

    embedder = IframeEmbedder(config)
    return embedder.deploy_charts()
