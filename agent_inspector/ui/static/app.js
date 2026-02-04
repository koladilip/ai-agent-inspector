// API base URL
        const API_BASE = '/v1';

        // State
        let currentRunId = null;
        let currentEventId = null;
        let runs = [];

        // DOM elements
        const runList = document.getElementById('runList');
        const timeline = document.getElementById('timeline');
        const detailView = document.getElementById('detailView');
        const searchInput = document.getElementById('searchInput');
        const statusFilter = document.getElementById('statusFilter');
        const eventTypeFilter = document.getElementById('eventTypeFilter');
        const themeToggle = document.getElementById('themeToggle');

        // Load runs on page load
        window.addEventListener('load', () => {
            initTheme();
            loadRuns();
        });

        // Search input debounce
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => filterRuns(), 300);
        });

        // Filter change handlers
        statusFilter.addEventListener('change', filterRuns);
        eventTypeFilter.addEventListener('change', () => {
            if (currentRunId) {
                loadTimeline(currentRunId);
            }
        });

        async function loadRuns() {
            try {
                const response = await fetch(`${API_BASE}/runs?limit=100`);
                const data = await response.json();
                runs = data.runs || [];
                renderRuns(runs);
            } catch (error) {
                runList.innerHTML = '<li class="error">Failed to load runs</li>';
                console.error('Error loading runs:', error);
            }
        }

        function renderRuns(runsToRender) {
            if (runsToRender.length === 0) {
                runList.innerHTML = '<li class="loading" style="padding: 40px;">No runs found</li>';
                return;
            }

            runList.innerHTML = runsToRender.map(run => `
                <li class="run-item ${currentRunId === run.id ? 'active' : ''}"
                    data-run-id="${run.id}"
                    onclick="selectRun('${run.id}')">
                    <div class="run-name">${escapeHtml(run.name || 'Unnamed Run')}</div>
                    <div class="run-meta">
                        ${formatTimestamp(run.started_at)}
                        <span class="run-status ${run.status}">${run.status}</span>
                    </div>
                </li>
            `).join('');
        }

        function filterRuns() {
            const searchTerm = searchInput.value.toLowerCase();
            const status = statusFilter.value;

            const filtered = runs.filter(run => {
                const matchesSearch = !searchTerm ||
                    (run.name && run.name.toLowerCase().includes(searchTerm));
                const matchesStatus = !status || run.status === status;
                return matchesSearch && matchesStatus;
            });

            renderRuns(filtered);
        }

        async function selectRun(runId) {
            currentRunId = runId;

            // Update UI
            document.querySelectorAll('.run-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.runId === runId) {
                    item.classList.add('active');
                }
            });

            // Clear detail view
            detailView.innerHTML = '<div class="detail-empty">Loading...</div>';

            // Load timeline
            await loadTimeline(runId);
        }

        async function loadTimeline(runId) {
            try {
                timeline.innerHTML = '<div class="loading">Loading timeline...</div>';

                const response = await fetch(`${API_BASE}/runs/${runId}/timeline`);
                const data = await response.json();
                const events = data.events || [];

                renderTimeline(events);
            } catch (error) {
                timeline.innerHTML = '<div class="error">Failed to load timeline</div>';
                console.error('Error loading timeline:', error);
            }
        }

        function renderTimeline(events) {
            if (events.length === 0) {
                timeline.innerHTML = '<div class="loading">No events in this run</div>';
                return;
            }

            const eventTypeFilter = document.getElementById('eventTypeFilter').value;
            const filteredEvents = eventTypeFilter
                ? events.filter(e => e.type === eventTypeFilter)
                : events;

            if (filteredEvents.length === 0) {
                timeline.innerHTML = '<div class="loading">No events match filter</div>';
                return;
            }

            timeline.innerHTML = `
                <div class="event-connector"></div>
                ${filteredEvents.map(event => `
                    <div class="timeline-event"
                         onclick="showEventDetail('${event.id}')"
                         data-event-id="${event.id}">
                        <div class="event-icon ${event.type}">
                            ${getEventIcon(event.type)}
                        </div>
                        <div class="event-content">
                            <div class="event-type">${formatEventType(event.type)}</div>
                            <div class="event-timestamp">${formatTimestamp(event.timestamp)}</div>
                            <div class="event-summary">${getEventSummary(event)}</div>
                        </div>
                    </div>
                `).join('')}
            `;
        }

        async function showEventDetail(eventId) {
            currentEventId = eventId;

            try {
                const response = await fetch(`${API_BASE}/runs/${currentRunId}/steps/${eventId}/data`);
                const data = await response.json();

                renderEventDetail(data.data);
            } catch (error) {
                detailView.innerHTML = '<div class="error">Failed to load event details</div>';
                console.error('Error loading event details:', error);
            }
        }

        function renderEventDetail(event) {
            if (!event) {
                detailView.innerHTML = '<div class="detail-empty">No event data</div>';
                return;
            }

            const sections = [];
            const richBlocks = [];

            // Basic info
            sections.push({
                label: 'Event ID',
                value: event.event_id || 'N/A'
            });

            sections.push({
                label: 'Type',
                value: formatEventType(event.type)
            });

            sections.push({
                label: 'Timestamp',
                value: formatTimestamp(event.timestamp_ms)
            });

            sections.push({
                label: 'Status',
                value: event.status || 'N/A'
            });

            if (event.duration_ms !== undefined) {
                sections.push({
                    label: 'Duration',
                    value: `${event.duration_ms}ms`
                });
            }

            // Type-specific details
            if (event.type === 'llm_call') {
                if (event.model) {
                    sections.push({ label: 'Model', value: event.model });
                }
                if (event.prompt) {
                    const parsed = parseMaybeJson(event.prompt);
                    if (parsed && Array.isArray(parsed)) {
                        richBlocks.push({
                            label: 'Prompt',
                            html: renderChatMessages(parsed)
                        });
                    } else {
                        sections.push({ label: 'Prompt', value: event.prompt });
                    }
                }
                if (event.response) {
                    sections.push({ label: 'Response', value: event.response });
                }
                if (event.total_tokens) {
                    sections.push({ label: 'Tokens', value: event.total_tokens.toString() });
                }
            } else if (event.type === 'tool_call') {
                if (event.tool_name) {
                    sections.push({ label: 'Tool', value: event.tool_name });
                }
                if (event.tool_args) {
                    sections.push({
                        label: 'Arguments',
                        value: JSON.stringify(event.tool_args, null, 2)
                    });
                }
                if (event.tool_result) {
                    sections.push({
                        label: 'Result',
                        value: JSON.stringify(event.tool_result, null, 2)
                    });
                }
            } else if (event.type === 'memory_read' || event.type === 'memory_write') {
                if (event.memory_key) {
                    sections.push({ label: 'Key', value: event.memory_key });
                }
                if (event.memory_value) {
                    sections.push({
                        label: 'Value',
                        value: JSON.stringify(event.memory_value, null, 2)
                    });
                }
            } else if (event.type === 'error') {
                if (event.error_type) {
                    sections.push({ label: 'Error Type', value: event.error_type });
                }
                if (event.error_message) {
                    sections.push({ label: 'Message', value: event.error_message });
                }
            } else if (event.type === 'final_answer') {
                if (event.answer) {
                    sections.push({ label: 'Answer', value: event.answer });
                }
            }

            // Metadata
            if (event.metadata && Object.keys(event.metadata).length > 0) {
                sections.push({
                    label: 'Metadata',
                    value: JSON.stringify(event.metadata, null, 2)
                });
            }

            // Render sections
            const sectionHtml = sections.map(section => `
                <div class="detail-section">
                    <div class="detail-label">${escapeHtml(section.label)}</div>
                    <div class="detail-value">${escapeHtml(section.value)}</div>
                </div>
            `).join('');

            const richHtml = richBlocks.map(block => `
                <div class="detail-section">
                    <div class="detail-label">${escapeHtml(block.label)}</div>
                    <div class="detail-chat">${block.html}</div>
                </div>
            `).join('');

            detailView.innerHTML = richHtml + sectionHtml;
        }

        function getEventIcon(type) {
            const icons = {
                'llm_call': '🤖',
                'tool_call': '🔧',
                'memory_read': '📖',
                'memory_write': '✍️',
                'error': '❌',
                'final_answer': '✅',
                'run_start': '▶️'
            };
            return icons[type] || '📌';
        }

        function formatEventType(type) {
            return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }

        function getEventSummary(event) {
            switch (event.type) {
                case 'llm_call':
                    return event.model ? `Model: ${event.model}` : 'LLM Call';
                case 'tool_call':
                    return event.tool_name ? `Tool: ${event.tool_name}` : 'Tool Call';
                case 'memory_read':
                    return event.memory_key ? `Read: ${event.memory_key}` : 'Memory Read';
                case 'memory_write':
                    return event.memory_key ? `Write: ${event.memory_key}` : 'Memory Write';
                case 'error':
                    return event.error_message || 'Error occurred';
                case 'final_answer':
                    return event.answer ? event.answer.substring(0, 50) + '...' : 'Final answer';
                default:
                    return event.name || event.type;
            }
        }

        function formatTimestamp(ms) {
            const date = new Date(ms);
            return date.toLocaleString();
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function initTheme() {
            const saved = localStorage.getItem('agent_inspector_theme') || 'auto';
            applyTheme(saved);
            themeToggle.addEventListener('click', cycleTheme);
        }

        function cycleTheme() {
            const current = localStorage.getItem('agent_inspector_theme') || 'auto';
            const next = current === 'auto' ? 'light' : current === 'light' ? 'dark' : 'auto';
            applyTheme(next);
        }

        function applyTheme(theme) {
            const root = document.documentElement;
            root.classList.remove('theme-light', 'theme-dark');
            if (theme === 'light') {
                root.classList.add('theme-light');
            } else if (theme === 'dark') {
                root.classList.add('theme-dark');
            }
            localStorage.setItem('agent_inspector_theme', theme);
            const label = theme === 'auto'
                ? 'Theme: Auto'
                : `Theme: ${theme[0].toUpperCase()}${theme.slice(1)}`;
            themeToggle.textContent = label;
        }

        function parseMaybeJson(text) {
            try {
                return JSON.parse(text);
            } catch (e) {
                return null;
            }
        }

        function renderChatMessages(messages) {
            return messages.map(msg => `
                <div class="chat-row ${escapeHtml(msg.role || 'unknown')}">
                    <div class="chat-role">${escapeHtml(msg.role || 'unknown')}</div>
                    <div class="chat-content">${escapeHtml(msg.content || '')}</div>
                </div>
            `).join('');
        }
