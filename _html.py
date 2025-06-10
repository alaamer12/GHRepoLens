from pathlib import Path
from typing import Optional, Tuple, Dict

from config import ThemeConfig, DefaultTheme
from console import logger
from repo_analyzer import OrganizationRepoAnalysis, PersonalRepoAnalysis
import re
from html.parser import HTMLParser
import html

CHART_NAMES = ["repository_timeline", "repo_creation_timeline", "quality_heatmap",
               "repo_types_distribution", "commit_activity_heatmap", "top_repos_metrics",
               "infrastructure_metrics", "documentation_quality", "active_inactive_age"]


class HTMLPruner(HTMLParser):
    """
    A robust HTML parser that extracts body content, head styles, and JavaScript.
    """

    def __init__(self, prune_tags=False):
        super().__init__()
        self.prune_tags: bool = prune_tags
        self.in_body: bool = False
        self.in_head: bool = False
        self.in_style: bool = False
        self.in_script: bool = False
        self.head_content: list[str] = []
        self.body_content: list[str] = []
        self.javascript_content: list[str] = []
        self.current_style: list[str] = []
        self.current_script: list[str] = []
        self.tag_stack: list[str] = []
        self.reset_state()

    def reset_state(self):
        """Reset the parser state for reuse."""
        self.in_head = False
        self.in_body = False
        self.in_style = False
        self.in_script = False
        self.head_content = []
        self.body_content = []
        self.javascript_content = []
        self.current_style = []
        self.current_script = []
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()

        if tag_lower == 'head':
            self.in_head = True
        elif tag_lower == 'body':
            self.in_body = True
        elif tag_lower == 'style' and self.in_head:
            self.in_style = True
            # Only add opening tag if not pruning tags
            if not self.prune_tags:
                attrs_str = self._attrs_to_string(attrs)
                self.current_style.append(f'<{tag}{attrs_str}>')
        elif tag_lower == 'script':
            self.in_script = True
            # Only add opening tag if not pruning tags
            if not self.prune_tags:
                attrs_str = self._attrs_to_string(attrs)
                self.current_script.append(f'<{tag}{attrs_str}>')
        elif self.in_body:
            # Reconstruct the tag with attributes
            attrs_str = self._attrs_to_string(attrs)
            self.body_content.append(f'<{tag}{attrs_str}>')
            self.tag_stack.append(tag_lower)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == 'head':
            self.in_head = False
        elif tag_lower == 'body':
            self.in_body = False
        elif tag_lower == 'style' and self.in_style:
            # Only add closing tag if not pruning tags
            if not self.prune_tags:
                self.current_style.append(f'</{tag}>')
            self.head_content.extend(self.current_style)
            self.current_style = []
            self.in_style = False
        elif tag_lower == 'script' and self.in_script:
            # Only add closing tag if not pruning tags
            if not self.prune_tags:
                self.current_script.append(f'</{tag}>')
            self.javascript_content.extend(self.current_script)
            self.current_script = []
            self.in_script = False
        elif self.in_body:
            self.body_content.append(f'</{tag}>')
            if self.tag_stack and self.tag_stack[-1] == tag_lower:
                self.tag_stack.pop()

    def handle_data(self, data):
        if self.in_style:
            self.current_style.append(data)
        elif self.in_script:
            self.current_script.append(data)
        elif self.in_body:
            self.body_content.append(html.escape(data) if data.strip() else data)

    def handle_comment(self, data):
        if self.in_body:
            self.body_content.append(f'<!--{data}-->')

    def handle_decl(self, decl):
        # Handle doctype declarations within body (unusual but possible)
        if self.in_body:
            self.body_content.append(f'<!{decl}>')

    @staticmethod
    def _attrs_to_string(attrs):
        """Convert attribute list to string format."""
        if not attrs:
            return ''
        attr_strings = []
        for name, value in attrs:
            if value is None:
                attr_strings.append(name)
            else:
                # Escape quotes in attribute values
                escaped_value = html.escape(value, quote=True)
                attr_strings.append(f'{name}="{escaped_value}"')
        return ' ' + ' '.join(attr_strings) if attr_strings else ''


# noinspection PyTypeChecker
def prune_html_content(html_content: str, prune_tags: bool = False) -> Tuple[str, str, str]:
    """
    Prune HTML content and extract body content, head styles, and JavaScript.
    
    Args:
        html_content (str): Raw HTML content as string
        prune_tags (bool): If True, return only the content inside tags without the tags themselves
        
    Returns:
        Tuple[str, str, str]: A tuple containing:
            - body_content: All content inside <body> tags
            - head_styles: Content of <style> tags from <head> (with or without tags based on prune_tags)
            - javascript: Content of all <script> tags (with or without tags based on prune_tags)
    
    Examples:
        >>> html = '''
        ... <!DOCTYPE html>
        ... <html>
        ... <head>
        ...     <title>Test</title>
        ...     <style>body { margin: 0; }</style>
        ...     <script>console.log('hello');</script>
        ... </head>
        ... <body>
        ...     <h1>Hello World</h1>
        ...     <script>alert('body script');</script>
        ... </body>
        ... </html>
        ... '''
        >>> body, styles, js = prune_html_content(html, prune_tags=False)
        >>> print(styles)  # With tags
        <style>body { margin: 0; }</style>
        
        >>> body, styles, js = prune_html_content(html, prune_tags=True)
        >>> print(styles)  # Without tags
        body { margin: 0; }
    """

    # Handle empty or None input
    if not html_content or not html_content.strip():
        return '', '', ''

    # Clean up the HTML content
    html_content = html_content.strip()

    # Handle malformed HTML or fragments
    try:
        parser = HTMLPruner(prune_tags=prune_tags)
        parser.feed(html_content)
        parser.close()

        # Join the collected content
        body_content = ''.join(parser.body_content).strip()
        head_styles = ''.join(parser.head_content).strip()
        javascript = ''.join(parser.javascript_content).strip()

        return body_content, head_styles, javascript

    except Exception as e:
        # Fallback to regex-based extraction for severely malformed HTML
        return _fallback_extraction(html_content, prune_tags)


# noinspection RegExpAnonymousGroup
def _fallback_extraction(html_content: str, prune_tags: bool = False) -> Tuple[str, str, str]:
    """
    Fallback extraction using regex for malformed HTML.
    """
    try:
        # Extract body content using regex
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        body_content = body_match.group(1).strip() if body_match else ''

        # Extract style tags from head using regex
        head_match = re.search(r'<head[^>]*>(.*?)</head>', html_content, re.DOTALL | re.IGNORECASE)
        head_styles = ''

        if head_match:
            head_content = head_match.group(1)
            if prune_tags:
                # Extract only the content inside style tags
                style_matches = re.findall(r'<style[^>]*>(.*?)</style>', head_content, re.DOTALL | re.IGNORECASE)
                head_styles = ''.join(style_matches).strip()
            else:
                # Extract complete style tags
                style_matches = re.findall(r'<style[^>]*>.*?</style>', head_content, re.DOTALL | re.IGNORECASE)
                head_styles = ''.join(style_matches).strip()

        # Extract all script tags from entire document
        if prune_tags:
            # Extract only the content inside script tags
            script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE)
            javascript = ''.join(script_matches).strip()
        else:
            # Extract complete script tags
            script_matches = re.findall(r'<script[^>]*>.*?</script>', html_content, re.DOTALL | re.IGNORECASE)
            javascript = ''.join(script_matches).strip()

        return body_content, head_styles, javascript

    except Exception:
        # Ultimate fallback - return original content and empty styles/js
        return html_content, '', ''


# Additional utility functions
def prune_html_file(file_path: str, prune_tags: bool = False) -> Tuple[str, str, str]:
    """
    Prune HTML content from a file.
    
    Args:
        file_path (str): Path to the HTML file
        prune_tags (bool): If True, return only the content inside tags without the tags themselves
        
    Returns:
        Tuple[str, str, str]: Body content, head styles, and JavaScript
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return prune_html_content(html_content, prune_tags)
    except FileNotFoundError:
        raise FileNotFoundError(f"HTML file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading HTML file: {str(e)}")


def create_social_links(social_links: Dict[str, str]) -> str:
    """Generate HTML for social links based on theme configuration"""
    links_html = []

    # Social media icon SVGs and colors
    icon_map = {
        "github": {
            "bg": "bg-gray-800",
            "hover": "hover:bg-primary",
            "svg": """<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
        </svg>"""
        },
        "linkedin": {
            "bg": "bg-blue-600",
            "hover": "hover:bg-blue-700",
            "svg": """<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.454C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.225 0z"/>
        </svg>"""
        },
        "portfolio": {
            "bg": "bg-emerald-600",
            "hover": "hover:bg-emerald-700",
            "svg": """<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm1 16.057v-3.05c2.083.129 4.066-.534 5.18-1.412-1.381 2.070-3.482 3.678-5.18 4.462zm-1 1.05c-4.986 0-9.047-4.061-9.047-9.07 0-4.99 4.061-9.044 9.047-9.044 4.986 0 9.047 4.054 9.047 9.044 0 4.37-3.099 8.008-7.197 8.851v-2.137c1.816-.471 3.857-1.932 3.857-6.001 0-2.186-.5-3.99-1.57-4.814.324-1.045.345-2.717-.42-3.818-.345-.003-1.208.154-2.679 1.135-.768-.22-1.59-.334-2.429-.334-.84 0-1.662.114-2.428.334-1.472-.98-2.343-1.138-2.688-1.135-.765 1.101-.735 2.773-.419 3.818-1.074.825-1.564 2.628-1.564 4.814 0 4.062 2.074 5.53 3.846 6.001v2.137c-4.098-.843-7.197-4.481-7.197-8.851 0-4.99 4.061-9.044 9.047-9.044 4.986 0 9.047 4.054 9.047 9.044 0 5.009-4.061 9.07-9.047 9.07z"/>
        </svg>"""
        },
        "twitter": {
            "bg": "bg-blue-400",
            "hover": "hover:bg-blue-500",
            "svg": """<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723 9.99 9.99 0 01-3.127 1.195 4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.937 4.937 0 004.604 3.417 9.868 9.868 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.054 0 13.999-7.496 13.999-13.986 0-.209 0-.42-.015-.63a9.936 9.936 0 002.46-2.548l-.047-.02z"/>
        </svg>"""
        }
    }

    # Generate HTML for each social link
    for platform, url in social_links.items():
        platform_lower = platform.lower()
        icon_config = icon_map.get(platform_lower, {
            "bg": "bg-gray-600",
            "hover": "hover:bg-gray-700",
            "svg": """<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
        </svg>"""
        })

        link_html = f"""
        <a href="{url}" target="_blank"
           class="social-icon p-2 rounded-full {icon_config['bg']} text-white {icon_config['hover']} shadow-md transition-all duration-300 hover:scale-110 hover:rotate-6 transform"
           aria-label="{platform} Profile">
            {icon_config['svg']}
        </a>
        """
        links_html.append(link_html)

    return "\n".join(links_html)


def create_skills_badges(skills: Dict[str, str]) -> str:
    """Generate HTML for skills badges based on theme configuration"""
    skill_badges = []

    for skill_name, skill_url in skills.items():
        badge_html = f"""
        <a href="{skill_url}" target="_blank" rel="noopener noreferrer">
            <span class="text-xs px-2 py-0.5 rounded-full tech-badge text-primary dark:text-indigo-300">{skill_name}</span>
        </a>
        """
        skill_badges.append(badge_html)

    return "\n".join(skill_badges)


class HTMLVisualizer:
    """Class responsible for creating HTML visualizations from repository data"""

    def __init__(self, username: str, reports_dir: Path, theme: Optional[ThemeConfig] = None):
        """Initialize the visualizer with username and reports directory"""
        self.username = username
        self.reports_dir = reports_dir
        self.theme = theme if theme is not None else DefaultTheme.get_default_theme()
        self.bg_html_body, self.bg_html_css, self.bg_html_js = self._load_background_html()

    def _load_background_html(self) -> Tuple[str, str, str]:
        """Load and parse background HTML if specified in theme config"""
        if not self.theme.get("background_html_path"):
            return "", "", ""

        html_path = self.theme["background_html_path"]
        if not Path(html_path).exists():
            return "", "", ""

        return prune_html_file(html_path, prune_tags=True)

    @staticmethod
    def create_chart_modal_container() -> str:
        """Create the chart modal container"""
        return """
                <!-- Modal for full-screen chart view with interactive content -->
                <div class="chart-modal" id="chartModal">
                    <div class="chart-modal-content">
                        <button class="chart-modal-close" id="chartModalClose">&times;</button>
                        <div class="chart-modal-iframe-container">
                            <iframe class="chart-modal-iframe" id="chartModalIframe" src="" allowfullscreen></iframe>
                        </div>
                        <div class="chart-modal-info">
                            <h3 class="chart-modal-title" id="chartModalTitle"></h3>
                            <p class="chart-modal-description" id="chartModalDescription"></p>
                        </div>
                    </div>
                </div>
        """

    def create_head_section(self) -> str:
        """Create the head section of the HTML file"""
        head = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <title>GitHub Repository Analysis Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
            <script src="https://unpkg.com/aos@2.3.1/dist/aos.js"></script>
            <link href="https://unpkg.com/aos@2.3.1/dist/aos.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.2/dist/gsap.min.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
            <link rel="icon" type="image/png" href="static/assets/favicon.png">
            <script>
                tailwind.config = {{
                    darkMode: 'class',
                    theme: {{
                        extend: {{
                            colors: {{
                                primary: '{self.theme["primary_color"]}',
                                secondary: '{self.theme["secondary_color"]}',
                                accent: '{self.theme["accent_color"]}',
                            }},
                            fontFamily: {{
                                sans: ['{self.theme["heading_font"].split(",")[0].replace("'", "")}', 'sans-serif'],
                                mono: ['{self.theme["code_font"].split(",")[0].replace("'", "")}', 'monospace'],
                            }},
                            borderRadius: {{
                                DEFAULT: '{self.theme["border_radius"]}',
                            }},
                            boxShadow: {{
                                custom: '{self.theme["shadow_style"]}',
                            }},
                            animation: {{
                                'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                                'float': 'float 3s ease-in-out infinite',
                                'slide-up': 'slideUp 0.5s ease-out',
                                'zoom-in': 'zoomIn 0.5s ease-out',
                                'bounce-in': 'bounceIn 0.7s ease-out',
                                'fade-in': 'fadeIn 0.5s ease-out',
                                'spin-slow': 'spin 8s linear infinite',
                            }},
                            keyframes: {{
                                float: {{
                                    '0%, 100%': {{ transform: 'translateY(0)' }},
                                    '50%': {{ transform: 'translateY(-10px)' }},
                                }},
                                slideUp: {{
                                    '0%': {{ transform: 'translateY(20px)', opacity: '0' }},
                                    '100%': {{ transform: 'translateY(0)', opacity: '1' }},
                                }},
                                zoomIn: {{
                                    '0%': {{ transform: 'scale(0.95)', opacity: '0' }},
                                    '100%': {{ transform: 'scale(1)', opacity: '1' }},
                                }},
                                bounceIn: {{
                                    '0%': {{ transform: 'scale(0.3)', opacity: '0' }},
                                    '50%': {{ transform: 'scale(1.05)', opacity: '0.8' }},
                                    '70%': {{ transform: 'scale(0.9)', opacity: '0.9' }},
                                    '100%': {{ transform: 'scale(1)', opacity: '1' }},
                                }},
                                fadeIn: {{
                                    '0%': {{ opacity: '0' }},
                                    '100%': {{ opacity: '1' }},
                                }}
                            }}
                        }}
                    }}
                }}
            </script>
            <style>
                {self.bg_html_css}
                /* Custom styles that extend Tailwind */
                .bg-gradient-primary {{
                    background: {self.theme["header_gradient"]};
                }}

                /* Theme transition */
                .transition-theme {{
                    transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
                }}

                /* Chart Modal Styles with iframe support */
                .chart-modal {{
                    visibility: hidden;
                    position: fixed;
                    top: 0;
                    right: 0;
                    bottom: 0;
                    left: 0;
                    background-color: rgba(0, 0, 0, 0.85);
                    z-index: 9999;
                    opacity: 0;
                    backdrop-filter: blur(5px);
                    transition: all 0.4s ease-in-out;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}

                .chart-modal.active {{
                     visibility: visible;
                    opacity: 1;
                }}

                .chart-modal-content {{
                    background-color: white;
                    width: 90%;
                    max-width: 1200px;
                    height: 85vh;
                    margin: 0 auto;
                    border-radius: 16px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
                    overflow-y: auto !important;
                    display: flex;
                    flex-direction: column;
                    transform: scale(0.95);
                    opacity: 0;
                    transition: all 0.3s ease-in-out;
                    position: relative;
                }}
                
                .chart-modal.active .chart-modal-content {{
                    transform: scale(1);
                    opacity: 1;
                }}

                .dark .chart-modal-content {{
                    background-color: #1f2937;
                    color: white;
                }}

                .chart-modal-iframe-container {{
                    flex: 1;
                    overflow-y: auto !important;
                    overflow-x: auto !important;
                    scroll-behavior: smooth;
                    display: block;
                    min-height: 400px;
                    height: 75vh;
                }}

                .chart-modal-iframe {{
                    width: 100%;
                    height: 100%;
                    border: none;
                    transition: opacity 0.3s ease;
                    display: block;
                }}

                .chart-modal-close {{
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    font-size: 24px;
                    color: #fff;
                    background: rgba(255, 255, 255, 0.2);
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    z-index: 10;
                    backdrop-filter: blur(4px);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
                    transition: all 0.3s cubic-bezier(0.19, 1, 0.22, 1);
                }}

                .dark .chart-modal-close {{
                    color: white;
                    background: #374151;
                }}

                .chart-modal-close:hover {{
                    transform: scale(1.1) rotate(90deg);
                    background-color: rgba(255, 255, 255, 0.3);
                }}

                .dark .chart-modal-close:hover {{
                    background-color: #4b5563;
                }}

                .chart-modal-info {{
                    padding: 20px;
                    background: linear-gradient(to top, rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.3), transparent);
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    transform: translateY(100%);
                    opacity: 0;
                    transition: all 0.6s cubic-bezier(0.19, 1, 0.22, 1);
                    transition-delay: 0.1s;
                    z-index: 5;
                }}

                .dark .chart-modal-info {{
                    border-top: 1px solid #374151;
                }}

                .chart-modal-title {{
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 8px;
                    color: white;
                }}

                .chart-modal-description {{
                    font-size: 1rem;
                    color: rgba(255, 255, 255, 0.8);
                }}

                .dark .chart-modal-description {{
                    color: #9ca3af;
                }}

                .chart-modal.active .chart-modal-info {{
                    transform: translateY(0);
                    opacity: 1;
                }}

                .chart-modal-image {{
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    display: block;
                }}

                /* Custom scrollbar */
                ::-webkit-scrollbar {{
                    width: 12px !important;
                    height: 12px !important;
                    display: block !important;
                }}

                ::-webkit-scrollbar-track {{
                    background: #f1f1f1;
                    border-radius: 4px;
                    margin: 2px;
                    display: block !important;
                }}

                .dark ::-webkit-scrollbar-track {{
                    background: #374151;
                }}

                ::-webkit-scrollbar-thumb {{
                     background: linear-gradient(135deg, rgba(79, 70, 229, 0.9) 0%, rgba(124, 58, 237, 0.9) 50%, rgba(249, 115, 22, 0.9) 100%) !important;
                    border-radius: 6px;
                    border: 2px solid transparent;
                    background-clip: padding-box;
                    transition: all 0.3s ease;
                    display: block !important;
                    min-height: 40px;
                }}

                ::-webkit-scrollbar-thumb:hover {{
                    background: linear-gradient(135deg, rgba(79, 70, 229, 1) 0%, rgba(124, 58, 237, 1) 50%, rgba(249, 115, 22, 1) 100%) !important;
                }}

                .dark ::-webkit-scrollbar-thumb {{
                     background: linear-gradient(135deg, rgba(79, 70, 229, 0.8) 0%, rgba(124, 58, 237, 0.8) 50%, rgba(249, 115, 22, 0.8) 100%) !important;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}

                .dark ::-webkit-scrollbar-thumb:hover {{
                    background: linear-gradient(135deg, rgba(79, 70, 229, 1) 0%, rgba(124, 58, 237, 1) 50%, rgba(249, 115, 22, 1) 100%) !important;
                }}

                /* Additional scrollbar styling for modal in dark mode */
                .chart-modal.active .chart-modal-content::-webkit-scrollbar,
                .chart-modal.active .chart-modal-iframe-container::-webkit-scrollbar {{
                    width: 14px !important;
                    display: block !important;
                }}

                .chart-modal.active .chart-modal-content::-webkit-scrollbar-thumb,
                .chart-modal.active .chart-modal-iframe-container::-webkit-scrollbar-thumb {{
                    background: linear-gradient(135deg, rgba(124, 58, 237, 0.9) 0%, rgba(249, 115, 22, 0.9) 100%) !important;
                    border: 2px solid #1f2937;
                    min-height: 50px;
                }}
                
                /* Smooth scrolling for the entire page */
                html {{
                    scroll-behavior: smooth;
                    overflow-y: auto !important;
                }}
                
                 /* Styles for scrollable tables and sections */
                .scrollable-table-container {{
                    max-height: 500px;
                    overflow-y: auto !important;
                    overflow-x: hidden;
                    border-radius: 0.5rem;
                    position: relative;
                    scrollbar-width: thin;
                    scrollbar-color: var(--primary) var(--scrollbar-track);
                    padding-right: 0.25rem;
                }}

                /* Stats animation */
                @keyframes countUp {{
                    from {{ transform: translateY(10px); opacity: 0; }}
                    to {{ transform: translateY(0); opacity: 1; }}
                }}

                .animate-count-up {{
                    animation: countUp 0.8s ease-out forwards;
                }}

                /* Card hover effects */
                .stat-card {{
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }}

                .stat-card:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 15px 30px -5px rgba(0, 0, 0, 0.15), 0 10px 15px -5px rgba(0, 0, 0, 0.08);
                }}

                /* New animation classes */
                .card-3d-effect {{
                    transform-style: preserve-3d;
                    perspective: 1000px;
                    transition: all 0.3s ease;
                }}

                .card-3d-effect:hover {{
                    transform: rotateX(5deg) rotateY(5deg);
                }}

                .card-inner {{
                    transform: translateZ(20px);
                    transition: all 0.3s ease;
                }}

                /* Animated background */
                .animated-bg {{
                    background-size: 400% 400%;
                    animation: gradientBG 15s ease infinite;
                }}

                @keyframes gradientBG {{
                    0% {{ background-position: 0% 50%; }}
                    50% {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}

                /* Progress bar animation */
                @keyframes progressFill {{
                    from {{ width: 0%; }}
                    to {{ width: var(--progress-width); }}
                }}

                .animate-progress {{
                    animation: progressFill 1.5s ease-out forwards;
                }}

                /* Icon pulse */
                @keyframes iconPulse {{
                    0% {{ transform: scale(1); }}
                    50% {{ transform: scale(1.1); }}
                    100% {{ transform: scale(1); }}
                }}

                .animate-icon-pulse {{
                    animation: iconPulse 2s ease-in-out infinite;
                }}

                /* Chart entrance animation */
                @keyframes chartEnter {{
                    0% {{ opacity: 0; transform: translateY(30px); }}
                    100% {{ opacity: 1; transform: translateY(0); }}
                }}

                .animate-chart-enter {{
                    animation: chartEnter 0.8s ease-out forwards;
                }}

                /* Creator section animation */
                @keyframes glowPulse {{
                    0% {{ box-shadow: 0 0 5px 0 rgba(79, 70, 229, 0.5); }}
                    50% {{ box-shadow: 0 0 20px 5px rgba(79, 70, 229, 0.5); }}
                    100% {{ box-shadow: 0 0 5px 0 rgba(79, 70, 229, 0.5); }}
                }}

                .animate-glow {{
                    animation: glowPulse 3s infinite;
                }}

                .social-link {{
                    transition: all 0.3s ease;
                }}

                .social-link:hover {{
                    transform: translateY(-3px);
                    filter: brightness(1.2);
                }}

                /* New creator card styles */
                .creator-card {{
                    position: relative;
                    overflow: hidden;
                    border-radius: 16px;
                    transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1);
                }}

                .creator-card::before {{
                    content: "";
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(225deg, rgba(79, 70, 229, 0.4) 0%, rgba(124, 58, 237, 0.4) 50%, rgba(249, 115, 22, 0.4) 100%);
                    opacity: 0;
                    z-index: 0;
                    transition: opacity 0.5s ease;
                }}

                .creator-card:hover::before {{
                    opacity: 1;
                }}

                .creator-profile-img {{
                    position: relative;
                    transition: all 0.5s ease;
                }}

                .creator-card:hover .creator-profile-img {{
                    transform: scale(1.05);
                }}

                .creator-info {{
                    position: relative;
                    z-index: 1;
                }}

                .social-icon {{
                    transition: all 0.3s ease;
                    position: relative;
                    overflow: hidden;
                }}

                .social-icon::after {{
                    content: "";
                    position: absolute;
                    inset: 0;
                    background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.2) 100%);
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }}

                .social-icon:hover {{
                    transform: translateY(-5px) scale(1.1);
                }}

                .social-icon:hover::after {{
                    opacity: 1;
                }}

                .stack-badge {{
                    position: relative;
                    overflow: hidden;
                }}

                .stack-badge::before {{
                    content: "";
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
                    transform: rotate(45deg);
                    animation: shine 3s infinite;
                }}

                @keyframes shine {{
                    0% {{ transform: translateX(-100%) rotate(45deg); }}
                    100% {{ transform: translateX(100%) rotate(45deg); }}
                }}

                .animate-typing {{
                    overflow: hidden;
                    border-right: 2.5px solid;
                    white-space: nowrap;
                    animation: typing 2.5s steps(40, end) forwards, 
                               blink-caret 0.65s step-end infinite;
                    width: 0;
                    display: inline-block;
                    max-width: calc(20ch + 10px);
                }}

                @keyframes typing {{
                    from {{ width: 0 }}
                    to {{ width: calc(20ch + 10px) }}
                }}

                @keyframes blink-caret {{
                    from, to {{ border-color: transparent }}
                    50% {{ border-color: currentColor }}
                }}

                .tech-badge {{
                    background: rgba(79, 70, 229, 0.1);
                    backdrop-filter: blur(8px);
                    border: 1px solid rgba(79, 70, 229, 0.2);
                    transition: all 0.3s ease;
                }}

                .tech-badge:hover {{
                    background: rgba(79, 70, 229, 0.2);
                    transform: translateY(-2px);
                }}

                .floating {{
                    animation: floating 3s ease-in-out infinite;
                }}

                @keyframes floating {{
                    0% {{ transform: translateY(0px); }}
                    50% {{ transform: translateY(-10px); }}
                    100% {{ transform: translateY(0px); }}
                }}
                
                /* Force scrollbar display for Firefox */
                * {{
                    scrollbar-width: thin;
                    scrollbar-color: var(--primary) var(--scrollbar-track);
                }}

                /* Repository metadata section styles */
                .metadata-row {{
                    transition: all 0.3s ease-out;
                }}
                
                .metadata-row.hidden {{
                    display: none;
                }}
                
                .toggle-metadata-btn {{
                    cursor: pointer;
                }}
                
                .metadata-arrow {{
                    transition: transform 0.3s ease;
                }}
                
                .metadata-container {{
                    transform-origin: top center;
                    max-height: 0;
                    opacity: 0;
                    animation: none;
                }}
                
                .metadata-container.animate-chart-enter {{
                    animation: metadataSlideDown 0.3s ease forwards;
                }}
                
                @keyframes metadataSlideDown {{
                    from {{
                        max-height: 0;
                        opacity: 0;
                        transform: translateY(-10px);
                    }}
                    to {{
                        max-height: 2000px;
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}
                
                .metadata-item {{
                    border-left: 3px solid rgba(79, 70, 229, 0.5);
                    transition: all 0.2s ease;
                }}
                
                .metadata-item:hover {{
                    border-left-color: rgb(79, 70, 229);
                    transform: translateX(3px);
                }}
                
                .stack-badge {{
                    position: relative;
                    overflow: hidden;
                }}
            </style>
        </head>"""

        return head

    def create_body_start(self, timestamp: str) -> str:
        """Create the body start section of the HTML file"""
        body_start = f"""<body class="transition-theme bg-gray-100 dark:bg-gray-900 min-h-screen">

            <!-- Background HTML -->
            {self.bg_html_body}

            <!-- Theme toggle button with animation -->
            <button id="theme-toggle" class="fixed top-4 right-4 z-50 p-2 rounded-full bg-white/20 dark:bg-gray-800/20 backdrop-blur-sm text-black dark:text-white border border-gray-200 dark:border-gray-700 hover:bg-white/30 dark:hover:bg-gray-800/30 transition-all duration-300 shadow-lg hover:animate-spin-slow">
                <svg id="theme-toggle-dark-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
                </svg>
                <svg id="theme-toggle-light-icon" class="w-6 h-6 hidden" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fill-rule="evenodd" clip-rule="evenodd"></path>
                </svg>
            </button>

            <div class="container mx-auto px-4 py-8 max-w-7xl">
                <!-- Header section with enhanced animations and banner as background -->
                <div data-aos="fade-down" data-aos-duration="800" class="relative bg-gradient-primary animated-bg rounded-lg shadow-xl mb-8 overflow-hidden transform transition-all hover:shadow-2xl">
                    <!-- Semi-transparent background banner image -->
                    <div class="absolute inset-0 w-full h-full opacity-20 dark:hidden">
                        <img src="static/assets/light_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>
                    <div class="absolute inset-0 w-full h-full opacity-20 hidden dark:block">
                        <img src="static/assets/dark_banner.png" alt="" class="w-full h-full object-cover" />
                    </div>

                    <div class="relative p-6 md:p-10 text-center z-10">
                        <h1 class="text-3xl md:text-5xl font-light text-white mb-4 animate-bounce-in">📊 GitHub Repository Analysis</h1>
                        <p class="text-lg text-white/90 animate-fade-in">
                            User: <span class="font-semibold">{self.username}</span> | Generated: {timestamp}
                        </p>
                    </div>
                </div>"""

        return body_start

    def create_creator_section(self) -> str:
        """Create the creator section of the HTML file"""

        social_links = self.theme["social_links"]
        skills = self.theme["skills"]
        user_avatar = self.theme["user_avatar"]
        user_name = self.theme["user_name"]
        user_title = self.theme["user_title"]
        user_bio = self.theme["user_bio"]

        creator_section = f"""
            <!-- Creator Section - Modern & Compact -->
            <div id="creator-section" class="relative overflow-hidden bg-white/10 dark:bg-gray-800/20 backdrop-blur-sm rounded-xl shadow-lg mb-6 transition-all duration-500 group">
                <div class="absolute inset-0 bg-gradient-to-br from-primary/5 via-secondary/5 to-accent/5 dark:from-primary/10 dark:via-secondary/10 dark:to-accent/10 opacity-80"></div>

                <div class="relative z-10 flex items-center p-4 gap-4">
                    <!-- Creator Image & Name -->
                    <div class="relative w-16 h-16 rounded-full overflow-hidden shadow-lg border-2 border-primary/30 creator-profile-img" data-aos="zoom-in" data-aos-delay="100">
                        <img src="{user_avatar}" alt="{user_name}" class="w-full h-full object-cover" />
                        <div class="absolute inset-0 bg-gradient-to-tr from-primary/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                    </div>

                    <div class="flex-1">
                        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                            <!-- Name & Role -->
                            <div>
                                <h3 class="text-xl font-bold text-gray-800 dark:text-white flex items-center" data-aos="fade-right" data-aos-delay="150">
                                    <span class="mr-2">{user_name}</span>
                                    <span class="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary dark:bg-primary/20 stack-badge">
                                        {user_title}
                                    </span>
                                </h3>
                                <p class="text-sm text-gray-600 dark:text-gray-300" data-aos="fade-right" data-aos-delay="200">
                                    <span class="animate-typing">{user_bio}</span>
                                </p>
                            </div>

                            <!-- Social Links -->
                            <div class="flex gap-3" data-aos="fade-left" data-aos-delay="250">
                                {create_social_links(social_links)}
                            </div>
                        </div>

                        <!-- Technologies Row -->
                        <div class="mt-2 flex flex-wrap gap-2" data-aos="fade-up" data-aos-delay="300">
                            {create_skills_badges(skills)}
                        </div>
                    </div>
                </div>
            </div>

            <script>
            document.addEventListener('DOMContentLoaded', function() {{
                if (typeof gsap !== 'undefined') {{
                    const creatorSection = document.getElementById('creator-section');
                    if (creatorSection) {{
                        creatorSection.addEventListener('mouseenter', function() {{
                            gsap.to(this, {{
                                scale: 1.02,
                                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
                                duration: 0.3,
                                ease: 'power2.out'
                            }});
                            gsap.to(this.querySelectorAll('.tech-badge'), {{
                                stagger: 0.05,
                                y: -4,
                                scale: 1.1,
                                duration: 0.2,
                                ease: 'back.out(1.7)'
                            }});
                        }});
                        creatorSection.addEventListener('mouseleave', function() {{
                            gsap.to(this, {{
                                scale: 1,
                                boxShadow: 'none',
                                duration: 0.3,
                                ease: 'power2.out'
                            }});
                            gsap.to(this.querySelectorAll('.tech-badge'), {{
                                stagger: 0.05,
                                y: 0,
                                scale: 1,
                                duration: 0.2,
                                ease: 'back.out(1.7)'
                            }});
                        }});
                    }}
                }}
            }});
            </script>
        """
        return creator_section

    @staticmethod
    def create_repo_type_tabs(has_org_repos: bool) -> str:
        """Create tab buttons to switch between personal and organization repositories"""
        # If there are no organization repositories, don't show the tabs
        if not has_org_repos:
            return ""

        repo_type_tabs = """
            <!-- Repository Type Tabs - Toggle between Personal and Organization repositories -->
            <div data-aos="fade-up" data-aos-duration="600" class="mb-8">
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 flex flex-col sm:flex-row justify-between items-center">
                    <div class="flex-1">
                        <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-3 sm:mb-0">Repository Analysis Type</h3>
                    </div>
                    
                    <!-- Tab buttons with modern styling -->
                    <div class="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1 shadow-inner relative overflow-hidden">
                        <!-- Personal repositories tab -->
                        <button id="personal-repos-tab" class="flex items-center justify-center px-6 py-2 text-sm font-medium rounded-md relative z-10 transition-all duration-300 text-gray-900 dark:text-white active-tab">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                            Personal
                        </button>
                        
                        <!-- Organizations repositories tab -->
                        <button id="org-repos-tab" class="flex items-center justify-center px-6 py-2 text-sm font-medium rounded-md relative z-10 transition-all duration-300 text-gray-500 dark:text-gray-400">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                            </svg>
                            Organizations
                        </button>
                        
                        <!-- Active indicator pill that slides between tabs -->
                        <span id="tab-indicator" class="absolute inset-y-1 left-1 bg-primary/90 dark:bg-primary rounded-md transition-all duration-300 shadow-md"></span>
                    </div>
                </div>
                
                <!-- Current view indicator -->
                <div class="mt-3 text-sm text-center">
                    <div class="inline-flex items-center bg-primary/10 text-primary dark:bg-primary/20 px-3 py-1 rounded-full">
                        <span id="current-view-icon" class="mr-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                        </span>
                        <span id="current-view-text">Viewing Personal Repository Stats</span>
                    </div>
                </div>
            </div>
        """
        return repo_type_tabs

    @staticmethod
    def create_stats_section() -> str:
        """Create the stats section of the HTML file"""
        stats_section = f"""<!-- Stats overview with enhanced animations -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                    <!-- Repositories count - Represents collection/organization -->
                    <div data-aos="zoom-in" data-aos-delay="100" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-primary shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-primary">Total Repositories</p>
                                <p id="repo-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-primary transform group-hover:animate-pulse">0</p>
                            </div>
                            <!-- Stack of folders animation - representing organized collection -->
                            <div class="relative bg-primary/10 rounded-full p-3 transition-all duration-500 group-hover:bg-primary/20">
                                <svg class="w-8 h-8 text-primary transition-all duration-700 group-hover:scale-125" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Floating mini boxes to represent multiple repos -->
                                <div class="absolute -top-1 -right-1 w-2 h-2 bg-primary rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.1s;"></div>
                                <div class="absolute -top-2 right-1 w-1.5 h-1.5 bg-primary/70 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.2s;"></div>
                                <div class="absolute top-0 -right-2 w-1 h-1 bg-primary/50 rounded-full opacity-0 group-hover:opacity-100 transition-all duration-500 group-hover:animate-bounce" style="animation-delay: 0.3s;"></div>
                            </div>
                        </div>
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-primary to-primary/50 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1000"></div>
                        <div class="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                    </div>

                    <!-- Total LOC - Represents typing/code flowing -->
                    <div data-aos="zoom-in" data-aos-delay="200" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-secondary shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-secondary">Total Lines of Code</p>
                                <!-- Counter animation simulating incrementing lines -->
                                <p id="loc-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-secondary relative overflow-hidden">
                                    <span class="inline-block transform transition-transform duration-700 group-hover:translate-y-[-100%]">0</span>
                                </p>
                            </div>
                            <!-- Typing animation - code brackets moving -->
                            <div class="relative bg-secondary/10 rounded-full p-3 transition-all duration-500 group-hover:bg-secondary/20">
                                <svg class="w-8 h-8 text-secondary transition-all duration-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Flowing code dots animation -->
                                <div class="absolute top-2 left-1 w-1 h-1 bg-secondary rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0s;"></div>
                                <div class="absolute top-4 left-2 w-1 h-1 bg-secondary/70 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.2s;"></div>
                                <div class="absolute top-6 left-3 w-1 h-1 bg-secondary/50 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.4s;"></div>
                            </div>
                        </div>
                        <!-- Progressive filling bar like code compilation -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-secondary via-secondary/70 to-secondary/50 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1500 ease-out"></div>
                        <div class="absolute inset-0 bg-secondary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg"></div>
                    </div>

                    <!-- Total Stars - Represents appreciation/twinkling -->
                    <div data-aos="zoom-in" data-aos-delay="300" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-accent shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-accent">Total Stars</p>
                                <!-- Glowing number effect for stars -->
                                <p id="stars-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-accent group-hover:drop-shadow-lg group-hover:filter group-hover:brightness-125">0</p>
                            </div>
                            <!-- Twinkling star animation -->
                            <div class="relative bg-accent/10 rounded-full p-3 transition-all duration-500 group-hover:bg-accent/20">
                                <svg class="w-8 h-8 text-accent transition-all duration-1000 group-hover:scale-125 group-hover:rotate-180 group-hover:drop-shadow-lg" fill="currentColor" stroke="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                </svg>
                                <!-- Sparkle effects around the star -->
                                <div class="absolute -top-1 -left-1 w-1 h-1 bg-accent rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0s;"></div>
                                <div class="absolute -top-2 -right-1 w-1.5 h-1.5 bg-accent/80 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.3s;"></div>
                                <div class="absolute -bottom-1 -left-2 w-1 h-1 bg-accent/60 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.6s;"></div>
                                <div class="absolute -bottom-2 -right-2 w-2 h-2 bg-accent/40 rounded-full opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-300" style="animation-delay: 0.9s;"></div>
                            </div>
                        </div>
                        <!-- Shimmering progress bar like starlight -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-accent via-yellow-300 to-accent transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1200 ease-out"></div>
                        <div class="absolute inset-0 bg-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg group-hover:animate-pulse"></div>
                    </div>

                    <!-- Active Repositories - Represents life/activity/heartbeat -->
                    <div data-aos="zoom-in" data-aos-delay="400" class="stat-card card-3d-effect bg-white dark:bg-gray-800 rounded-lg p-6 border-l-4 border-green-500 shadow-lg dark:text-white overflow-hidden relative group transform transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                        <div class="card-inner flex items-center justify-between">
                            <div class="transform transition-all duration-700 group-hover:translate-x-2">
                                <p class="text-sm text-gray-500 dark:text-gray-400 transition-colors duration-300 group-hover:text-green-500">Active Repositories</p>
                                <!-- Heartbeat-like pulsing number -->
                                <p id="active-count" class="text-3xl font-bold transition-all duration-700 group-hover:scale-110 group-hover:text-green-500 group-hover:animate-pulse">0</p>
                            </div>
                            <!-- Heartbeat/pulse animation for activity -->
                            <div class="relative bg-green-500/10 rounded-full p-3 transition-all duration-500 group-hover:bg-green-500/20">
                                <svg class="w-8 h-8 text-green-500 transition-all duration-700 group-hover:scale-125" fill="currentColor" stroke="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd" class="group-hover:animate-pulse"></path>
                                </svg>
                                <!-- Ripple effects for activity -->
                                <div class="absolute inset-0 rounded-full bg-green-500/20 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700"></div>
                                <div class="absolute inset-1 rounded-full bg-green-500/15 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700" style="animation-delay: 0.3s;"></div>
                                <div class="absolute inset-2 rounded-full bg-green-500/10 opacity-0 group-hover:opacity-100 group-hover:animate-ping transition-all duration-700" style="animation-delay: 0.6s;"></div>
                            </div>
                        </div>
                        <!-- Rhythmic progress bar like activity monitor -->
                        <div class="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-green-500 via-green-400 to-green-300 transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-1000 ease-in-out"></div>
                        <div class="absolute inset-0 bg-green-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-lg"></div>
                        <!-- Subtle heartbeat lines -->
                        <div class="absolute top-4 right-4 opacity-0 group-hover:opacity-30 transition-opacity duration-500">
                            <div class="w-8 h-0.5 bg-green-500/50 group-hover:animate-pulse"></div>
                            <div class="w-6 h-0.5 bg-green-500/30 mt-1 group-hover:animate-pulse" style="animation-delay: 0.2s;"></div>
                            <div class="w-4 h-0.5 bg-green-500/20 mt-1 group-hover:animate-pulse" style="animation-delay: 0.4s;"></div>
                        </div>
                    </div>
                </div>"""
        return stats_section

    @staticmethod
    def create_charts_section(has_org_repos: bool, orepo_analysis: OrganizationRepoAnalysis,
                              prepo_analysis: PersonalRepoAnalysis) -> str:
        """Create the charts section of the HTML file"""
        # Generate personal repository charts
        personal_charts = prepo_analysis.create_charts_section()

        # Generate organization repository charts if applicable
        org_charts = ""
        if has_org_repos and orepo_analysis:
            org_charts = orepo_analysis.create_charts_section()

        # If there are organization repositories, we'll include both sections
        # The repo_tabs_js will handle showing/hiding these sections
        if has_org_repos:
            return f"""
            <!-- Personal Repository Charts (visible by default) -->
            <div id="personal-repos-content">
                {personal_charts}
            </div>
            
            <!-- Organization Repository Charts (hidden by default) -->
            <div id="org-repos-content" class="hidden">
                {org_charts}
            </div>
            """
        else:
            # If there are no organization repositories, just return the personal charts
            return personal_charts

    def check_chart_exists(self, chart_name: str) -> bool:
        """Check if a chart file exists in the reports directory"""
        chart_path = self.reports_dir / f"{chart_name}.png"
        # Add logging to debug the issue
        logger.info(f"Checking if chart exists at: {chart_path}")
        exists = chart_path.exists()
        logger.info(f"Chart {chart_name}.png exists: {exists}")

        # Always return True to include the section with placeholder images when needed
        # The get_chart_html method will handle displaying a placeholder if the file doesn't exist
        return True

    def get_chart_html(self, chart_name: str, title: str, description: str, color_class: str) -> str:
        """Generate HTML for a chart, with fallback for missing charts"""
        chart_path = self.reports_dir / f"{chart_name}.png"
        chart_exists = chart_path.exists()

        if chart_exists:
            # Use HTML file for interactive version instead of PNG
            return f"""
            <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group transform transition-all duration-300 hover:scale-105">
                <div class="p-4">
                    <h3 class="text-lg font-medium mb-2 dark:text-white group-hover:text-{color_class} dark:group-hover:text-{color_class} transition-colors duration-300">{title}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{description}</p>
                    <div class="chart-item cursor-pointer block relative" 
                         data-chart-src="{chart_name}.html" 
                         data-chart-title="{title}" 
                         data-chart-description="{description}">
                        <div class="overflow-hidden rounded-lg">
                            <img src="{chart_name}.png" alt="{title}" class="w-full h-48 object-cover rounded-lg transform transition-transform duration-500 group-hover:scale-110" />
                        </div>
                        <div class="absolute inset-0 bg-{color_class}/0 group-hover:bg-{color_class}/10 flex items-center justify-center transition-all duration-300 rounded-lg">
                            <span class="opacity-0 group-hover:opacity-100 mt-2 inline-flex items-center bg-white/90 dark:bg-gray-800/90 px-3 py-1.5 rounded-full text-{color_class} font-medium text-sm transform translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                                View Interactive Chart
                            </span>
                        </div>
                    </div>
                </div>
            </div>"""
        else:
            logger.warning(f"Chart {chart_name} not found. Using placeholder.")
            return f"""
            <div data-aos="zoom-in" data-aos-delay="100" class="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden group">
                <div class="p-4">
                    <h3 class="text-lg font-medium mb-2 dark:text-white text-{color_class} dark:text-{color_class}">{title}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{description}</p>
                    <div class="flex items-center justify-center h-48 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <div class="text-center p-4">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto mb-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p class="text-gray-500 dark:text-gray-400">Chart not available</p>
                            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Not enough data to generate this visualization</p>
                        </div>
                    </div>
                </div>
            </div>"""

    def create_additional_charts_section(self) -> str:
        """Create the additional charts section of the HTML file"""
        # Log which charts exist before creating the section
        logger.info("Checking charts for additional section:")
        for chart_name in CHART_NAMES:
            exists = self.check_chart_exists(chart_name)
            logger.info(f"- {chart_name}: {'✓' if exists else '✗'}")

        # Define chart configurations
        chart_configs = [
            ("repository_timeline", "Repository Timeline",
             "Chronological view of repository creation and last commit dates", "primary"),
            ("repo_creation_timeline", "Repository Creation Timeline",
             "When repositories were created over time", "secondary"),
            ("quality_heatmap", "Maintenance Quality Matrix",
             "Quality factors across top repositories", "accent"),
            ("repo_types_distribution", "Repository Types",
             "Distribution of different repository types", "green-500"),
            ("commit_activity_heatmap", "Commit Activity",
             "Heatmap of commit activity by month and year", "blue-500"),
            ("top_repos_metrics", "Top Repositories",
             "Top repositories by various metrics", "purple-500"),
            ("infrastructure_metrics", "Infrastructure Metrics",
             "Analysis of repository infrastructure and quality", "pink-500"),
            ("documentation_quality", "Documentation Quality",
             "Quality of documentation across repositories", "yellow-500"),
            ("active_inactive_age", "Active vs Inactive Repos",
             "Age distribution of active vs inactive repositories", "teal-500")
        ]

        # Generate chart HTML for each configuration
        chart_html_elements = [
            self.get_chart_html(name, title, description, color)
            for name, title, description, color in chart_configs
        ]

        # Create the section with all charts
        return f"""<!-- Additional Charts Section with enhanced animations -->
                <div data-aos="fade-up" data-aos-duration="800" data-aos-delay="300" class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 transition-theme mb-10 transform hover:shadow-2xl transition-all duration-300">
                    <h2 class="text-2xl font-semibold mb-6 dark:text-white flex items-center">
                        <span class="bg-accent/10 text-accent p-2 rounded-lg mr-3">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                                            </svg>
                                        </span>
                        Additional Analysis Charts
                    </h2>

                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <!-- Timeline Chart -->
                        {chart_html_elements[0]}

                        <!-- Language Evolution -->
                        {chart_html_elements[1]}

                        <!-- Quality Heatmap -->
                        {chart_html_elements[2]}

                        <!-- Repository Types -->
                        {chart_html_elements[3]}

                        <!-- Commit Activity -->
                        {chart_html_elements[4]}

                        <!-- Top Repositories -->
                        {chart_html_elements[5]}

                        <!-- Metrics Correlation -->
                        {chart_html_elements[6]}

                        <!-- Topics Word Cloud -->
                        {chart_html_elements[7]}

                        <!-- Active vs Inactive Age -->
                        {chart_html_elements[8]}
                    </div>
                </div>"""

    @staticmethod
    def create_footer_section(timestamp: str) -> str:
        """Create the footer section of the HTML file with enhanced style and dynamic timestamp"""
        footer_section = f"""
        <!-- Footer with enhanced style and animation -->
        <div data-aos="fade-up" data-aos-duration="800" class="mt-12 text-center border-none">
            <div class="py-6 px-8 opacity-80 border-none bg-none">
                <p class="flex items-center justify-center font-medium">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3 
                        dark:text-teal-400 
                        text-teal-700
                        animate-pulse-slow 
                        opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span class="relative">
                        <span class="mr-1 opacity-100 bg-clip-text text-transparent 
                            bg-gradient-to-r from-teal-400 to-blue-500 font-semibold
                            dark:bg-gradient-to-r dark:from-teal-400 dark:to-blue-500
                            bg-gradient-to-r from-teal-500 via-cyan-400 to-blue-600
                            dark:bg-clip-text dark:text-transparent
                        ">
                            Generated with GHRepoLens
                        </span>
                        <span class="inline-block ml-1 dark:text-white">• {timestamp}</span>
                        <span class="absolute -bottom-1 left-0 w-full h-px bg-gradient-to-r from-transparent via-teal-500/50 to-transparent"></span>
                    </span>
                </p>
            </div>
        </div>
        </div>"""
        return footer_section

    @staticmethod
    def create_js_part1() -> str:
        """Create the first part of the JavaScript section of the HTML file"""
        js_part1 = """<script>
                
                // Initialize AOS animations
                document.addEventListener('DOMContentLoaded', function() {
                    AOS.init({
                        duration: 800,
                        easing: 'ease-in-out',
                        once: true,
                        mirror: false
                    });
                });

                // Initialize theme based on user preference
                if (localStorage.getItem('color-theme') === 'dark' || 
                    (!localStorage.getItem('color-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark');
                    document.getElementById('theme-toggle-light-icon').classList.remove('hidden');
                } else {
                    document.documentElement.classList.remove('dark');
                    document.getElementById('theme-toggle-dark-icon').classList.remove('hidden');
                }

                // Theme toggle functionality
                const themeToggleBtn = document.getElementById('theme-toggle');
                const themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
                const themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');

                themeToggleBtn.addEventListener('click', function() {
                    // Toggle icons
                    themeToggleDarkIcon.classList.toggle('hidden');
                    themeToggleLightIcon.classList.toggle('hidden');

                    // Toggle dark class
                    document.documentElement.classList.toggle('dark');"""

        return js_part1

    def create_js_part2(self, fig, total_repos, total_loc, total_stars, active_repos) -> str:
        """Create the second part of the JavaScript section of the HTML file"""
        js_part2 = f"""
                    // Update localStorage
                    if (document.documentElement.classList.contains('dark')) {{
                        localStorage.setItem('color-theme', 'dark');
                        // Update Plotly chart colors for dark mode
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': '{self.theme["dark_chart_bg"]}',
                            'plot_bgcolor': '{self.theme["dark_chart_bg"]}',
                            'font.color': '{self.theme["dark_text_color"]}'
                        }});
                    }} else {{
                        localStorage.setItem('color-theme', 'light');
                        // Update Plotly chart colors for light mode
                        Plotly.relayout('main-dashboard', {{
                            'paper_bgcolor': '#ffffff',
                            'plot_bgcolor': '#ffffff',
                            'font.color': '#111827'
                        }});
                    }}

                    // Update scrollbar colors based on theme
                    if (document.documentElement.classList.contains('dark')) {{
                        document.documentElement.style.setProperty('--scrollbar-track', '#374151');
                    }} else {{
                        document.documentElement.style.setProperty('--scrollbar-track', '#f1f1f1');
                    }}
                }});

                // Plot the main dashboard with animation
                var plotData = {fig.to_json()};
                
                // Config options for the plot
                const plotlyConfig = {{
                    responsive: true,
                    displayModeBar: false,  // Hide the modebar for cleaner mobile view
                    scrollZoom: false,      // Disable scroll zoom on mobile
                }};
                
                // Create the plot with proper config options
                Plotly.newPlot('main-dashboard', plotData.data, plotData.layout, plotlyConfig);
                
                // Store the dashboard figure in a global variable for access by other functions
                window.dashboardFigure = document.getElementById('main-dashboard')._fullData;
                
                // Add resize listener for responsive adjustments
                window.addEventListener('resize', function() {{
                    if (window.resizeTimer) clearTimeout(window.resizeTimer);
                    window.resizeTimer = setTimeout(function() {{
                        // Adjust modebar visibility on mobile
                        var modeBarButtons = document.querySelectorAll('.modebar-container');
                        for (var i = 0; i < modeBarButtons.length; i++) {{
                            modeBarButtons[i].style.display = (window.innerWidth <= 768) ? 'none' : 'flex';
                        }}
                    }}, 250);
                }});

                // Initialize charts with the correct theme
                if (document.documentElement.classList.contains('dark')) {{
                    Plotly.relayout('main-dashboard', {{
                        'paper_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'plot_bgcolor': '{self.theme["dark_chart_bg"]}',
                        'font.color': '{self.theme["dark_text_color"]}'
                    }});
                }}

                // Animated number counters
                function animateCounters() {{
                    // Counter animation function
                    function animateValue(element, start, end, duration) {{
                        let startTimestamp = null;
                        const step = (timestamp) => {{
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            let value = Math.floor(progress * (end - start) + start);

                            // Format with commas if needed
                            if (end > 999) {{
                                value = value.toLocaleString();
                            }}

                            element.textContent = value;
                            if (progress < 1) {{
                                window.requestAnimationFrame(step);
                            }}
                        }};
                        window.requestAnimationFrame(step);
                    }}

                    // Animate repo count
                    const repoCountElement = document.getElementById('repo-count');
                    animateValue(repoCountElement, 0, {total_repos}, 1500);

                    // Animate LOC count - parse the string value directly in JavaScript
                    const locCountElement = document.getElementById('loc-count');
                    const locValue = '{total_loc}';
                    animateValue(locCountElement, 0, parseInt(locValue.replace(/,/g, '')), 2000);

                    // Animate stars count - parse the string value directly in JavaScript
                    const starsCountElement = document.getElementById('stars-count');
                    const starsValue = '{total_stars}';
                    animateValue(starsCountElement, 0, parseInt(starsValue.replace(/,/g, '')), 2000);

                    // Animate active count
                    const activeCountElement = document.getElementById('active-count');
                    animateValue(activeCountElement, 0, {active_repos}, 1500);

                // Background HTML JS
                {self.bg_html_js}
                }}"""

        return js_part2

    @staticmethod
    def create_repo_table_js(repos_json: str) -> str:
        """Create the JavaScript section for the repository table"""
        repo_table_js = f"""
                // Repository data
                const reposData = {repos_json};
                let currentPage = 1;
                const reposPerPage = 10;
                let sortField = 'name';
                let sortDirection = 'asc';
                let filteredRepos = [...reposData];

                function initReposTable() {{
                    // Set up sorting
                    document.querySelectorAll('th[data-sort]').forEach(th => {{
                        th.addEventListener('click', () => {{
                            const field = th.getAttribute('data-sort');
                            if (sortField === field) {{
                                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                            }} else {{
                                sortField = field;
                                sortDirection = 'asc';
                            }}

                            // Reset all sort icons
                            document.querySelectorAll('.sort-icon').forEach(icon => {{
                                icon.textContent = '↕';
                            }});

                            // Update current sort icon
                            const sortIcon = th.querySelector('.sort-icon');
                            sortIcon.textContent = sortDirection === 'asc' ? '↓' : '↑';

                            renderTable();
                        }});
                    }});

                    // Set up search and filter
                    document.getElementById('repo-search').addEventListener('input', filterRepos);
                    document.getElementById('repo-filter').addEventListener('change', filterRepos);

                    // Set up pagination
                    document.getElementById('prev-page').addEventListener('click', () => {{
                        if (currentPage > 1) {{
                            currentPage--;
                            renderTable();
                        }}
                    }});

                    document.getElementById('next-page').addEventListener('click', () => {{
                        const totalPages = Math.ceil(filteredRepos.length / reposPerPage);
                        if (currentPage < totalPages) {{
                            currentPage++;
                            renderTable();
                        }}
                    }});

                    // Initial render
                    filterRepos();
                }}

                function filterRepos() {{
                    const searchTerm = document.getElementById('repo-search').value.toLowerCase();
                    const filterValue = document.getElementById('repo-filter').value;

                    filteredRepos = reposData.filter(repo => {{
                        // Apply search filter
                        const matchesSearch = 
                            repo.name.toLowerCase().includes(searchTerm) || 
                            repo.language.toLowerCase().includes(searchTerm);

                        // Apply dropdown filter
                        let matchesDropdown = true;
                        if (filterValue === 'active') matchesDropdown = repo.is_active;
                        else if (filterValue === 'inactive') matchesDropdown = !repo.is_active;
                        else if (filterValue === 'has-docs') matchesDropdown = repo.has_docs === 'Yes';
                        else if (filterValue === 'no-docs') matchesDropdown = repo.has_docs === 'No';

                        return matchesSearch && matchesDropdown;
                    }});

                    // Reset to first page
                    currentPage = 1;
                    renderTable();
                }}

                function renderTable() {{
                    // Sort repos
                    filteredRepos.sort((a, b) => {{
                        let comparison = 0;

                        if (sortField === 'name' || sortField === 'language') {{
                            comparison = String(a[sortField]).localeCompare(String(b[sortField]));
                        }} else if (sortField === 'stars' || sortField === 'loc') {{
                            comparison = Number(a[sortField]) - Number(b[sortField]);
                        }} else if (sortField === 'activity') {{
                            comparison = a.is_active === b.is_active ? 0 : a.is_active ? -1 : 1;
                        }} else if (sortField === 'maintenance') {{
                            comparison = parseFloat(a.maintenance) - parseFloat(b.maintenance);
                        }}

                        return sortDirection === 'asc' ? comparison : -comparison;
                    }});

                    // Calculate pagination
                    const totalPages = Math.ceil(filteredRepos.length / reposPerPage);
                    const startIndex = (currentPage - 1) * reposPerPage;
                    const endIndex = Math.min(startIndex + reposPerPage, filteredRepos.length);
                    const currentRepos = filteredRepos.slice(startIndex, endIndex);

                    // Update table body
                    const tableBody = document.getElementById('repos-table-body');
                    tableBody.innerHTML = '';

                    currentRepos.forEach((repo, index) => {{
                        const row = document.createElement('tr');
                        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-150';
                        row.style.animation = `slideUp ${{0.2 + index * 0.05}}s ease-out forwards`;

                        // Animate progress bar
                        const animateProgress = `style="--progress-width: ${{repo.maintenance}}%; animation: progressFill 1s ease-out forwards; animation-delay: ${{0.5 + index * 0.1}}s;"`;

                        row.innerHTML = `
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-primary">
                                <div class="flex items-center justify-between">
                                    <a href="${{repo.url}}" target="_blank" class="hover:underline hover:text-primary-dark transition-colors duration-200 flex items-center mr-2">
                                        ${{repo.name}}
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 ml-1 opacity-70" viewBox="0 0 20 20" fill="currentColor">
                                            <path fill-rule="evenodd" d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd" />
                                        </svg>
                                    </a>
                                    <button class="toggle-metadata-btn p-1 rounded-full hover:bg-primary/10 transition-colors">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 transform transition-transform metadata-arrow" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </button>
                                </div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.language}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.stars}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                                ${{repo.loc.toLocaleString()}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="${{repo.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300'}} px-2 py-1 rounded-full text-xs font-medium">
                                    ${{repo.is_active ? 'Active' : 'Inactive'}}
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                                    <div class="bg-primary h-2.5 rounded-full w-0 animate-progress" ${{animateProgress}}></div>
                                </div>
                                <span class="text-xs text-gray-600 dark:text-gray-400 mt-1 block">${{repo.maintenance}}%</span>
                            </td>
                        `;

                        tableBody.appendChild(row);
                        
                        // Create metadata row (initially hidden)
                        const metadataRow = document.createElement('tr');
                        metadataRow.className = 'metadata-row hidden';
                        
                        // Get all available metadata keys - include ALL keys
                        const metadataKeys = Object.keys(repo);
                        
                        // Group metadata into categories for better organization
                        const metadataCategories = {{
                            'Basic Info': ['name', 'description', 'url', 'default_branch', 'is_fork', 'is_archived', 'is_template', 'homepage'],
                            'Stats': ['stars', 'forks', 'watchers', 'size_kb', 'total_files', 'avg_loc_per_file', 'open_issues', 'closed_issues', 'open_prs'],
                            'Dates': ['created_at', 'updated_at', 'pushed_at', 'last_commit_date'],
                            'Development': ['primary_language', 'file_types', 'project_structure', 'is_monorepo', 'contributors_count', 'commit_frequency', 'commits_last_month', 'commits_last_year'],
                            'Quality': ['has_ci', 'has_tests', 'test_files_count', 'test_coverage_percentage', 'has_docs', 'docs_files_count', 'docs_size_category', 'readme_comprehensiveness', 'readme_line_count'],
                            'Infrastructure': ['has_deployments', 'deployment_files', 'has_packages', 'package_files', 'has_releases', 'release_count', 'dependency_files', 'cicd_files'],
                            'Community': ['license_name', 'license_spdx_id', 'topics'],
                            'Scores': ['code_quality_score', 'documentation_score', 'popularity_score', 'anomalies'],
                            'Other': []
                        }};
                        
                        // Exclude redundant keys that are already visible in the main table
                        const redundantKeys = ['language', 'loc', 'is_active', 'maintenance'];
                        
                        // Categorize metadata keys
                        let categorizedKeys = {{}};
                        metadataKeys.forEach(key => {{
                            // Skip redundant keys
                            if (redundantKeys.includes(key)) {{
                                return;
                            }}
                            
                            let placed = false;
                            
                            // Check if key belongs to a predefined category
                            for (const category in metadataCategories) {{
                                if (metadataCategories[category].includes(key)) {{
                                    if (!categorizedKeys[category]) categorizedKeys[category] = [];
                                    categorizedKeys[category].push(key);
                                    placed = true;
                                    break;
                                }}
                            }}
                            
                            // If key doesn't match any predefined category, check by name patterns
                            if (!placed) {{
                                if (key.includes('date') || key.includes('time')) {{
                                    if (!categorizedKeys['Dates']) categorizedKeys['Dates'] = [];
                                    categorizedKeys['Dates'].push(key);
                                }} else if (key.includes('count') || key.includes('number') || key.includes('size')) {{
                                    if (!categorizedKeys['Stats']) categorizedKeys['Stats'] = [];
                                    categorizedKeys['Stats'].push(key);
                                }} else if (key.includes('has_') || key.includes('is_') || key.includes('quality') || key.includes('score')) {{
                                    if (!categorizedKeys['Quality']) categorizedKeys['Quality'] = [];
                                    categorizedKeys['Quality'].push(key);
                                }} else if (key.includes('language') || key.includes('code')) {{
                                    if (!categorizedKeys['Development']) categorizedKeys['Development'] = [];
                                    categorizedKeys['Development'].push(key);
                                }} else if (key.includes('file') || key.includes('deploy') || key.includes('ci') || key.includes('package')) {{
                                    if (!categorizedKeys['Infrastructure']) categorizedKeys['Infrastructure'] = [];
                                    categorizedKeys['Infrastructure'].push(key);
                                }} else {{
                                    if (!categorizedKeys['Other']) categorizedKeys['Other'] = [];
                                    categorizedKeys['Other'].push(key);
                                }}
                            }}
                        }});
                        
                        // Create metadata row content
                        const metadataCell = document.createElement('td');
                        metadataCell.setAttribute('colspan', '6');
                        metadataCell.className = 'px-0 py-0';
                        
                        const metadataContainer = document.createElement('div');
                        metadataContainer.className = 'metadata-container bg-gray-50 dark:bg-gray-800/50 rounded-lg m-2 p-4 shadow-inner overflow-auto transition-all duration-500';
                        
                        if (metadataKeys.length > 0) {{
                            // We have metadata to display
                            const categoriesContainer = document.createElement('div');
                            categoriesContainer.className = 'space-y-4';
                            
                            // Create sections for each category
                            for (const category in categorizedKeys) {{
                                if (categorizedKeys[category] && categorizedKeys[category].length > 0) {{
                                    // Create category heading
                                    const categoryHeading = document.createElement('h3');
                                    categoryHeading.className = 'text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 border-b border-gray-200 dark:border-gray-700 pb-1';
                                    categoryHeading.textContent = category;
                                    
                                    // Create grid for this category
                                    const metadataGrid = document.createElement('div');
                                    metadataGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4';
                                    
                                    // Add each metadata item in this category
                                    categorizedKeys[category].forEach(key => {{
                                        const metadataItem = document.createElement('div');
                                        metadataItem.className = 'metadata-item p-3 bg-white/50 dark:bg-gray-700/50 rounded-lg shadow-sm hover:shadow-md transition-shadow';
                                        
                                        const metadataLabel = document.createElement('div');
                                        metadataLabel.className = 'text-xs font-medium text-gray-500 dark:text-gray-400 mb-1';
                                        metadataLabel.textContent = key.replace(/_/g, ' ').toUpperCase();
                                        
                                        const metadataValue = document.createElement('div');
                                        metadataValue.className = 'font-mono text-sm text-gray-800 dark:text-gray-200';
                                        
                                        // Format value based on metadata type
                                        if (key.includes('date') || key.includes('created_at') || key.includes('updated_at')) {{
                                            // Format dates nicely
                                            try {{
                                                const date = new Date(repo[key]);
                                                metadataValue.textContent = date.toLocaleDateString(undefined, {{ 
                                                    year: 'numeric', 
                                                    month: 'short', 
                                                    day: 'numeric'
                                                }});
                                                // Add time icon
                                                metadataValue.innerHTML = `<span class="inline-flex items-center"><svg class="w-3 h-3 mr-1 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>${{metadataValue.textContent}}</span>`;
                                            }} catch (e) {{
                                                metadataValue.textContent = repo[key];
                                            }}
                                        }} else if (key.includes('url') || key.includes('link')) {{
                                            // Format URLs as clickable links
                                            metadataValue.innerHTML = `<a href="${{repo[key]}}" target="_blank" class="text-primary hover:underline flex items-center">
                                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                                ${{ repo[key].length > 30 ? repo[key].substring(0, 30) + '...' : repo[key] }}
                                            </a>`;
                                        }} else if (key.includes('count') || key.includes('size') || key.includes('number') || key === 'stars' || key === 'loc' || key === 'forks' || key === 'issues') {{
                                            // Format numeric values
                                            metadataValue.innerHTML = `<span class="font-semibold">${{Number(repo[key]).toLocaleString()}}</span>`;
                                        }} else if (key.includes('percentage') || key.includes('ratio') || key.includes('score') || key === 'maintenance') {{
                                            // Format percentages with a progress bar
                                            const value = parseFloat(repo[key]);
                                            const color = value > 75 ? 'bg-green-500' : value > 50 ? 'bg-yellow-500' : 'bg-red-500';
                                            metadataValue.innerHTML = `
                                                <div class="flex items-center">
                                                    <span class="mr-2 font-semibold">${{value}}%</span>
                                                    <div class="flex-grow bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden">
                                                        <div class="${{color}} h-2 rounded-full" style="width: ${{value}}%"></div>
                                                    </div>
                                                </div>
                                            `;
                                        }} else if (typeof repo[key] === 'boolean' || key === 'is_active' || key === 'has_docs') {{
                                            // Format boolean values
                                            if (repo[key] === true || repo[key] === 'Yes' || repo[key] === 'yes' || repo[key] === 'true' || repo[key] === 'True') {{
                                                metadataValue.innerHTML = '<span class="inline-flex items-center text-green-600 dark:text-green-400"><svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>Yes</span>';
                                            }} else {{
                                                metadataValue.innerHTML = '<span class="inline-flex items-center text-red-600 dark:text-red-400"><svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>No</span>';
                                            }}
                                        }} else if (Array.isArray(repo[key])) {{
                                            // Format arrays as comma-separated lists with badges
                                            if (repo[key].length === 0) {{
                                                metadataValue.innerHTML = '<span class="text-gray-400 italic">None</span>';
                                            }} else {{
                                                metadataValue.innerHTML = `<div class="flex flex-wrap gap-1">
                                                    ${{repo[key].map(item => `<span class="px-2 py-0.5 rounded-full bg-primary/10 text-xs">${{item}}</span>`).join('')}}
                                                </div>`;
                                            }}
                                        }} else {{
                                            // Default formatting
                                            metadataValue.textContent = repo[key];
                                        }}
                                        
                                        metadataItem.appendChild(metadataLabel);
                                        metadataItem.appendChild(metadataValue);
                                        metadataGrid.appendChild(metadataItem);
                                    }});
                                    
                                    // Add category and its metadata to the container
                                    categoriesContainer.appendChild(categoryHeading);
                                    categoriesContainer.appendChild(metadataGrid);
                                }}
                            }}
                            
                            metadataContainer.appendChild(categoriesContainer);
                        }} else {{
                            // No metadata available
                            const noMetadataMsg = document.createElement('p');
                            noMetadataMsg.className = 'text-center text-gray-500 dark:text-gray-400 italic';
                            noMetadataMsg.textContent = 'No repository data available';
                            metadataContainer.appendChild(noMetadataMsg);
                        }}
                        
                        metadataCell.appendChild(metadataContainer);
                        metadataRow.appendChild(metadataCell);
                        tableBody.appendChild(metadataRow);
                        
                        // Add click event to toggle button
                        const toggleBtn = row.querySelector('.toggle-metadata-btn');
                        toggleBtn.addEventListener('click', (e) => {{
                            e.preventDefault();
                            const arrow = toggleBtn.querySelector('.metadata-arrow');
                            arrow.classList.toggle('rotate-180');
                            metadataRow.classList.toggle('hidden');
                            
                            // Add animation class if showing
                            if (!metadataRow.classList.contains('hidden')) {{
                                metadataContainer.classList.add('animate-chart-enter');
                            }}
                        }});
                    }});

                    // Update pagination info
                    document.getElementById('total-repos-count').textContent = filteredRepos.length;
                    document.getElementById('page-info').textContent = `Page ${{currentPage}} of ${{totalPages || 1}}`;

                    // Enable/disable pagination buttons
                    document.getElementById('prev-page').disabled = currentPage === 1;
                    document.getElementById('next-page').disabled = currentPage === totalPages || totalPages === 0;

                    // Update button styles based on disabled state
                    document.getElementById('prev-page').classList.toggle('opacity-50', currentPage === 1);
                    document.getElementById('next-page').classList.toggle('opacity-50', currentPage === totalPages || totalPages === 0);
                }}
                """
        return repo_table_js

    @staticmethod
    def create_repo_tabs_js(has_org_repos: bool) -> str:
        """Create the JavaScript for repository type tabs functionality"""
        # If there are no organization repositories, return empty JavaScript
        if not has_org_repos:
            return ""

        repo_tabs_js = """
                // Repository Type Tabs Functionality
                function initRepoTypeTabs() {
                    const personalReposTab = document.getElementById('personal-repos-tab');
                    const orgReposTab = document.getElementById('org-repos-tab');
                    const tabIndicator = document.getElementById('tab-indicator');
                    const currentViewText = document.getElementById('current-view-text');
                    const currentViewIcon = document.getElementById('current-view-icon');
                    
                    // Wait for stats counters to be fully animated before storing values
                    setTimeout(() => {
                        // Store the initial personal data state for restoration when switching back
                        window.personalData = null;
                        window.personalLayout = null;
                        window.personalTableData = null;
                        window.personalStats = {
                            repoCount: document.getElementById('repo-count').textContent,
                            locCount: document.getElementById('loc-count').textContent,
                            starsCount: document.getElementById('stars-count').textContent,
                            activeCount: document.getElementById('active-count').textContent
                        };
                        
                        // Store initial table state
                        const tableBody = document.getElementById('repos-table-body');
                        window.personalTableData = tableBody.innerHTML;
                        
                        // Store initial total repos and page info
                        window.totalReposCount = document.getElementById('total-repos-count').textContent;
                        window.pageInfo = document.getElementById('page-info').textContent;
                        
                        // Capture the initial plot data
                        const dashboardElement = document.getElementById('main-dashboard');
                        if (dashboardElement && dashboardElement.data) {
                            window.personalData = JSON.parse(JSON.stringify(dashboardElement.data));
                            window.personalLayout = JSON.parse(JSON.stringify(dashboardElement.layout));
                        }
                        
                        console.log('Personal stats stored:', window.personalStats);
                    }, 2500); // Wait for animations to complete
                    
                    // Personal icon SVG
                    const personalIconSvg = `
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    `;
                    
                    // Organization icon SVG
                    const orgIconSvg = `
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                    `;
                    
                    // Set initial tab indicator position
                    setTimeout(() => {
                        if (personalReposTab && tabIndicator) {
                            tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                        }
                    }, 100);
                    
                    // Personal repos tab click handler
                    if (personalReposTab) {
                        personalReposTab.addEventListener('click', () => {
                            // Update tab styles
                            personalReposTab.classList.add('text-gray-900', 'dark:text-white');
                            personalReposTab.classList.remove('text-gray-500', 'dark:text-gray-400');
                            
                            orgReposTab.classList.remove('text-gray-900', 'dark:text-white');
                            orgReposTab.classList.add('text-gray-500', 'dark:text-gray-400');
                            
                            // Update tab indicator
                            tabIndicator.style.left = '1px';
                            tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                            
                            // Update view text and icon
                            currentViewText.textContent = 'Viewing Personal Repository Stats';
                            currentViewIcon.innerHTML = personalIconSvg;
                            
                            // Update content
                            switchToPersonalRepos();
                        });
                    }
                    
                    // Organization repos tab click handler
                    if (orgReposTab) {
                        orgReposTab.addEventListener('click', () => {
                            // Update tab styles
                            orgReposTab.classList.add('text-gray-900', 'dark:text-white');
                            orgReposTab.classList.remove('text-gray-500', 'dark:text-gray-400');
                            
                            personalReposTab.classList.remove('text-gray-900', 'dark:text-white');
                            personalReposTab.classList.add('text-gray-500', 'dark:text-gray-400');
                            
                            // Update tab indicator
                            tabIndicator.style.left = `${personalReposTab.offsetWidth + 1}px`;
                            tabIndicator.style.width = `${orgReposTab.offsetWidth}px`;
                            
                            // Update view text and icon
                            currentViewText.textContent = 'Viewing Organization Repository Stats';
                            currentViewIcon.innerHTML = orgIconSvg;
                            
                            // Update content
                            switchToOrgRepos();
                        });
                    }
                    
                    // Function to switch to personal repos content (default view)
                    function switchToPersonalRepos() {
                        console.log('Switched to personal repositories view');
                        
                        if (!window.personalStats) {
                            console.error('Personal stats not found!');
                            return;
                        }
                        
                        console.log('Restoring personal stats:', window.personalStats);
                        
                        // Restore personal stats with animation
                        const repoCount = document.getElementById('repo-count');
                        const locCount = document.getElementById('loc-count');
                        const starsCount = document.getElementById('stars-count');
                        const activeCount = document.getElementById('active-count');
                        
                        // First store current state for animation
                        const currentRepoCount = repoCount.textContent;
                        const currentLocCount = locCount.textContent;
                        const currentStarsCount = starsCount.textContent;
                        const currentActiveCount = activeCount.textContent;
                        
                        // Clear current values
                        repoCount.textContent = '0';
                        locCount.textContent = '0';
                        starsCount.textContent = '0';
                        activeCount.textContent = '0';
                        
                        // Then animate to the saved values
                        setTimeout(() => {
                            // Animate repo count
                            animateValue(repoCount, 0, parseInt(window.personalStats.repoCount.replace(/,/g, '')), 800);
                            
                            // Animate LOC count
                            animateValue(locCount, 0, parseInt(window.personalStats.locCount.replace(/,/g, '')), 800);
                            
                            // Animate stars count
                            animateValue(starsCount, 0, parseInt(window.personalStats.starsCount.replace(/,/g, '')), 800);
                            
                            // Animate active count
                            animateValue(activeCount, 0, parseInt(window.personalStats.activeCount.replace(/,/g, '')), 800);
                        }, 100);
                        
                        // Restore original chart if we have saved data
                        if (window.personalData && window.personalLayout) {
                            const plotlyConfig = {
                                responsive: true,
                                displayModeBar: false,
                                scrollZoom: false
                            };
                            
                            Plotly.newPlot('main-dashboard', window.personalData, window.personalLayout, plotlyConfig);
                        }
                        
                        // Restore table data
                        if (window.personalTableData) {
                            document.getElementById('repos-table-body').innerHTML = window.personalTableData;
                            document.getElementById('total-repos-count').textContent = window.totalReposCount;
                            document.getElementById('page-info').textContent = window.pageInfo;
                        }
                    }
                    
                    // Function to switch to organization repos content (empty for now)
                    function switchToOrgRepos() {
                        console.log('Switched to organization repositories view');
                        
                        // Reset stats to zero with animation
                        const repoCount = document.getElementById('repo-count');
                        const locCount = document.getElementById('loc-count');
                        const starsCount = document.getElementById('stars-count');
                        const activeCount = document.getElementById('active-count');
                        
                        // First store current state for animation
                        const currentRepoCount = parseInt(repoCount.textContent.replace(/,/g, ''));
                        const currentLocCount = parseInt(locCount.textContent.replace(/,/g, ''));
                        const currentStarsCount = parseInt(starsCount.textContent.replace(/,/g, ''));
                        const currentActiveCount = parseInt(activeCount.textContent.replace(/,/g, ''));
                        
                        // Animate to zero
                        animateValue(repoCount, currentRepoCount, 0, 800);
                        animateValue(locCount, currentLocCount, 0, 800);
                        animateValue(starsCount, currentStarsCount, 0, 800);
                        animateValue(activeCount, currentActiveCount, 0, 800);
                        
                        // Clear the charts
                        Plotly.purge('main-dashboard');
                        
                        // Create empty/placeholder chart
                        const emptyLayout = {
                            height: 2000,
                            title: {
                                text: '📊 Organization Repository Analysis Dashboard - Not Implemented Yet',
                                x: 0.5
                            },
                            annotations: [{
                                text: 'Organization repositories analysis will be available soon',
                                font: {
                                    size: 20,
                                    color: document.documentElement.classList.contains('dark') ? 'white' : 'black'
                                },
                                showarrow: false,
                                xref: 'paper',
                                yref: 'paper',
                                x: 0.5,
                                y: 0.5
                            }],
                            paper_bgcolor: document.documentElement.classList.contains('dark') ? '#1f2937' : '#ffffff',
                            plot_bgcolor: document.documentElement.classList.contains('dark') ? '#1f2937' : '#ffffff'
                        };
                        
                        // Make sure to apply the same config options when creating the empty chart
                        const plotlyConfig = {
                            responsive: true,
                            displayModeBar: false,
                            scrollZoom: false
                        };
                        
                        Plotly.newPlot('main-dashboard', [], emptyLayout, plotlyConfig);
                        
                        // Clear repository table
                        document.getElementById('repos-table-body').innerHTML = '';
                        document.getElementById('total-repos-count').textContent = '0';
                        document.getElementById('page-info').textContent = 'Page 1 of 1';
                    }
                    
                    // Reuse the counter animation function
                    function animateValue(element, start, end, duration) {
                        let startTimestamp = null;
                        const step = (timestamp) => {
                            if (!startTimestamp) startTimestamp = timestamp;
                            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                            let value = Math.floor(progress * (end - start) + start);

                            // Format with commas if needed
                            if (end > 999 || start > 999) {
                                value = value.toLocaleString();
                            }

                            element.textContent = value;
                            if (progress < 1) {
                                window.requestAnimationFrame(step);
                            }
                        };
                        window.requestAnimationFrame(step);
                    }
                    
                    // Handle window resize for tab indicator
                    window.addEventListener('resize', () => {
                        if (personalReposTab && orgReposTab && tabIndicator) {
                            if (personalReposTab.classList.contains('text-gray-900') || 
                                personalReposTab.classList.contains('dark:text-white')) {
                                tabIndicator.style.left = '1px';
                                tabIndicator.style.width = `${personalReposTab.offsetWidth}px`;
                            } else {
                                tabIndicator.style.left = `${personalReposTab.offsetWidth + 1}px`;
                                tabIndicator.style.width = `${orgReposTab.offsetWidth}px`;
                            }
                        }
                    });
                }
                """
        return repo_tabs_js

    @staticmethod
    def create_js_part3(repo_table_js: str, repo_tabs_js: str) -> str:
        """Create the third part of the JavaScript section of the HTML file"""
        # Add conditional check for repo_tabs_js
        init_repo_tabs_js = """
                    // Initialize repository type tabs
                    initRepoTypeTabs();
        """ if repo_tabs_js else ""

        js_part3 = f"""
                // Initialize when DOM is loaded
                document.addEventListener('DOMContentLoaded', function() {{
                    // Start animated counters
                    animateCounters();

                    // Initialize repository table
                    initReposTable();
                    {init_repo_tabs_js}

                    // Add intersection observer for animations not handled by AOS
                    const observer = new IntersectionObserver((entries) => {{
                        entries.forEach(entry => {{
                            if (entry.isIntersecting) {{
                                entry.target.classList.add('animate-fade-in');
                                observer.unobserve(entry.target);
                            }}
                        }});
                    }}, {{ threshold: 0.1 }});

                    // Observe elements that need animation
                    document.querySelectorAll('.needs-animation').forEach(el => {{
                        observer.observe(el);
                    }});

                    // Chart Modal Functionality
                    const chartModal = document.getElementById('chartModal');
                    const chartModalIframe = document.getElementById('chartModalIframe');
                    const chartModalTitle = document.getElementById('chartModalTitle');
                    const chartModalDescription = document.getElementById('chartModalDescription');
                    const chartModalClose = document.getElementById('chartModalClose');

                    // Set up chart click handlers
                    document.querySelectorAll('.chart-item').forEach(chart => {{
                        chart.addEventListener('click', () => {{
                            openChartModal(chart);
                        }});
                    }});

                    // Handle iframe load events
                    chartModalIframe.addEventListener('load', function() {{
                        // Ensure iframe content is properly displayed
                        try {{
                            // Allow a moment for the iframe to fully render its contents
                            setTimeout(() => {{
                                // Make iframe visible with a smooth fade in
                                chartModalIframe.style.opacity = '0';
                                setTimeout(() => {{
                                    chartModalIframe.style.opacity = '1';
                                }}, 100);
                            }}, 300);
                        }} catch (e) {{
                            console.error("Error handling iframe load:", e);
                        }}
                    }});

                    function openChartModal(chartElement) {{
                        // Get chart data from dataset
                        const src = chartElement.dataset.chartSrc;
                        const title = chartElement.dataset.chartTitle;
                        const description = chartElement.dataset.chartDescription;
                        
                        console.log(`Opening modal for: ${{title}}, src: ${{src}}`);

                        // Set modal content
                        chartModalIframe.src = src;
                        chartModalTitle.textContent = title;
                        chartModalDescription.textContent = description;

                        // Show modal with animation 
                        document.body.style.overflow = 'hidden';
                        
                        // Trigger a reflow to ensure animations work properly
                        void chartModal.offsetWidth;
                        
                        // Add active class to show the modal
                        chartModal.classList.add('active');
                        
                        // Scroll to top when opening modal
                        if (chartModalIframe.parentElement) {{
                            chartModalIframe.parentElement.scrollTop = 0;
                        }}
                        
                        // Force the scrollbars to display
                        setTimeout(() => {{
                            const modalContent = document.querySelector('.chart-modal-content');
                            const iframeContainer = document.querySelector('.chart-modal-iframe-container');
                            
                            if (modalContent) {{
                                modalContent.style.overflowY = 'auto';
                                modalContent.style.display = 'block';
                            }}
                            
                            if (iframeContainer) {{
                                iframeContainer.style.overflowY = 'auto';
                                iframeContainer.style.display = 'block';
                                iframeContainer.style.height = '75vh';
                            }}
                        }}, 300);
                        
                        console.log('Modal should now be visible');
                    }}

                    function closeChartModal() {{
                        // Hide modal and restore scrolling
                        chartModal.classList.remove('active');
                        document.body.style.overflow = 'auto';
                        
                        // Clear iframe source after animation completes
                        setTimeout(() => {{
                            chartModalIframe.src = '';
                        }}, 500);
                    }}

                    // Event listeners for closing modal
                    chartModalClose.addEventListener('click', closeChartModal);
                    chartModal.addEventListener('click', (e) => {{
                        if (e.target === chartModal) {{
                            closeChartModal();
                        }}
                    }});

                    // Keyboard navigation for modal
                    document.addEventListener('keydown', (e) => {{
                        if (e.key === 'Escape' && chartModal.classList.contains('active')) {{
                            closeChartModal();
                        }}
                    }});

                    // Set CSS variables for scrollbar colors
                    document.documentElement.style.setProperty('--primary', '#4f46e5');
                    document.documentElement.style.setProperty('--scrollbar-track', '#f1f1f1');
                }});

                {repo_table_js}
                
                {repo_tabs_js}
            </script>
            </div>
        </body>
        </html>"""
        return js_part3
