from config import ThemeConfig


class CSSCreator:
    def __init__(self, theme: ThemeConfig, bg_html_css: str):
        self.theme = theme
        self.bg_html_css = bg_html_css

    def create_tailwindcss_config(self) -> str:
        return f""""
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
        """

    def create_css_style(self) -> str:
        return f""""
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
        """
