#!/usr/bin/env python3
import os
import dotenv
from pathlib import Path
import requests
from rich.console import Console

# Initialize console for rich output
console = Console()

def print_info(message):
    console.print(f"ℹ️ {message}")

def print_success(message):
    console.print(f"✅ {message}")

def print_error(message):
    console.print(f"❌ {message}")

def print_warning(message):
    console.print(f"⚠️ {message}")

# Load environment variables from .env file if present
env_path = Path('.env')
if env_path.exists():
    print_info(f"Loading environment variables from {env_path.absolute()}")
    dotenv.load_dotenv(dotenv_path=env_path, override=True)
else:
    print_warning("No .env file found in the current directory")
    
# Debug: Show loaded environment variables (without showing sensitive values)
print_info("Loaded environment variables:")
for key in ["GITHUB_USERNAME", "IFRAME_EMBEDDING", "VERCEL_PROJECT_NAME"]:
    if key in os.environ:
        print_info(f"  {key} = {os.environ[key]}")
# Show if token exists but not its value
for key in ["GITHUB_TOKEN", "VERCEL_TOKEN"]:
    if key in os.environ:
        print_info(f"  {key} = [HIDDEN]")
        
# Test Vercel token
vercel_token = os.environ.get("VERCEL_TOKEN", "")
if not vercel_token:
    print_error("No Vercel token found in environment variables")
    exit(1)
    
print_info("Testing Vercel token validity...")
try:
    headers = {
        "Authorization": f"Bearer {vercel_token.strip()}",
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
        print_success(f"Vercel token is valid! Authenticated as: {username}")
        
        # Also test listing projects
        print_info("Testing project listing...")
        proj_response = requests.get(
            "https://api.vercel.com/v2/projects", 
            headers=headers,
            timeout=10
        )
        
        if proj_response.status_code == 200:
            projects = proj_response.json()  # v2 API returns array directly
            print_success(f"Successfully listed {len(projects)} projects")
            for project in projects[:5]:  # Show up to 5 projects
                print_info(f"  - {project.get('name')} (ID: {project.get('id')})")
        else:
            print_error(f"Failed to list projects: HTTP {proj_response.status_code}")
            print_info(f"Response: {proj_response.text[:200]}")
    else:
        print_error(f"Vercel token validation failed: HTTP {response.status_code}")
        print_info(f"Response: {response.text[:200]}")
        
except Exception as e:
    print_error(f"Error testing Vercel token: {str(e)}")

if __name__ == "__main__":
    # The script already ran the test when imported
    pass 