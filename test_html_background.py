#!/usr/bin/env python3
"""
HTML Background Test Script

This script tests the HTML background parsing functionality in _html.py
"""

from pathlib import Path
from _html import prune_html_content

def test_html_parsing():
    """Test HTML background parsing functionality"""
    # Path to the background HTML file
    html_path = Path(__file__).parent / "assets" / "background.html"
    
    # Check if the file exists
    if not html_path.exists():
        print(f"Error: HTML file not found at {html_path}")
        return
        
    try:
        # Read the HTML content
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        # Parse the HTML content
        body, style, js = prune_html_content(html_content)
        
        # Print the results
        print(f"Successfully parsed HTML background from {html_path}")
        print(f"  Body content: {len(body)} characters")
        print(f"  CSS styles: {len(style)} characters")
        print(f"  JavaScript: {len(js)} characters")
        
        # Print the first 100 characters of each
        print("\nBody content preview:")
        print(body[:200] + "..." if len(body) > 200 else body)
        
        print("\nCSS styles preview:")
        print(style[:200] + "..." if len(style) > 200 else style)
        
        print("\nJavaScript preview:")
        print(js[:200] + "..." if len(js) > 200 else js)
        
    except Exception as e:
        print(f"Error parsing HTML: {str(e)}")
        
if __name__ == "__main__":
    test_html_parsing() 