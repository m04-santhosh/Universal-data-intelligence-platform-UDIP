import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# We will inject new CSS
new_css = """
        /* Enterprise Dashboard Layout Styles */
        .dashboard-grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .recommendation-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .recommendation-list li {
            padding: 0.75rem 1rem;
            background-color: #EFF6FF;
            color: #1E3A8A;
            margin-bottom: 0.5rem;
            border-radius: 0.375rem;
            border-left: 4px solid #3B82F6;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .catalog-table, .explore-table, .nl-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }
        .catalog-table th, .explore-table th, .nl-table th {
            background-color: #F9FAFB;
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 600;
            color: #374151;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .catalog-table td, .explore-table td, .nl-table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
            color: #111827;
        }
        .catalog-table tbody tr:hover, .explore-table tbody tr:hover, .nl-table tbody tr:hover {
            background-color: #F9FAFB;
        }
        .export-buttons {
            display: flex;
            gap: 0.5rem;
        }
        .export-btn {
            background-color: white;
            border: 1px solid var(--border-color);
            color: #374151;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.875rem;
            transition: all 0.2s;
        }
        .export-btn:hover {
            background-color: #F3F4F6;
        }
        .export-btn.active {
            background-color: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        .nl-query-container {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        .nl-query-input {
            flex-grow: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            font-size: 1rem;
        }
        .nl-query-btn {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 0 1.5rem;
            border-radius: 0.375rem;
            font-weight: 600;
            cursor: pointer;
        }
        .nl-query-btn:hover {
            background-color: #4F46E5;
        }
        .explore-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .search-input {
            padding: 0.5rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            width: 300px;
        }
        .pagination-controls {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .page-btn {
            padding: 0.25rem 0.75rem;
            border: 1px solid var(--border-color);
            background: white;
            border-radius: 0.25rem;
            cursor: pointer;
        }
        .page-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .table-scroll-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
        }
"""
content = content.replace("</style>", new_css + "\n    </style>")

# We will replace the content of main > resultsSection
new_results_html = """
        <div class="results-section" id="resultsSection">
            <div class="results-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 style="margin: 0; font-size: 1.5rem;">Enterprise Data Dashboard</h2>
                <div style="display: flex; gap: 1rem; align-items: center;">
                    <span id="processingTimeDisplay" style="font-size: 0.875rem; color: #6B7280; font-weight: 500;"></span>
                    <div class="export-buttons">
                        <button class="export-btn active" id="btnExportJson">JSON</button>
                        <button class="export-btn" id="btnExportCsv">CSV</button>
                        <button class="export-btn" id="btnExportExcel">Excel</button>
                    </div>
                </div>
            </div>

            <!-- Trust Report & Quality Breakdown -->
            <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; position: relative;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <h3 style="margin: 0; font-size: 1.25rem;">Trust Report</h3>
                        <div class="tooltip-container">
                            <svg width="18" height="18" fill="none" stroke="#6B7280" viewBox="0 0 24 24" style="cursor: help;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            <div class="tooltip-text">
                                <strong>How is the score calculated?</strong><br/><br/>
                                Starts at 100.<br/>
                                • Missing values heavily reduce completeness.<br/>
                                • Minor conflicts moderately reduce consistency.<br/>
                                • Duplicates are merged successfully without penalty.<br/><br/>
                                Final score combines these metrics.
                            </div>
                        </div>
                    </div>
                    <div id="qualityScoreBadge" class="score-badge"></div>
                </div>
                
                <div class="dashboard-grid" id="scoreBreakdownGrid" style="display: grid; background-color: #F9FAFB; padding: 1rem; border-radius: 0.5rem; border: 1px solid var(--border-color); margin-top: 0;">
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase; font-weight: 600;">Completeness</div>
                        <div id="breakdownCompleteness" style="font-size: 1.25rem; font-weight: 700; color: var(--text-color); margin-top: 0.25rem;">-</div>
                    </div>
                    <div style="text-align: center; border-left: 1px solid var(--border-color); border-right: 1px solid var(--border-color);">
                        <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase; font-weight: 600;">Consistency</div>
                        <div id="breakdownConsistency" style="font-size: 1.25rem; font-weight: 700; color: var(--text-color); margin-top: 0.25rem;">-</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase; font-weight: 600;">Duplicates</div>
                        <div id="breakdownDuplicates" style="font-size: 1.25rem; font-weight: 700; color: #10B981; margin-top: 0.25rem;">-</div>
                    </div>
                </div>
            </div>

            <!-- Insights and Recommendations Layout -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem;">
                <!-- AI Insights -->
                <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Data Insights Panel</h3>
                    <div class="dashboard-grid-cards" id="insightsContainer" style="display: grid; grid-template-columns: 1fr; gap: 0.75rem;">
                        <!-- Insights injected here -->
                    </div>
                </div>

                <!-- Recommendations -->
                <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Smart Recommendations</h3>
                    <ul class="recommendation-list" id="recommendationsContainer">
                        <!-- Recommendations injected here -->
                    </ul>
                </div>
            </div>

            <!-- Data Catalog -->
            <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Data Catalog</h3>
                <div class="table-scroll-container">
                    <table class="catalog-table">
                        <thead>
                            <tr>
                                <th>Column Name</th>
                                <th>Data Type</th>
                                <th>Description</th>
                                <th>Null %</th>
                                <th>Unique Count</th>
                                <th>Sample Values</th>
                            </tr>
                        </thead>
                        <tbody id="catalogTableBody">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Natural Language Query Engine -->
            <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Natural Language Query Engine</h3>
                <form id="nlQueryForm" class="nl-query-container">
                    <input type="text" id="nlQueryInput" class="nl-query-input" placeholder="e.g. Show all customers from Bangalore, Show records where revenue > 10000...">
                    <button type="submit" class="nl-query-btn" id="nlQueryBtn">Execute Query</button>
                </form>
                <div id="nlQueryStatus" style="font-size: 0.875rem; color: #6B7280; margin-bottom: 1rem; display: none;"></div>
                <div class="table-scroll-container" id="nlTableContainer" style="display: none;">
                    <table class="nl-table">
                        <thead id="nlTableHeader"></thead>
                        <tbody id="nlTableBody"></tbody>
                    </table>
                </div>
            </div>

            <!-- Searchable Record Explorer -->
            <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Searchable Record Explorer</h3>
                <div class="explore-controls">
                    <input type="text" id="exploreSearchInput" class="search-input" placeholder="Search records...">
                    <div class="pagination-controls">
                        <span id="explorePageInfo" style="font-size: 0.875rem; color: #374151;">Page 1 of 1</span>
                        <button class="page-btn" id="explorePrevBtn" disabled>&lt; Prev</button>
                        <button class="page-btn" id="exploreNextBtn" disabled>Next &gt;</button>
                    </div>
                </div>
                <div class="table-scroll-container">
                    <table class="explore-table">
                        <thead id="exploreTableHeader"></thead>
                        <tbody id="exploreTableBody"></tbody>
                    </table>
                </div>
            </div>

            <!-- Relationship Explorer -->
            <div class="relationship-section" style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-top: 0;">
                <h3 style="margin-top: 0; font-size: 1.25rem; margin-bottom: 1rem;">Relationship Explorer</h3>
                <div id="relationshipExplorerContainer">
                    <!-- Tree cards will be injected here -->
                </div>
            </div>
            
        </div>
"""

# Extract the existing <main> wrapper to inject the new section
import re
main_match = re.search(r'<div class="results-section" id="resultsSection">.*?</main>', content, re.DOTALL)
if main_match:
    content = content[:main_match.start()] + new_results_html + "\n    </main>" + content[main_match.end():]

# Now we rewrite the javascript
new_js = """
    <script>
        const fileInput = document.getElementById('fileInput');
        const addFileBtn = document.getElementById('addFileBtn');
        const fileListContainer = document.getElementById('fileListContainer');
        const statusText = document.getElementById('statusText');
        const submitBtn = document.getElementById('submitBtn');
        const uploadForm = document.getElementById('uploadForm');
        const loader = document.getElementById('loader');
        const resultsSection = document.getElementById('resultsSection');
        const errorMessage = document.getElementById('errorMessage');
        const processingTimeDisplay = document.getElementById('processingTimeDisplay');

        // Explore state
        let currentDownloadId = null;
        let explorePage = 1;
        let exploreLimit = 100;
        let exploreSearch = '';
        let exploreSort = '';
        let exploreTotalPages = 1;

        let selectedFiles = [];

        addFileBtn.addEventListener('click', () => { fileInput.click(); });

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                selectedFiles.push(file);
                updateUI();
                fileInput.value = '';
            }
        });

        function updateUI() {
            fileListContainer.innerHTML = '';
            selectedFiles.forEach((f, index) => {
                const item = document.createElement('div');
                item.style.padding = '0.5rem';
                item.style.backgroundColor = '#F3F4F6';
                item.style.marginBottom = '0.5rem';
                item.style.borderRadius = '0.25rem';
                item.style.fontSize = '0.875rem';
                item.style.display = 'flex';
                item.style.justifyContent = 'space-between';
                item.innerHTML = `<span>File ${index + 1}: ${f.name}</span> <span style="color:#10B981; font-weight:bold;">&#10003; Added</span>`;
                fileListContainer.appendChild(item);
            });

            if (selectedFiles.length >= 3) {
                statusText.textContent = `${selectedFiles.length} files ready to process.`;
                statusText.style.color = '#10B981';
                submitBtn.disabled = false;
                errorMessage.textContent = '';
            } else {
                statusText.textContent = `Please add ${3 - selectedFiles.length} more file(s).`;
                statusText.style.color = '#6B7280';
                submitBtn.disabled = true;
            }
        }

        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (selectedFiles.length < 3) return;

            const formData = new FormData();
            selectedFiles.forEach(f => formData.append('files', f));

            submitBtn.disabled = true;
            loader.style.display = 'block';
            resultsSection.style.display = 'none';
            errorMessage.textContent = '';
            
            const startTime = performance.now();

            try {
                const response = await fetch('/api/convert', { method: 'POST', body: formData });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || errorData.detail || 'Error converting file');
                }

                const result = await response.json();
                const endTime = performance.now();
                const timeTakenMs = (endTime - startTime).toFixed(0);
                
                currentDownloadId = result.download_id;
                
                const trustReport = result.trust_report || {};
                processingTimeDisplay.textContent = `Processing Time: ${trustReport.processing_time || timeTakenMs + ' ms'}`;

                // Trust Score Badge
                const score = trustReport.quality_score || 0;
                const badge = document.getElementById('qualityScoreBadge');
                badge.textContent = `Quality Score: ${score}`;
                badge.className = 'score-badge';
                if (score >= 90) badge.classList.add('score-green');
                else if (score >= 70) badge.classList.add('score-yellow');
                else badge.classList.add('score-red');
                
                if (trustReport.score_breakdown) {
                    document.getElementById('breakdownCompleteness').textContent = trustReport.score_breakdown.completeness_score;
                    document.getElementById('breakdownConsistency').textContent = trustReport.score_breakdown.consistency_score;
                    document.getElementById('breakdownDuplicates').textContent = trustReport.score_breakdown.duplicate_score;
                }

                // AI Insights
                const insightsContainer = document.getElementById('insightsContainer');
                insightsContainer.innerHTML = '';
                if (result.data_insights) {
                    result.data_insights.forEach(insight => {
                        const div = document.createElement('div');
                        div.style.padding = '0.75rem';
                        div.style.backgroundColor = '#F9FAFB';
                        div.style.border = '1px solid #E5E7EB';
                        div.style.borderRadius = '0.375rem';
                        div.style.fontSize = '0.875rem';
                        div.style.color = '#374151';
                        div.textContent = insight;
                        insightsContainer.appendChild(div);
                    });
                }

                // Recommendations
                const recContainer = document.getElementById('recommendationsContainer');
                recContainer.innerHTML = '';
                if (result.recommendations) {
                    result.recommendations.forEach(rec => {
                        const li = document.createElement('li');
                        li.innerHTML = `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg> ${rec}`;
                        recContainer.appendChild(li);
                    });
                }

                // Data Catalog
                const catalogBody = document.getElementById('catalogTableBody');
                catalogBody.innerHTML = '';
                if (result.data_catalog) {
                    result.data_catalog.forEach(col => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td style="font-weight: 600; color: var(--primary-color);">${col.column_name}</td>
                            <td><span style="background: #E5E7EB; padding: 0.1rem 0.4rem; border-radius: 0.25rem;">${col.data_type}</span></td>
                            <td>${col.description}</td>
                            <td>
                                <div style="display:flex; align-items:center; gap:0.5rem;">
                                    <div style="flex-grow:1; height:6px; background:#E5E7EB; border-radius:3px; overflow:hidden;">
                                        <div style="height:100%; width:${col.null_percentage}%; background:${col.null_percentage > 50 ? '#EF4444' : (col.null_percentage > 0 ? '#F59E0B' : '#10B981')};"></div>
                                    </div>
                                    <span>${col.null_percentage}%</span>
                                </div>
                            </td>
                            <td>${col.unique_values}</td>
                            <td style="color: #6B7280;">${col.sample_values.join(', ')}</td>
                        `;
                        catalogBody.appendChild(tr);
                    });
                }

                // Relationship Explorer
                const relContainer = document.getElementById('relationshipExplorerContainer');
                relContainer.innerHTML = '';
                if (result.relationship_graphs && result.relationship_graphs.length > 0) {
                    result.relationship_graphs.forEach(graph => {
                        const card = document.createElement('div');
                        card.className = 'relationship-card';
                        
                        const header = document.createElement('div');
                        header.className = 'relationship-header';
                        header.innerHTML = `
                            <div class="entity-name">${graph.name || graph.entity_id}</div>
                            <div class="entity-meta">
                                <span style="background-color: #E5E7EB; padding: 0.1rem 0.5rem; border-radius: 0.25rem;">ID: ${graph.entity_id}</span>
                                <span style="background-color: #E5E7EB; padding: 0.1rem 0.5rem; border-radius: 0.25rem;">Connections: ${graph.relationship_count}</span>
                                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                            </div>
                        `;
                        const body = document.createElement('div');
                        body.className = 'tree-container';
                        let childrenHtml = '';
                        graph.children.forEach(child => { childrenHtml += `<li>${child.name}</li>`; });
                        body.innerHTML = `
                            <div class="root-node">
                                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                                ${graph.name || graph.entity_id}
                            </div>
                            <ul class="css-tree">${childrenHtml || '<li style="color: #9CA3AF; font-style: italic;">No relationships found</li>'}</ul>
                        `;
                        header.addEventListener('click', () => header.classList.toggle('open'));
                        card.appendChild(header); card.appendChild(body);
                        relContainer.appendChild(card);
                    });
                } else {
                    relContainer.innerHTML = '<p style="color: #6B7280;">No relationships discovered.</p>';
                }

                // Initial Load of Explorer Table
                loadExploreData();

                resultsSection.style.display = 'block';
            } catch (err) {
                errorMessage.textContent = err.message;
            } finally {
                loader.style.display = 'none';
                submitBtn.disabled = false;
                selectedFiles = [];
                updateUI();
            }
        });

        // Searchable Record Explorer
        async function loadExploreData() {
            if (!currentDownloadId) return;
            try {
                const params = new URLSearchParams({ page: explorePage, limit: exploreLimit });
                if (exploreSearch) params.append('search', exploreSearch);
                if (exploreSort) params.append('sort_by', exploreSort);

                const res = await fetch(`/api/explore/${currentDownloadId}?${params}`);
                const data = await res.json();
                
                if(data.success) {
                    exploreTotalPages = Math.ceil(data.total / exploreLimit) || 1;
                    document.getElementById('explorePageInfo').textContent = `Page ${data.page} of ${exploreTotalPages} (${data.total} records)`;
                    document.getElementById('explorePrevBtn').disabled = data.page <= 1;
                    document.getElementById('exploreNextBtn').disabled = data.page >= exploreTotalPages;
                    
                    const head = document.getElementById('exploreTableHeader');
                    const body = document.getElementById('exploreTableBody');
                    
                    if (data.columns && data.columns.length > 0) {
                        head.innerHTML = `<tr>${data.columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
                        body.innerHTML = data.records.map(row => {
                            return `<tr>${data.columns.map(c => `<td>${row[c] !== null ? row[c] : ''}</td>`).join('')}</tr>`;
                        }).join('');
                    }
                }
            } catch (err) { console.error("Explore API Error:", err); }
        }

        document.getElementById('exploreSearchInput').addEventListener('input', (e) => {
            exploreSearch = e.target.value;
            explorePage = 1;
            loadExploreData();
        });

        document.getElementById('explorePrevBtn').addEventListener('click', () => {
            if (explorePage > 1) { explorePage--; loadExploreData(); }
        });
        document.getElementById('exploreNextBtn').addEventListener('click', () => {
            if (explorePage < exploreTotalPages) { explorePage++; loadExploreData(); }
        });

        // NL Query Engine
        const nlForm = document.getElementById('nlQueryForm');
        const nlInput = document.getElementById('nlQueryInput');
        const nlBtn = document.getElementById('nlQueryBtn');
        const nlStatus = document.getElementById('nlQueryStatus');
        const nlContainer = document.getElementById('nlTableContainer');
        const nlHead = document.getElementById('nlTableHeader');
        const nlBody = document.getElementById('nlTableBody');

        nlForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentDownloadId) return;
            const query = nlInput.value.trim();
            if (!query) return;

            nlBtn.disabled = true;
            nlBtn.textContent = 'Executing...';
            nlStatus.style.display = 'block';
            nlStatus.textContent = 'Parsing intent and executing pandas filter...';
            nlContainer.style.display = 'none';

            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ download_id: currentDownloadId, query: query })
                });
                const data = await res.json();
                if (data.success && data.results) {
                    nlStatus.textContent = `Returned ${data.results.length} records.`;
                    if (data.results.length > 0) {
                        const cols = Object.keys(data.results[0]);
                        nlHead.innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr>`;
                        nlBody.innerHTML = data.results.map(row => {
                            return `<tr>${cols.map(c => `<td>${row[c] !== null ? row[c] : ''}</td>`).join('')}</tr>`;
                        }).join('');
                        nlContainer.style.display = 'block';
                    }
                } else {
                    nlStatus.textContent = `Error: ${data.error || 'No results'}`;
                }
            } catch (err) {
                nlStatus.textContent = `Error: ${err.message}`;
            } finally {
                nlBtn.disabled = false;
                nlBtn.textContent = 'Execute Query';
            }
        });

        // Exports
        function triggerDownload(format) {
            if (!currentDownloadId) return;
            window.location.href = `/api/download/${currentDownloadId}?format=${format}`;
        }
        document.getElementById('btnExportJson').addEventListener('click', () => triggerDownload('json'));
        document.getElementById('btnExportCsv').addEventListener('click', () => triggerDownload('csv'));
        document.getElementById('btnExportExcel').addEventListener('click', () => triggerDownload('excel'));

    </script>
</body>
</html>
"""

script_match = re.search(r'<script>.*?</script>\s*</body>\s*</html>', content, re.DOTALL)
if script_match:
    content = content[:script_match.start()] + new_js

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(content)
