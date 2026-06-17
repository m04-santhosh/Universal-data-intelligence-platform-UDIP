import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject CSS
new_css = """
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-height: 400px;
            overflow-y: auto;
            padding: 1rem;
            background-color: #F9FAFB;
            border-radius: 0.5rem;
            border: 1px solid var(--border-color);
            margin-bottom: 1rem;
        }
        .chat-bubble {
            max-width: 80%;
            padding: 1rem;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            line-height: 1.4;
        }
        .chat-bubble.user {
            background-color: var(--primary-color);
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 0;
        }
        .chat-bubble.ai {
            background-color: white;
            color: #111827;
            align-self: flex-start;
            border-bottom-left-radius: 0;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        .suggested-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        .chip {
            background-color: #E0E7FF;
            color: #3730A3;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid #C7D2FE;
            transition: all 0.2s;
        }
        .chip:hover {
            background-color: #C7D2FE;
        }
        .ai-result-table {
            width: 100%;
            margin-top: 1rem;
            border-collapse: collapse;
            font-size: 0.75rem;
        }
        .ai-result-table th {
            background-color: #F3F4F6;
            padding: 0.5rem;
            border: 1px solid var(--border-color);
        }
        .ai-result-table td {
            padding: 0.5rem;
            border: 1px solid var(--border-color);
        }
"""
content = content.replace("</style>", new_css + "\n    </style>")


# 2. Replace HTML section
old_html_regex = r'<!-- Natural Language Query Engine -->.*?<!-- Searchable Record Explorer -->'

new_html = """<!-- ASK YOUR DATA AI Engine -->
            <div style="background-color: white; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
                    <svg width="24" height="24" fill="none" stroke="var(--primary-color)" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                    <h3 style="margin: 0; font-size: 1.25rem;">Ask Your Data AI</h3>
                </div>
                
                <div class="suggested-chips">
                    <span class="chip" onclick="document.getElementById('aiQueryInput').value='How many customers exist?'; document.getElementById('aiQueryBtn').click();">How many customers exist?</span>
                    <span class="chip" onclick="document.getElementById('aiQueryInput').value='Show duplicate records'; document.getElementById('aiQueryBtn').click();">Show duplicate records</span>
                    <span class="chip" onclick="document.getElementById('aiQueryInput').value='Top customers by revenue'; document.getElementById('aiQueryBtn').click();">Top customers by revenue</span>
                    <span class="chip" onclick="document.getElementById('aiQueryInput').value='Customers with missing values'; document.getElementById('aiQueryBtn').click();">Customers with missing values</span>
                    <span class="chip" onclick="document.getElementById('aiQueryInput').value='Count customers by city'; document.getElementById('aiQueryBtn').click();">Count customers by city</span>
                </div>

                <div class="chat-container" id="chatContainer">
                    <div class="chat-bubble ai">
                        <strong>AI Assistant:</strong> Hello! I'm your Enterprise Data AI. Ask me any question about your newly generated dataset.
                    </div>
                </div>

                <form id="aiQueryForm" class="nl-query-container" style="margin-bottom: 0;">
                    <input type="text" id="aiQueryInput" class="nl-query-input" placeholder="Ask a question in plain English...">
                    <button type="submit" class="nl-query-btn" id="aiQueryBtn">Ask</button>
                </form>
            </div>

            <!-- Searchable Record Explorer -->"""

content = re.sub(old_html_regex, new_html, content, flags=re.DOTALL)


# 3. Replace JS Section
old_js_regex = r'// NL Query Engine.*?// Exports'

new_js = """// Ask Your Data AI
        const aiForm = document.getElementById('aiQueryForm');
        const aiInput = document.getElementById('aiQueryInput');
        const aiBtn = document.getElementById('aiQueryBtn');
        const chatContainer = document.getElementById('chatContainer');

        function appendChatBubble(text, sender, isHtml = false) {
            const bubble = document.createElement('div');
            bubble.className = `chat-bubble ${sender}`;
            if (isHtml) {
                bubble.innerHTML = text;
            } else {
                bubble.textContent = text;
            }
            chatContainer.appendChild(bubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        aiForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentDownloadId) {
                appendChatBubble("Please upload and process data first.", 'ai');
                return;
            }
            const query = aiInput.value.trim();
            if (!query) return;

            appendChatBubble(query, 'user');
            aiInput.value = '';
            aiBtn.disabled = true;
            aiBtn.textContent = 'Thinking...';

            const loadingBubble = document.createElement('div');
            loadingBubble.className = 'chat-bubble ai';
            loadingBubble.innerHTML = '<span style="color:#6B7280; font-style:italic;">Analyzing query intent and executing...</span>';
            chatContainer.appendChild(loadingBubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const res = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ download_id: currentDownloadId, query: query })
                });
                const data = await res.json();
                
                chatContainer.removeChild(loadingBubble);

                if (data.success) {
                    let aiResponseHtml = `<div style="margin-bottom: 0.5rem;"><strong>Answer:</strong> `;
                    
                    if (data.result_type === 'scalar') {
                        aiResponseHtml += `<span style="font-size: 1.125rem; font-weight: 600; color: var(--primary-color);">${data.result}</span></div>`;
                    } else if (data.result_type === 'dataframe') {
                        const arr = Array.isArray(data.result) ? data.result : [];
                        aiResponseHtml += `Found ${arr.length} records.</div>`;
                        if (arr.length > 0) {
                            const cols = Object.keys(arr[0]);
                            let tableHtml = `<div style="max-height: 200px; overflow-y: auto; margin-bottom: 0.5rem;"><table class="ai-result-table"><thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>`;
                            arr.slice(0, 100).forEach(row => {
                                tableHtml += `<tr>${cols.map(c => `<td>${row[c] !== null ? row[c] : ''}</td>`).join('')}</tr>`;
                            });
                            tableHtml += `</tbody></table></div>`;
                            if (arr.length > 100) tableHtml += `<div style="font-size: 0.75rem; color: #6B7280;">Showing first 100 records.</div>`;
                            aiResponseHtml += tableHtml;
                        }
                    }

                    let confColor = data.confidence >= 90 ? '#10B981' : (data.confidence >= 70 ? '#F59E0B' : '#EF4444');

                    aiResponseHtml += `
                        <div style="background: #F3F4F6; padding: 0.75rem; border-radius: 0.375rem; margin-top: 0.5rem; font-size: 0.75rem;">
                            <div style="margin-bottom: 0.25rem;"><strong>Execution Logic:</strong> <code style="background: #E5E7EB; padding: 0.1rem 0.25rem; border-radius: 0.25rem; color: #374151;">${data.interpretation || 'N/A'}</code></div>
                            <div style="margin-bottom: 0.25rem;"><strong>Insight:</strong> ${data.insight || 'None'}</div>
                            <div><strong>Confidence:</strong> <span style="color: ${confColor}; font-weight: 600;">${data.confidence || 0}%</span></div>
                        </div>
                    `;

                    appendChatBubble(aiResponseHtml, 'ai', true);
                } else {
                    appendChatBubble(`Error: ${data.error || 'Failed to process query'}`, 'ai');
                }
            } catch (err) {
                if (chatContainer.contains(loadingBubble)) chatContainer.removeChild(loadingBubble);
                appendChatBubble(`Error: ${err.message}`, 'ai');
            } finally {
                aiBtn.disabled = false;
                aiBtn.textContent = 'Ask';
            }
        });

        // Exports"""

content = re.sub(old_js_regex, new_js, content, flags=re.DOTALL)

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(content)
