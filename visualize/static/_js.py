from config import ThemeConfig


class JSCreator:
    def __init__(self, theme: ThemeConfig, bg_html_js: str):
        self.theme = theme
        self.bg_html_js = bg_html_js

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
                                        }} else if (key.includes('url') || key.includes('link') || key === 'homepage') {{
                                            // Format URLs as clickable links
                                            let displayText = repo[key];
                                            let isAutoGenerated = false;
                                            
                                            // Special handling for auto-generated homepage
                                            if (key === 'homepage' && repo[key] && repo[key].includes('[Auto-generated]')) {{
                                                isAutoGenerated = true;
                                                displayText = repo[key].replace('[Auto-generated] ', '');
                                            }}
                                            
                                            metadataValue.innerHTML = `<a href="${{repo[key]}}" target="_blank" class="text-primary hover:underline flex items-center">
                                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                                ${{ displayText.length > 30 ? displayText.substring(0, 30) + '...' : displayText }}
                                            </a>`;
                                            
                                            // Add auto-generated note if applicable
                                            if (isAutoGenerated) {{
                                                metadataValue.innerHTML += `<div class="text-xs text-gray-500 italic mt-1">(Auto-generated)</div>`;
                                            }}
                                        }} else if (key.includes('count') || key.includes('size') || key.includes('number') || key === 'stars' || key === 'loc' || key === 'forks' || key === 'issues') {{
                                            // Format numeric values
                                            metadataValue.innerHTML = `<span class="font-semibold">${{Number(repo[key]).toLocaleString()}}</span>`;
                                        }} else if (key.includes('percentage') || key.includes('ratio') || key.includes('score') || key === 'maintenance') {{
                                            // Format percentages with a progress bar
                                            const value = parseFloat(repo[key]);
                                            // Check if the value is NaN or null
                                            if (isNaN(value) || repo[key] === null) {{
                                                metadataValue.innerHTML = '<span class="text-gray-400 italic">N/A</span>';
                                            }} else {{
                                                const color = value > 75 ? 'bg-green-500' : value > 50 ? 'bg-yellow-500' : 'bg-red-500';
                                                metadataValue.innerHTML = `
                                                    <div class="flex items-center">
                                                        <span class="mr-2 font-semibold">${{value}}%</span>
                                                        <div class="flex-grow bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden">
                                                            <div class="${{color}} h-2 rounded-full" style="width: ${{value}}%"></div>
                                                        </div>
                                                    </div>
                                                `;
                                            }}
                                        }} else if (key === 'docs_size_category' || key === 'readme_comprehensiveness') {{
                                            // Special formatting for category strings
                                            // Make sure value is treated as a string
                                            const value = String(repo[key] || '');
                                            
                                            // Debug logging to console
                                            if (key === 'docs_size_category') {{
                                                console.log('docs_size_category for ' + repo.name + ': "' + repo[key] + '" (type: ' + typeof repo[key] + ')');
                                            }}
                                            
                                            let colorClass = 'text-gray-500';
                                            
                                            if (value === 'Comprehensive' || value === 'Big') {{
                                                colorClass = 'text-green-600 dark:text-green-400';
                                            }} else if (value === 'Good' || value === 'Intermediate') {{
                                                colorClass = 'text-yellow-600 dark:text-yellow-400';
                                            }} else if (value === 'Small') {{
                                                colorClass = 'text-orange-500 dark:text-orange-300';
                                            }} else if (value === 'None') {{
                                                colorClass = 'text-red-500 dark:text-red-300';
                                            }}
                                            
                                            metadataValue.innerHTML = `<span class="${{colorClass}} font-medium">${{value || 'N/A'}}</span>`;
                                        }} else if (key === 'file_types' || key === 'project_structure') {{
                                            // Format object as a list of key-value pairs
                                            // First, parse the JSON string back to an object
                                            let objData;
                                            try {{
                                                objData = JSON.parse(repo[key]);
                                            }} catch (e) {{
                                                objData = repo[key]; // Keep as is if not valid JSON
                                            }}
                                            
                                            if (!objData || Object.keys(objData).length === 0) {{
                                                metadataValue.innerHTML = '<span class="text-gray-400 italic">None</span>';
                                            }} else {{
                                                // Get entries and sort by value (count) in descending order
                                                const entries = Object.entries(objData).sort((a, b) => b[1] - a[1]);
                                                
                                                // Show only first 10 items initially if more than 10 exist
                                                const showAll = entries.length <= 10;
                                                const initialEntries = showAll ? entries : entries.slice(0, 10);
                                                const remainingEntries = showAll ? [] : entries.slice(10);
                                                
                                                // Create the visible items
                                                const visibleItems = initialEntries
                                                    .map(([k, v]) => `<div class="flex justify-between"><span>${{k}}</span><span class="font-semibold">${{v}}</span></div>`)
                                                    .join('');
                                                
                                                // Create the hidden items if any
                                                let hiddenItemsHtml = '';
                                                if (remainingEntries.length > 0) {{
                                                    const hiddenItems = remainingEntries
                                                        .map(([k, v]) => `<div class="flex justify-between"><span>${{k}}</span><span class="font-semibold">${{v}}</span></div>`)
                                                        .join('');
                                                    hiddenItemsHtml = `
                                                        <div class="hidden-content hidden mt-2">
                                                            ${{hiddenItems}}
                                                        </div>
                                                    `;
                                                }}
                                                
                                                // Create the read more/less toggle button if needed
                                                let toggleButtonHtml = '';
                                                if (remainingEntries.length > 0) {{
                                                    toggleButtonHtml = `
                                                        <button class="toggle-content-btn mt-2 text-xs bg-primary/10 hover:bg-primary/20 text-primary px-2 py-1 rounded-md transition-colors">
                                                            Show ${{remainingEntries.length}} more...
                                                        </button>
                                                    `;
                                                }}
                                                
                                                // Set the HTML with the content and toggle functionality
                                                metadataValue.innerHTML = `
                                                    <div class="space-y-1 max-h-40 overflow-y-auto text-xs">
                                                        <div class="visible-content">
                                                            ${{visibleItems}}
                                                        </div>
                                                        ${{hiddenItemsHtml}}
                                                        ${{toggleButtonHtml}}
                                                    </div>
                                                `;
                                                
                                                // Add event listener for the toggle button after the HTML is set
                                                if (remainingEntries.length > 0) {{
                                                    const toggleBtn = metadataValue.querySelector('.toggle-content-btn');
                                                    const hiddenContent = metadataValue.querySelector('.hidden-content');
                                                    
                                                    if (toggleBtn && hiddenContent) {{
                                                        toggleBtn.addEventListener('click', () => {{
                                                            const isHidden = hiddenContent.classList.contains('hidden');
                                                            
                                                            // Toggle visibility
                                                            hiddenContent.classList.toggle('hidden');
                                                            
                                                            // Update button text
                                                            toggleBtn.textContent = isHidden 
                                                                ? 'Show less' 
                                                                : `Show ${{remainingEntries.length}} more...`;
                                                                
                                                            // Adjust max height of parent container
                                                            const container = metadataValue.querySelector('.space-y-1');
                                                            if (container) {{
                                                                if (isHidden) {{
                                                                    container.style.maxHeight = '80vh';
                                                                }} else {{
                                                                    container.style.maxHeight = '40px';
                                                                }}
                                                            }}
                                                        }});
                                                    }}
                                                }}
                                            }}
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
