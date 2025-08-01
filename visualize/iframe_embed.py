"""
GitHub Repository Iframe Embedding Module

This module enables the embedding of generated HTML chart pages into external websites 
via iframe by hosting them on Vercel. It handles the preparation of files for 
deployment, the deployment process itself, and the verification of the deployment.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from typing import List, Optional, Tuple, Set
import requests
from bs4 import BeautifulSoup
from rich.prompt import Confirm

from console import logger, print_info, print_success, print_warning, print_error
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


class VercelDeployer:
    """Handles Vercel deployment operations"""

    def __init__(self, vercel_token: str, project_name: str):
        self.vercel_token = vercel_token
        self.project_name = project_name
        self.project_id = ""

    def deploy(self, temp_path: Path) -> Tuple[bool, str]:
        """
        Deploy the project to Vercel.

        Args:
            temp_path: Path to temporary directory with files to deploy

        Returns:
            Tuple[bool, str]: Success flag and deployment URL
        """
        print_info("Deploying to Vercel...")

        # Check if vercel CLI is available
        if not self._is_vercel_cli_available():
            print_warning("Vercel CLI not found, attempting API deployment...")
            return self._deploy_to_vercel_api()

        # Deploy using CLI
        env = self._prepare_environment()
        # First, try to create the project if it doesn't exist
        self._attempt_project_creation(env)

        # Run the deployment
        success, url = self._run_deployment(temp_path, env)

        if success:
            # Try to get the project ID
            self._get_project_id(env)

        return success, url

    @staticmethod
    def _is_vercel_cli_available() -> bool:
        """Check if Vercel CLI is available"""
        try:
            with open(os.devnull, 'w') as devnull:
                return subprocess.run(
                    ["vercel", "--version"],
                    stdout=devnull,
                    stderr=devnull
                ).returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _prepare_environment(self) -> dict:
        """Prepare environment variables for Vercel CLI"""
        env = os.environ.copy()
        env["VERCEL_TOKEN"] = self.vercel_token
        return env

    def _attempt_project_creation(self, env: dict) -> None:
        """Attempt to create the Vercel project"""
        # Validate project name to prevent injection
        if not self._is_valid_project_name(self.project_name):
            logger.warning(f"Invalid project name: {self.project_name}")
            return

        create_cmd = ["vercel", "project", "add", self.project_name, "--yes"]
        try:
            create_process = subprocess.run(
                create_cmd,
                env=env,
                capture_output=True,
                text=True
            )
            if create_process.returncode == 0:
                logger.info(f"Successfully created project: {self.project_name}")
                print_info(f"Created project: {self.project_name}")
            else:
                logger.info(f"Project creation output: {create_process.stderr}")
        except Exception as e:
            logger.warning(f"Project creation attempt failed: {str(e)}")

    def _run_deployment(self, temp_path: Path, env: dict) -> Tuple[bool, str]:
        """Run the actual deployment process"""
        cmd = ["vercel", "--prod", "--yes"]

        logger.info(f"Running Vercel deployment command: {' '.join(cmd)}")
        print_info(f"Deploying to project: {self.project_name}")

        current_dir = os.getcwd()
        try:
            os.chdir(temp_path)

            # Try primary deployment
            process = self._execute_deployment_command(cmd, env)

            if process.returncode != 0:
                logger.warning(f"First deployment attempt failed with code {process.returncode}")
                logger.warning(f"Error output: {process.stderr}")

                # Try alternative methods
                process = self._try_alternative_deployment_methods(temp_path, cmd, env)

            if process.returncode != 0:
                logger.error(f"Vercel CLI deployment failed with code {process.returncode}")
                logger.error(f"Error output: {process.stderr}")
                print_error(f"Vercel deployment failed: {process.stderr[:100]}...")
                return False, ""
            else:
                logger.info(f"Vercel deployment output: {process.stdout[:200]}...")

            # Get deployment URL
            url = self._get_deployment_url(env)
            return True, url
        finally:
            os.chdir(current_dir)

    @staticmethod
    def _execute_deployment_command(cmd: list, env: dict):
        """Execute a deployment command"""
        return subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )

    def _try_alternative_deployment_methods(self, temp_path: Path, cmd: list, env: dict):
        """Try alternative deployment methods if primary fails"""

        # Method 1: Update project.json and retry
        print_info("Trying alternative deployment method...")
        logger.info("Trying alternative deployment method")

        self._update_project_json(temp_path)
        process = self._execute_deployment_command(cmd, env)

        if process.returncode != 0:
            # Method 2: Deploy-then-link approach
            process = self._try_deploy_then_link(env)

            if process.returncode != 0:
                # Method 3: Create-project-first approach
                process = self._try_create_project_first(cmd, env)

        return process

    def _update_project_json(self, temp_path: Path) -> None:
        """Update project.json with correct project name"""
        vercel_dir = temp_path / ".vercel"
        if vercel_dir.exists():
            project_json_path = vercel_dir / "project.json"
            if project_json_path.exists():
                try:
                    with open(project_json_path, 'r') as f:
                        project_data = json.load(f)

                    if 'settings' not in project_data:
                        project_data['settings'] = {}
                    project_data['settings']['projectName'] = self.project_name

                    with open(project_json_path, 'w') as f:
                        json.dump(project_data, f, indent=2)

                    logger.info(f"Updated project name in project.json: {self.project_name}")
                except Exception as e:
                    logger.error(f"Error updating project.json: {str(e)}")

    def _try_deploy_then_link(self, env: dict):
        """Try deploy-then-link approach"""

        logger.warning("Second deployment attempt failed, trying deploy-then-link approach")
        print_info("Trying deploy-then-link approach...")

        # First, just deploy without specifying project name
        deploy_cmd = ["vercel", "--prod", "--yes"]
        deploy_process = subprocess.run(
            deploy_cmd,
            env=env,
            capture_output=True,
            text=True
        )

        if deploy_process.returncode == 0:
            # Now try to link to the project
            link_cmd = ["vercel", "link", "--yes"]
            link_process = subprocess.run(
                link_cmd,
                env=env,
                capture_output=True,
                text=True,
                input=f"{self.project_name}\n"
            )

            if link_process.returncode == 0:
                logger.info("Deploy-then-link approach succeeded")
                return deploy_process
            else:
                logger.error(f"Project linking failed: {link_process.stderr}")
                print_error("Failed to link project after deployment")

        return deploy_process

    def _try_create_project_first(self, cmd: list, env: dict):
        """Try create-project-first approach"""

        logger.warning("Trying create-project-first approach")
        print_info("Trying to create project first...")

        # Validate project name
        if not self._is_valid_project_name(self.project_name):
            logger.error(f"Invalid project name: {self.project_name}")
            return subprocess.run(cmd, env=env, capture_output=True, text=True)

        # Create project
        create_cmd = ["vercel", "project", "add", self.project_name, "--yes"]
        create_process = subprocess.run(
            create_cmd,
            env=env,
            capture_output=True,
            text=True
        )

        if create_process.returncode == 0:
            # Now deploy to the created project
            final_deploy_cmd = ["vercel", "--prod", "--yes"]
            final_process = subprocess.run(
                final_deploy_cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if final_process.returncode == 0:
                logger.info("Create-project-first approach succeeded")
                return final_process

        # Return the last attempt result
        return subprocess.run(cmd, env=env, capture_output=True, text=True)

    def _get_deployment_url(self, env: dict) -> str:
        """Get the deployment URL from Vercel"""

        # Try to get URL from Vercel CLI
        url = self._fetch_url_from_vercel_cli(env)
        if url:
            print_success(f"Deployment successful! URL: {url}")
            return url

        # Fallback to constructed URL
        return self._get_fallback_url()

    def _fetch_url_from_vercel_cli(self, env: dict) -> str:
        """Fetch deployment URL from Vercel CLI"""
        url_cmd = ["vercel", "ls", "--json", "--limit", "1"]

        try:
            result = subprocess.run(url_cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                return self._parse_deployment_url(result.stdout)
        except Exception as e:
            logger.error(f"Error getting deployment URL: {str(e)}")

        return ""

    def _parse_deployment_url(self, json_output: str) -> str:
        """Parse deployment URL from JSON output"""
        try:
            deployments = json.loads(json_output)
            if not deployments:
                return ""

            url = self._extract_url_from_deployments(deployments)
            return f"https://{url}" if url else ""

        except Exception as e:
            logger.warning(f"Error parsing deployment list: {str(e)}")
            return ""

    @staticmethod
    def _extract_url_from_deployments(deployments) -> str:
        """Extract URL from deployments data structure"""
        # Handle array format
        if isinstance(deployments, list) and len(deployments) > 0:
            return deployments[0].get("url", "")

        # Handle object format with deployments property
        if isinstance(deployments, dict) and "deployments" in deployments:
            deployment_list = deployments.get("deployments", [])
            if deployment_list and len(deployment_list) > 0:
                return deployment_list[0].get("url", "")
        return ""

    def _get_fallback_url(self) -> str:
        """Get fallback URL based on project name"""
        url = f"https://{self.project_name}.vercel.app"
        print_success(f"Deployment successful! URL (estimated): {url}")
        return url

    def _get_project_id(self, env: dict) -> None:
        """Get the project ID from Vercel"""

        if self.project_id:
            return

        project_cmd = ["vercel", "project", "ls", "--json"]
        try:
            proj_result = subprocess.run(project_cmd, env=env, capture_output=True, text=True)
            if proj_result.returncode == 0:
                try:
                    projects = json.loads(proj_result.stdout)
                    # Handle both array format (v2 API) and object with projects property (v9 API)
                    project_list = projects if isinstance(projects, list) else projects.get("projects", [])
                    for project in project_list:
                        if project.get("name") == self.project_name:
                            self.project_id = project.get("id", "")
                            logger.info(f"Found project ID: {self.project_id}")
                            break
                except Exception as e:
                    logger.warning(f"Error parsing project list: {str(e)}")
        except Exception as e:
            logger.warning(f"Error getting project ID: {str(e)}")

    @staticmethod
    def _is_valid_project_name(project_name: str) -> bool:
        """Validate project name to prevent command injection"""
        if not project_name:
            return False
        # Allow alphanumeric, hyphens, underscores, and dots
        # This matches Vercel's project name requirements
        import re
        return bool(re.match(r'^[a-zA-Z0-9._-]+$', project_name)) and len(project_name) <= 100

    @staticmethod
    def _deploy_to_vercel_api() -> Tuple[bool, str]:
        """
        Deploy to Vercel using the API instead of the CLI.

        Returns:
            Tuple[bool, str]: Success flag and deployment URL
        """
        # This is a placeholder for API-based deployment
        # Implementing a full Vercel API client is beyond the scope
        # In a real implementation, this would use the Vercel API to deploy

        print_warning("Vercel CLI not found. API-based deployment not implemented.")
        print_warning("Please install Vercel CLI: npm install -g vercel")
        print_info("You can also try running 'npx vercel' which doesn't require installation")
        logger.warning("Vercel CLI not found and API deployment not implemented")
        return False, ""


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
        self.project_id = ""  # Store project ID for potential deletion

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

        # Validate token format
        if not self._validate_vercel_token():
            return False

        if not self.vercel_project_name:
            print_error("Vercel project name is required for iframe embedding")
            logger.error("Missing Vercel project name for iframe embedding")
            return False

        # Check if project already exists
        project_exists = self._check_project_exists()
        if project_exists:
            print_warning(
                "⚠️ Warning: You are linking to an existing Vercel project. This may cause unexpected results unless the project is clean and dedicated to this deployment flow.")
            logger.warning(f"Project {self.vercel_project_name} already exists on Vercel")
            print_info("It's recommended to use a fresh project name unless you understand the implications.")

            # Ask if user wants to continue
            if not Confirm.ask("Continue with existing project?", default=True):
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

    def _validate_vercel_token(self) -> bool:
        """
        Validate the Vercel token format and check if it's valid by making a test API call.
        
        Returns:
            bool: True if the token is valid, False otherwise
        """
        # Basic format validation
        if len(self.vercel_token) < 10:
            print_error("Vercel token appears to be too short")
            logger.error("Vercel token is too short")
            return False

        # Check if token contains common issues
        if ' ' in self.vercel_token or '\n' in self.vercel_token or '\r' in self.vercel_token:
            print_error("Vercel token contains whitespace characters")
            logger.error("Vercel token contains whitespace characters")
            print_info("Make sure your token doesn't have extra spaces or line breaks")
            # Clean the token
            self.vercel_token = self.vercel_token.strip()

        # Test the token with a simple API call
        try:
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(
                "https://api.vercel.com/v2/user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get("user", {}).get("username", "unknown")
                logger.info(f"Successfully authenticated with Vercel as user: {username}")
                return True
            else:
                print_error(f"Vercel token validation failed: HTTP {response.status_code}")
                logger.error(f"Vercel token validation failed: HTTP {response.status_code}, {response.text}")
                print_info("Please check that your Vercel token is correct and has the necessary permissions")
                return False

        except Exception as e:
            print_error(f"Error validating Vercel token: {str(e)}")
            logger.error(f"Error validating Vercel token: {str(e)}")
            return False

    def _check_project_exists(self) -> bool:
        """
        Check if the specified Vercel project already exists.
        
        Returns:
            bool: True if project exists, False otherwise
        """
        if not self.vercel_token:
            return False

        try:
            # Use Vercel API to check if project exists
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json"
            }

            # First, get all projects
            response = requests.get(
                "https://api.vercel.com/v2/projects",
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"Failed to check if project exists: {response.status_code}")
                return False

            projects = response.json()
            for project in projects:
                if project.get("name") == self.vercel_project_name:
                    # Store the project ID for potential deletion later
                    self.project_id = project.get("id", "")
                    return True

            return False
        except Exception as e:
            logger.warning(f"Error checking if project exists: {str(e)}")
            return False

    def delete_project(self) -> bool:
        """
        Delete the Vercel project.
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if not self.vercel_token or not self.project_id:
            if not self.project_id and self.vercel_project_name:
                # Try to get project ID first
                self._check_project_exists()

            if not self.project_id:
                print_error("No project ID available for deletion")
                return False

        try:
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json"
            }

            response = requests.delete(
                f"https://api.vercel.com/v2/projects/{self.project_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code in (200, 204):
                print_success(f"Successfully deleted project: {self.vercel_project_name}")
                logger.info(f"Deleted Vercel project: {self.vercel_project_name}")
                return True
            else:
                print_error(f"Failed to delete project: {response.status_code}")
                logger.error(f"Failed to delete project: {response.status_code}, {response.text}")
                return False

        except Exception as e:
            print_error(f"Error deleting project: {str(e)}")
            logger.error(f"Error deleting project: {str(e)}")
            return False

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

        # Simplified project configuration to avoid invalid settings
        project_config = {
            "orgId": "",
            "settings": {
                "framework": None
            }
        }

        with open(vercel_dir / "project.json", "w") as f:
            json.dump(project_config, f, indent=2)

        logger.info("Created Vercel configuration files")

    def _deploy_to_vercel(self, temp_path: Path) -> Tuple[bool, str]:
        """
        Deploy the project to Vercel using the VercelDeployer class.
        
        Args:
            temp_path: Path to temporary directory with files to deploy
            
        Returns:
            Tuple[bool, str]: Success flag and deployment URL
        """
        deployer = VercelDeployer(self.vercel_token, self.vercel_project_name)
        success, url = deployer.deploy(temp_path)

        # Store the project ID for potential deletion
        if success:
            self.project_id = deployer.project_id

        return success, url

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

        # Check main URL accessibility
        if not self._verify_main_url():
            return False

        # Check sample files
        return self._verify_sample_files(deployed_files)

    def _verify_main_url(self) -> bool:
        """
        Verify that the main deployment URL is accessible.
        
        Returns:
            bool: True if main URL is accessible, False otherwise
        """
        try:
            response = requests.get(self.deployment_url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Main URL returned status code {response.status_code}")
                print_warning(f"Deployment verification: Main URL returned status code {response.status_code}")
            else:
                print_success("Main URL is accessible")
            return True
        except Exception as e:
            logger.error(f"Error accessing main URL: {str(e)}")
            print_warning(f"Could not access main URL: {str(e)}")
            return False

    def _verify_sample_files(self, deployed_files: List[str]) -> bool:
        """
        Verify that a sample of deployed files are accessible and valid.
        
        Args:
            deployed_files: List of files that were deployed
            
        Returns:
            bool: True if all sample files are verified, False otherwise
        """
        files_to_check = min(3, len(deployed_files))
        files_sample = deployed_files[:files_to_check]
        success_count = 0

        for file in files_sample:
            if self._verify_single_file(file):
                success_count += 1

        return self._evaluate_verification_results(success_count, files_to_check)

    def _verify_single_file(self, filename: str) -> bool:
        """
        Verify that a single deployed file is accessible and valid HTML.
        
        Args:
            filename: Name of the file to verify
            
        Returns:
            bool: True if file is accessible and valid, False otherwise
        """
        file_url = f"{self.deployment_url}/{filename}"

        try:
            response = requests.get(file_url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"File {filename} returned status code {response.status_code}")
                return False

            # Verify it looks like valid HTML
            if self._is_valid_html_content(response.text):
                logger.info(f"Successfully verified {file_url}")
                return True
            else:
                logger.warning(f"File {filename} returned 200 but may not be valid HTML")
                return False

        except Exception as e:
            logger.error(f"Error accessing {filename}: {str(e)}")
            return False

    @staticmethod
    def _is_valid_html_content(content: str) -> bool:
        """
        Check if the content appears to be valid HTML.
        
        Args:
            content: HTML content to validate
            
        Returns:
            bool: True if content appears to be valid HTML, False otherwise
        """
        try:
            soup = BeautifulSoup(content, 'html.parser')
            return soup.title is not None and soup.find('div') is not None
        except Exception:
            return False

    @staticmethod
    def _evaluate_verification_results(success_count: int, total_files: int) -> bool:
        """
        Evaluate the verification results and provide appropriate feedback.
        
        Args:
            success_count: Number of successfully verified files
            total_files: Total number of files checked
            
        Returns:
            bool: True if all files were verified successfully, False otherwise
        """
        if success_count == total_files:
            print_success(f"Successfully verified all {total_files} sample files")
            return True
        else:
            print_warning(f"Verified {success_count}/{total_files} sample files")
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


def validate_deploy_and_optionally_delete(config: Configuration) -> Tuple[
    bool, Optional[IframeEmbedder]]:
    """
    Validate iframe configuration, deploy charts, and optionally delete the project.
    
    Args:
        config: The configuration dictionary containing iframe embedding settings
        
    Returns:
        Tuple[bool, Optional[IframeEmbedder]]: Success flag and embedder instance
    """
    iframe_mode = config.get("IFRAME_EMBEDDING", "disabled")

    if iframe_mode == "disabled":
        return True, None

    embedder = IframeEmbedder(config)
    success = embedder.deploy_charts()

    return success, embedder
