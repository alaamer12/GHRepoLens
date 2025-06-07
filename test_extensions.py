#!/usr/bin/env python3
"""
Test script for verifying file extension handling
"""

import logging
from pathlib import Path
from utilities import get_file_language
from config import LANGUAGE_EXTENSIONS
from visualizer import GithubVisualizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

def test_jsx_tsx_handling():
    """Test that .jsx and .tsx files are handled correctly"""
    logger.info("Testing JSX/TSX file extension handling...")
    
    # Test JSX extensions
    assert get_file_language('test.jsx') == 'JavaScript'
    assert LANGUAGE_EXTENSIONS.get('.jsx') == 'JavaScript'
    
    # Test TSX extensions
    assert get_file_language('test.tsx') == 'TypeScript'
    assert LANGUAGE_EXTENSIONS.get('.tsx') == 'TypeScript'
    
    logger.info("✓ JSX/TSX handling is correct")

def test_latex_tex_handling():
    """Test that LaTeX and TeX are treated as the same language"""
    logger.info("Testing LaTeX/TeX language standardization...")
    
    # Test direct TeX/LaTeX extension handling
    assert get_file_language('test.tex') == 'LaTeX'
    assert get_file_language('test.ltx') == 'LaTeX'
    assert get_file_language('test.latex') == 'LaTeX'
    
    # Test language standardization
    assert GithubVisualizer._standardize_language_name('TeX') == 'LaTeX'
    assert GithubVisualizer._standardize_language_name('LaTeX') == 'LaTeX'
    
    logger.info("✓ LaTeX/TeX standardization is correct")

def main():
    logger.info("Starting file extension handling tests...")
    
    # Run tests
    test_jsx_tsx_handling()
    test_latex_tex_handling()
    
    logger.info("All tests passed!")

if __name__ == "__main__":
    main() 