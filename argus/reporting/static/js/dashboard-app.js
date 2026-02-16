import { API_BASE } from './app/constants.js';
import { fetchJSON as fetchJSONInternal } from './app/api.js';
import { escapeHtml as escapeHtmlInternal, renderMarkdown as renderMarkdownInternal } from './app/utils.js';
import {
  renderTranscript as renderTranscriptInternal,
  buildRunsTable as buildRunsTableInternal,
  buildReviewQueueTable as buildReviewQueueTableInternal,
  buildScenariosTable as buildScenariosTableInternal,
  buildSuitesTable as buildSuitesTableInternal,
  buildChecksTable as buildChecksTableInternal,
} from './app/components.js';
import {
  ackRun as ackRunAction,
  rescoreRun as rescoreRunAction,
  judgeCompareRun as judgeCompareRunAction,
  rescoreScenario as rescoreScenarioAction,
  compareFromRun as compareFromRunAction,
  startScenarioMatrixRun as startScenarioMatrixRunAction,
} from './app/actions.js';

    // Application Logic
    const app = {
      state: {
        route: '/',
        params: {},
        darkMode: window.matchMedia('(prefers-color-scheme: dark)').matches
      },

      init() {
        // Theme init
        this.state.darkMode = localStorage.getItem('theme') === 'dark' ||
          (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
        this.applyTheme();
        this.bindStaticUiEvents();

        window.addEventListener('popstate', () => this.handleRoute());
        this.handleRoute(); // Initial load
      },

      bindStaticUiEvents() {
        document.querySelectorAll('[data-nav-path]').forEach((el) => {
          el.addEventListener('click', (event) => {
            const path = el.getAttribute('data-nav-path');
            if (!path) return;
            this.navigate(event, path);
          });
        });

        const themeToggle = document.querySelector('[data-action="toggle-theme"]');
        if (themeToggle) {
          themeToggle.addEventListener('click', () => this.toggleTheme());
        }
      },

      toggleTheme() {
        this.state.darkMode = !this.state.darkMode;
        localStorage.setItem('theme', this.state.darkMode ? 'dark' : 'light');
        this.applyTheme();
      },

      applyTheme() {
        document.documentElement.classList.toggle('dark', this.state.darkMode);
        const text = document.getElementById('theme-text');
        const iconLight = document.getElementById('theme-icon-light');
        const iconDark = document.getElementById('theme-icon-dark');

        if (text) text.textContent = this.state.darkMode ? 'Light Mode' : 'Dark Mode';
        if (iconLight) iconLight.classList.toggle('hidden', !this.state.darkMode);
        if (iconDark) iconDark.classList.toggle('hidden', this.state.darkMode);
      },

      navigate(event, path) {
        if (event) event.preventDefault();
        history.pushState(null, '', path);
        this.handleRoute();
      },

      async handleRoute() {
        const path = window.location.pathname;
        this.state.route = path;

        // Update Sidebar
        document.querySelectorAll('.nav-item').forEach(el => {
          el.classList.toggle('active', path === el.dataset.route || (el.dataset.route !== '/' && path.startsWith(el.dataset.route)));
        });

        const root = document.getElementById('app-root');
        root.innerHTML = '<div class="flex-center"><div class="spinner"></div></div>'; // Loading state

        try {
          if (path === '/') {
            await this.renderDashboard(root);
          } else if (path.startsWith('/runs/')) {
            const runId = path.split('/runs/')[1];
            await this.renderRunDetail(root, runId);
          } else if (path === '/runs') {
            await this.renderRunList(root);
          } else if (path.startsWith('/compare')) {
            await this.renderCompareDetail(root);
          } else if (path === '/review-queue') {
            await this.renderReviewQueue(root);
          } else if (path.startsWith('/scenarios/')) {
            const scenarioId = path.split('/scenarios/')[1];
            if (path.endsWith('/runs')) {
              // Might handle specific sub-view, but for now reuse detail
              await this.renderScenarioDetail(root, scenarioId);
            } else {
              await this.renderScenarioDetail(root, scenarioId);
            }
          } else if (path.startsWith('/jobs/')) {
            const jobId = path.split('/jobs/')[1];
            await this.renderJobDetail(root, jobId);
          } else if (path === '/scenarios') {
            await this.renderScenarioList(root);
          } else if (path.startsWith('/suites/')) {
            const suiteId = path.split('/suites/')[1];
            await this.renderSuiteDetail(root, suiteId);
          } else if (path === '/suites') {
            await this.renderSuiteList(root);
          } else {
            root.innerHTML = '<h2>404 Not Found</h2>';
          }
        } catch (err) {
          console.error(err);
          root.innerHTML = `<div class="card"><h2>Error</h2><p>${err.message}</p></div>`;
        }
      },

      // --- Renderers ---

      async renderDashboard(root) {
        // Fetch summary data (scams logic?)
        // Currently no dedicated dashboard API. We can fetch top runs.
        const runsData = await this.fetchJSON(`${API_BASE}/runs?page_size=5`);
        const scenariosData = await this.fetchJSON(`${API_BASE}/scenarios?page_size=5`);
        const reviewQueueData = await this.fetchJSON(`${API_BASE}/review-queue?page_size=5&latest_only=true`);
        const reasonCounts = reviewQueueData.summary?.reason_counts || {};

        const html = `
          <div class="page-header">
            <h1 class="page-title">Dashboard</h1>
          </div>
          <div class="grid-stats">
            <div class="stat-card">
              <span class="stat-label">Total Scenarios</span>
              <span class="stat-value">${scenariosData.total}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Recent Runs</span>
              <span class="stat-value">${runsData.total}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Needs Review</span>
              <span class="stat-value">${reviewQueueData.total}</span>
            </div>
          </div>
          
          <div class="card">
            <h2>Recent Runs</h2>
            ${this.buildRunsTable(runsData.items)}
          </div>

          <div class="card">
            <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:12px;">
              <h2 style="margin:0;">Review Queue</h2>
              <a href="/review-queue" onclick="app.navigate(event, '/review-queue')">Open full queue &rarr;</a>
            </div>
            <div class="text-muted" style="margin-bottom:12px;">
              Reasons: ${Object.entries(reasonCounts).map(([k, v]) => `${k}=${v}`).join(' • ') || 'none'}
            </div>
            ${this.buildReviewQueueTable(reviewQueueData.items || [])}
          </div>
        `;
        root.innerHTML = html;
      },

      async renderRunList(root) {
        const urlParams = new URLSearchParams(window.location.search);
        const page = urlParams.get('page') || 1;
        const scenarioId = urlParams.get('scenario_id') || '';
        const model = urlParams.get('model') || '';
        const passed = urlParams.get('passed') || '';
        const toolMode = urlParams.get('tool_mode') || '';
        const latestOnly = urlParams.get('latest_only') || 'false';

        let apiUrl = `${API_BASE}/runs?page=${page}&page_size=25`;
        if (scenarioId) apiUrl += `&scenario_id=${encodeURIComponent(scenarioId)}`;
        if (model) apiUrl += `&model=${encodeURIComponent(model)}`;
        if (passed) apiUrl += `&passed=${passed}`;
        if (toolMode) apiUrl += `&tool_mode=${encodeURIComponent(toolMode)}`;
        if (latestOnly) apiUrl += `&latest_only=${latestOnly}`;

        const data = await this.fetchJSON(apiUrl);

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Run Reports</h1>
            <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
              <button onclick="app.rescoreRunsFromFilters(false)">Rescore Filtered</button>
              <button class="primary" onclick="app.rescoreRunsFromFilters(true)">Rescore All</button>
            </div>
          </div>
          
          <div class="card" style="margin-bottom: 16px;">
            <div class="filters">
              <div class="filter-group">
                <span class="filter-label">Scenario ID</span>
                <input type="text" id="filter-scenario" placeholder="Search..." value="${scenarioId}">
              </div>
              <div class="filter-group">
                <span class="filter-label">Model</span>
                <input type="text" id="filter-model" placeholder="Model..." value="${model}">
              </div>
              <div class="filter-group">
                <span class="filter-label">Status</span>
                <select id="filter-passed">
                  <option value="">All</option>
                  <option value="true" ${passed === 'true' ? 'selected' : ''}>Pass</option>
                  <option value="false" ${passed === 'false' ? 'selected' : ''}>Fail</option>
                </select>
              </div>
              <div class="filter-group">
                <span class="filter-label">Tool Mode</span>
                <select id="filter-tool-mode">
                  <option value="">All</option>
                  <option value="enforce" ${toolMode === 'enforce' ? 'selected' : ''}>Enforce</option>
                  <option value="raw_tools_terminate" ${toolMode === 'raw_tools_terminate' ? 'selected' : ''}>Raw (Terminate)</option>
                  <option value="allow_forbidden_tools" ${toolMode === 'allow_forbidden_tools' ? 'selected' : ''}>Allow Forbidden</option>
                </select>
              </div>
              <div class="filter-group">
                <span class="filter-label">Latest per Scenario+Model+Tool</span>
                <select id="filter-latest-only">
                  <option value="false" ${latestOnly === 'false' ? 'selected' : ''}>No</option>
                  <option value="true" ${latestOnly === 'true' ? 'selected' : ''}>Yes</option>
                </select>
              </div>
              <div class="filter-group" style="justify-content: flex-end;">
                 <button class="primary" onclick="app.applyRunFilters()">Apply Filters</button>
              </div>
            </div>
          </div>

          <div class="card">
             ${this.buildRunsTable(data.items)}
             <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
               <button ${data.page <= 1 ? 'disabled' : ''} onclick="app.changePage(${data.page - 1})">Prev</button>
               <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)} (${data.total} total)</span>
               <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} onclick="app.changePage(${data.page + 1})">Next</button>
             </div>
          </div>
        `;
      },

      applyRunFilters() {
        const scenario = document.getElementById('filter-scenario').value;
        const model = document.getElementById('filter-model').value;
        const passed = document.getElementById('filter-passed').value;
        const toolMode = document.getElementById('filter-tool-mode').value;
        const latestOnly = document.getElementById('filter-latest-only').value;
        const url = new URL(window.location);
        url.searchParams.set('page', '1');
        if (scenario) url.searchParams.set('scenario_id', scenario); else url.searchParams.delete('scenario_id');
        if (model) url.searchParams.set('model', model); else url.searchParams.delete('model');
        if (passed) url.searchParams.set('passed', passed); else url.searchParams.delete('passed');
        if (toolMode) url.searchParams.set('tool_mode', toolMode); else url.searchParams.delete('tool_mode');
        if (latestOnly) url.searchParams.set('latest_only', latestOnly); else url.searchParams.delete('latest_only');
        history.pushState(null, '', url);
        this.handleRoute();
      },

      async rescoreRunsFromFilters(ignoreFilters) {
        const scenario = document.getElementById('filter-scenario')?.value || '';
        const model = document.getElementById('filter-model')?.value || '';
        const toolMode = document.getElementById('filter-tool-mode')?.value || '';
        const passed = document.getElementById('filter-passed')?.value || '';

        if (!ignoreFilters && !scenario && !model && !toolMode && !passed) {
          if (!confirm("No filters set. Rescore everything?")) return;
          ignoreFilters = true;
        }

        const label = ignoreFilters ? "ALL runs" : "filtered runs";
        if (!confirm(`Rescore ${label} using the latest scenario YAML(s)? This updates stored scorecards.`)) return;

        try {
          // Bulk rescore supports scenario_id + model filters. (Status/tool_mode filters don't affect scoring.)
          const body = {
            reason: ignoreFilters ? 'dashboard_bulk_rescore_all' : 'dashboard_bulk_rescore_filtered',
          };
          if (!ignoreFilters && scenario) body.scenario_id = scenario;
          if (!ignoreFilters && model) body.model = model;

          const res = await fetch(`${API_BASE}/runs/rescore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          if (!res.ok) throw new Error("Failed to bulk rescore runs");
          const data = await res.json();
          const skipped = (data.skipped_runs ?? 0);
          alert(`Rescore complete. Candidate=${data.candidate_runs} Rescored=${data.rescored_runs} Skipped=${skipped} Changed=${data.changed_runs} Errors=${(data.errors || []).length}`);
          this.handleRoute();
        } catch (err) {
          alert("Error: " + err.message);
        }
      },

      async renderReviewQueue(root) {
        const urlParams = new URLSearchParams(window.location.search);
        const page = urlParams.get('page') || 1;
        const scenarioId = urlParams.get('scenario_id') || '';
        const model = urlParams.get('model') || '';
        const includePassed = urlParams.get('include_passed') || '';
        const latestOnly = urlParams.get('latest_only') || 'true';

        let apiUrl = `${API_BASE}/review-queue?page=${page}&page_size=25&latest_only=${latestOnly}`;
        if (scenarioId) apiUrl += `&scenario_id=${encodeURIComponent(scenarioId)}`;
        if (model) apiUrl += `&model=${encodeURIComponent(model)}`;
        if (includePassed) apiUrl += `&include_passed=${includePassed}`;

        const data = await this.fetchJSON(apiUrl);
        const summary = data.summary || {};
        const reasons = summary.reason_counts || {};

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Review Queue</h1>
          </div>
          
          <div class="grid-stats" style="margin-bottom:16px;">
            <div class="stat-card">
              <span class="stat-label">Queue Size</span>
              <span class="stat-value">${data.total}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Total Runs</span>
              <span class="stat-value">${summary.total_runs || 0}</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Fail Runs</span>
              <span class="stat-value">${summary.fail_runs || 0}</span>
            </div>
          </div>

          <div class="card" style="margin-bottom: 16px;">
            <div class="filters">
              <div class="filter-group">
                <span class="filter-label">Scenario ID</span>
                <input type="text" id="review-filter-scenario" placeholder="Search..." value="${scenarioId}">
              </div>
              <div class="filter-group">
                <span class="filter-label">Model</span>
                <input type="text" id="review-filter-model" placeholder="Model..." value="${model}">
              </div>
              <div class="filter-group">
                <span class="filter-label">Latest per Scenario+Model</span>
                <select id="review-filter-latest">
                  <option value="true" ${latestOnly === 'true' ? 'selected' : ''}>Yes</option>
                  <option value="false" ${latestOnly === 'false' ? 'selected' : ''}>No</option>
                </select>
              </div>
              <div class="filter-group">
                <span class="filter-label">Include Passed Clean Runs</span>
                <select id="review-filter-passed">
                  <option value="" ${!includePassed ? 'selected' : ''}>No</option>
                  <option value="true" ${includePassed === 'true' ? 'selected' : ''}>Yes</option>
                </select>
              </div>
              <div class="filter-group" style="justify-content: flex-end;">
                 <button class="primary" onclick="app.applyReviewFilters()">Apply Filters</button>
              </div>
            </div>
            <div class="text-muted">
              Reasons: ${Object.entries(reasons).map(([k, v]) => `${k}=${v}`).join(' • ') || 'none'}
            </div>
          </div>

          <div class="card">
             ${this.buildReviewQueueTable(data.items || [])}
             <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
               <button ${data.page <= 1 ? 'disabled' : ''} onclick="app.changePage(${data.page - 1})">Prev</button>
               <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)} (${data.total} total)</span>
               <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} onclick="app.changePage(${data.page + 1})">Next</button>
             </div>
          </div>
        `;
      },

      applyReviewFilters() {
        const scenario = document.getElementById('review-filter-scenario').value;
        const model = document.getElementById('review-filter-model').value;
        const latestOnly = document.getElementById('review-filter-latest').value;
        const includePassed = document.getElementById('review-filter-passed').value;

        const url = new URL(window.location);
        url.searchParams.set('page', '1');
        if (scenario) url.searchParams.set('scenario_id', scenario); else url.searchParams.delete('scenario_id');
        if (model) url.searchParams.set('model', model); else url.searchParams.delete('model');
        if (latestOnly) url.searchParams.set('latest_only', latestOnly); else url.searchParams.delete('latest_only');
        if (includePassed) url.searchParams.set('include_passed', includePassed); else url.searchParams.delete('include_passed');
        history.pushState(null, '', url);
        this.handleRoute();
      },

      async renderRunDetail(root, runId) {
        // Parallel fetch for summary and timeline
        const [runData, timelineData] = await Promise.all([
          this.fetchJSON(`${API_BASE}/runs/${runId}`),
          this.fetchJSON(`${API_BASE}/runs/${runId}/timeline`) // Handles separate timeline endpoint
        ]);

        const steps = timelineData.steps || [];
        const systemPrompt = runData.run?.runtime_summary?.setup_visible_context;
        const chatHtml = this.renderTranscript(steps, systemPrompt);

        const scenarioId = runData.scorecard?.scenario_id || runData.run?.scenario_id || '';
        const modelName = runData.scorecard?.model || runData.run?.model || '';
        const rs = runData.run?.runtime_summary || {};
        let toolGateMode = rs.tool_gate_mode || '';
        if (!toolGateMode) {
          if (rs.allow_forbidden_tools) toolGateMode = 'allow_forbidden_tools';
          else if (rs.terminate_on_blocked_tool_call) toolGateMode = 'raw_tools_terminate';
          else toolGateMode = 'enforce';
        }

        const isAcknowledged = (runData.review?.status === 'acknowledged');
        const lastRescoredAt = runData.rescoring?.last_rescored_at;
        const judgeCompare = runData.run?.runtime_summary?.llm_judge_compare;
        const judgeBadge = judgeCompare?.enabled
          ? `<span class="badge ${judgeCompare.disagreement_count > 0 ? 'warning' : 'neutral'}" style="font-size:0.9rem; padding:6px 12px;">AI Compare ${this.escapeHtml(judgeCompare.judge_model || '')}: ${judgeCompare.disagreement_count || 0} diff</span>`
          : '';

        root.innerHTML = `
           <div class="page-header">
            <h1 class="page-title">Run ${runId}</h1>
            <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
                 ${lastRescoredAt ? `<span class="badge neutral" style="font-size:0.9rem; padding:6px 12px;">Rescored ${this.escapeHtml(lastRescoredAt)}</span>` : ''}
                 ${judgeBadge}
                 <button onclick="app.rescoreRun('${runId}')">Rescore</button>
                 <button onclick="app.judgeCompareRun('${runId}')">AI Compare</button>
                 <button onclick="app.compareFromRun('${runId}')">Compare…</button>
                 ${isAcknowledged
            ? '<span class="badge success" style="font-size:0.9rem; padding:6px 12px;">Reviewed ✅</span>'
            : `<button id="btn-ack" onclick="app.ackRun('${runId}')">Mark as Reviewed</button>`
          }
            </div>
          </div>
          <div class="text-muted" style="margin-top:-6px; margin-bottom:12px;">
            ${scenarioId ? `<a href="/scenarios/${this.escapeHtml(scenarioId)}" onclick="app.navigate(event, '/scenarios/${this.escapeHtml(scenarioId)}')">&larr; Back to ${this.escapeHtml(scenarioId)}</a>` : ''}
          </div>
          <div class="grid-stats">
             <div class="stat-card">
               <span class="stat-label">Status</span>
               <span class="stat-value">${runData.scorecard.passed ? '<span class=trend-up>PASS</span>' : '<span class=trend-down>FAIL</span>'}</span>
             </div>
             <div class="stat-card">
               <span class="stat-label">Grade</span>
               <span class="stat-value">${runData.scorecard.grade}</span>
             </div>
             <div class="stat-card">
               <span class="stat-label">Checks Passed</span>
                <span class="stat-value">${runData.scorecard.checks.filter(c => c.passed).length}/${runData.scorecard.checks.length}</span>
             </div>
             <div class="stat-card">
               <span class="stat-label">Model</span>
               <span class="stat-value" style="font-family:var(--font-mono); font-size:0.95rem; line-height:1.1;">${this.escapeHtml(modelName || 'unknown')}</span>
             </div>
             <div class="stat-card">
               <span class="stat-label">Tool Mode</span>
               <span class="stat-value" style="font-family:var(--font-mono); font-size:0.95rem; line-height:1.1;">${this.escapeHtml(toolGateMode || 'enforce')}</span>
             </div>
          </div>
          
           <div class="card" style="margin-top:16px">
             <h2>Checks</h2>
             ${this.buildChecksTable(runData.scorecard.checks)}
           </div>

           <div class="card" style="margin-top:16px">
              <h2>Transcript</h2>
              ${chatHtml}
           </div>
        `;
      },

      async renderCompareDetail(root) {
        const url = new URL(window.location);
        const left = (url.searchParams.get('left') || '').trim();
        const right = (url.searchParams.get('right') || '').trim();

        const controls = `
          <div class="card" style="margin-bottom:16px;">
            <div class="compare-controls">
              <div class="filter-group" style="min-width: 240px;">
                <span class="filter-label">Left run_id</span>
                <input id="cmp-left" type="text" placeholder="e.g. ef4386b7" value="${this.escapeHtml(left)}">
              </div>
              <div class="filter-group" style="min-width: 240px;">
                <span class="filter-label">Right run_id</span>
                <input id="cmp-right" type="text" placeholder="e.g. a9f157e5" value="${this.escapeHtml(right)}">
              </div>
              <div class="filter-group">
                <button class="primary" onclick="app.applyCompare()">Load</button>
              </div>
              <div class="filter-group">
                <button onclick="app.swapCompare()">Swap</button>
              </div>
            </div>
            <div class="text-muted" style="margin-top:10px;">
              Tip: open any run and click <span class="badge neutral">Compare…</span>.
            </div>
          </div>
        `;

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Compare Runs</h1>
          </div>
          ${controls}
          <div id="cmp-body"></div>
        `;

        if (!left || !right) {
          const body = document.getElementById('cmp-body');
          body.innerHTML = `<div class="card"><div class="text-muted">Enter two run ids to compare.</div></div>`;
          return;
        }

        await this.loadCompareInto(left, right);
      },

      async loadCompareInto(left, right) {
        const body = document.getElementById('cmp-body');
        body.innerHTML = '<div class="flex-center"><div class="spinner"></div></div>';

        const [a, b, aTl, bTl] = await Promise.all([
          this.fetchJSON(`${API_BASE}/runs/${encodeURIComponent(left)}`),
          this.fetchJSON(`${API_BASE}/runs/${encodeURIComponent(right)}`),
          this.fetchJSON(`${API_BASE}/runs/${encodeURIComponent(left)}/timeline`),
          this.fetchJSON(`${API_BASE}/runs/${encodeURIComponent(right)}/timeline`),
        ]);

        const aScore = a.scorecard || {};
        const bScore = b.scorecard || {};
        const aRun = a.run || {};
        const bRun = b.run || {};

        const scenarioA = aScore.scenario_id || aRun.scenario_id || '';
        const scenarioB = bScore.scenario_id || bRun.scenario_id || '';
        const modelA = aScore.model || aRun.model || '';
        const modelB = bScore.model || bRun.model || '';

        const checksA = Array.isArray(aScore.checks) ? aScore.checks : [];
        const checksB = Array.isArray(bScore.checks) ? bScore.checks : [];
        const byNameA = new Map(checksA.filter(x => x && x.name).map(x => [String(x.name), x]));
        const byNameB = new Map(checksB.filter(x => x && x.name).map(x => [String(x.name), x]));
        const names = Array.from(new Set([...byNameA.keys(), ...byNameB.keys()])).sort();

        const checkRows = names.map(name => {
          const ca = byNameA.get(name) || null;
          const cb = byNameB.get(name) || null;
          const aPass = ca ? !!ca.passed : null;
          const bPass = cb ? !!cb.passed : null;
          const differs = (ca && cb) ? (aPass !== bPass) : false;
          const kind = (ca?.kind || cb?.kind || '').toString();
          const detailsA = (ca?.details || '').toString();
          const detailsB = (cb?.details || '').toString();
          return `
            <tr>
              <td style="font-family:var(--font-mono); font-size:0.85rem;">${this.escapeHtml(name)}</td>
              <td><span class="badge neutral">${this.escapeHtml(kind)}</span></td>
              <td>${ca ? `<span class="badge ${aPass ? 'success' : 'error'}">${aPass ? 'PASS' : 'FAIL'}</span>` : `<span class="badge neutral">-</span>`}</td>
              <td>${cb ? `<span class="badge ${bPass ? 'success' : 'error'}">${bPass ? 'PASS' : 'FAIL'}</span>` : `<span class="badge neutral">-</span>`}</td>
              <td>${differs ? `<span class="badge warning">diff</span>` : `<span class="badge neutral">same</span>`}</td>
              <td class="text-muted" style="font-size:0.85rem">${differs ? `<span class="diff">${this.escapeHtml(detailsA || detailsB || '')}</span>` : this.escapeHtml(detailsA || detailsB || '')}</td>
            </tr>
          `;
        }).join('');

        const summary = `
          <div class="grid-stats" style="margin-bottom:16px;">
            <div class="stat-card">
              <span class="stat-label">Left</span>
              <span class="stat-value" style="font-family:var(--font-mono); font-size:1.05rem;">${this.escapeHtml(left)}</span>
              <div class="text-muted" style="margin-top:6px;">${this.escapeHtml(modelA)}</div>
              <div class="text-muted">${this.escapeHtml(scenarioA)}</div>
            </div>
            <div class="stat-card">
              <span class="stat-label">Right</span>
              <span class="stat-value" style="font-family:var(--font-mono); font-size:1.05rem;">${this.escapeHtml(right)}</span>
              <div class="text-muted" style="margin-top:6px;">${this.escapeHtml(modelB)}</div>
              <div class="text-muted">${this.escapeHtml(scenarioB)}</div>
            </div>
            <div class="stat-card">
              <span class="stat-label">Status</span>
              <span class="stat-value" style="font-size:1.2rem;">
                <span class="badge ${aScore.passed ? 'success' : 'error'}">${aScore.passed ? 'LEFT PASS' : 'LEFT FAIL'}</span>
                <span style="margin:0 6px;"></span>
                <span class="badge ${bScore.passed ? 'success' : 'error'}">${bScore.passed ? 'RIGHT PASS' : 'RIGHT FAIL'}</span>
              </span>
            </div>
          </div>
        `;

        body.innerHTML = `
          ${summary}
          <div class="card" style="margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
              <h2 style="margin:0;">Checks Diff</h2>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <a href="/runs/${this.escapeHtml(left)}" onclick="app.navigate(event, '/runs/${this.escapeHtml(left)}')">Open left run</a>
                <span class="text-muted">•</span>
                <a href="/runs/${this.escapeHtml(right)}" onclick="app.navigate(event, '/runs/${this.escapeHtml(right)}')">Open right run</a>
              </div>
            </div>
            <div class="table-container" style="margin-top:12px;">
              <table>
                <thead>
                  <tr>
                    <th>Check</th>
                    <th>Kind</th>
                    <th>Left</th>
                    <th>Right</th>
                    <th>Δ</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>${checkRows || ''}</tbody>
              </table>
            </div>
          </div>

          <div class="compare-grid">
            <div class="card">
              <h2 style="margin-top:0;">Left Transcript</h2>
              ${this.renderTranscript((aTl.steps || []), aRun?.runtime_summary?.setup_visible_context)}
            </div>
            <div class="card">
              <h2 style="margin-top:0;">Right Transcript</h2>
              ${this.renderTranscript((bTl.steps || []), bRun?.runtime_summary?.setup_visible_context)}
            </div>
          </div>
        `;
      },

      applyCompare() {
        const left = (document.getElementById('cmp-left')?.value || '').trim();
        const right = (document.getElementById('cmp-right')?.value || '').trim();
        const url = new URL(window.location);
        if (left) url.searchParams.set('left', left); else url.searchParams.delete('left');
        if (right) url.searchParams.set('right', right); else url.searchParams.delete('right');
        history.pushState(null, '', url);
        this.handleRoute();
      },

      swapCompare() {
        const leftEl = document.getElementById('cmp-left');
        const rightEl = document.getElementById('cmp-right');
        if (!leftEl || !rightEl) return;
        const tmp = leftEl.value;
        leftEl.value = rightEl.value;
        rightEl.value = tmp;
      },

      compareFromRun(runId) {
        return compareFromRunAction(this, runId);
      },

      async renderScenarioList(root) {
        // Fetch a large page so the UI shows the full scenario library by default.
        const data = await this.fetchJSON(`${API_BASE}/scenarios?page=1&page_size=500`);

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Scenarios</h1>
          </div>
          <div class="card">
             ${this.buildScenariosTable(data.items)}
          </div>
        `;
      },

      async renderScenarioDetail(root, scenarioId) {
        const urlParams = new URLSearchParams(window.location.search);
        const model = urlParams.get('model') || '';
        const passed = urlParams.get('passed') || '';
        const toolMode = urlParams.get('tool_mode') || '';
        const latestOnly = urlParams.get('latest_only') || 'true';

        let apiUrl = `${API_BASE}/scenarios/${scenarioId}/runs?page=1&page_size=100&latest_only=${latestOnly}`;
        if (model) apiUrl += `&model=${encodeURIComponent(model)}`;
        if (passed) apiUrl += `&passed=${passed}`;
        if (toolMode) apiUrl += `&tool_mode=${encodeURIComponent(toolMode)}`;

        const [data, modelsData, jobsData, scenarioMeta] = await Promise.all([
          this.fetchJSON(apiUrl),
          this.fetchJSON(`${API_BASE}/models`),
          this.fetchJSON(`${API_BASE}/scenarios/${scenarioId}/jobs?page=1&page_size=10`),
          this.fetchJSON(`${API_BASE}/scenarios/${scenarioId}`).catch(() => null),
        ]);
        const models = (modelsData.items || []).map(x => x.model);
        const jobs = (jobsData.items || []);
        const meta = scenarioMeta || {};
        const targets = meta.targets || [];
        const knobs = meta.knobs || {};
        const visibleContext = meta.setup?.visible_context || '';
        const hiddenTruth = meta.setup?.hidden_truth || '';
        const promptSequence = meta.prompt_sequence || [];
        root.innerHTML = `
            <div class="page-header">
                <div style="display:flex; flex-direction:column; gap:6px;">
                  <h1 class="page-title" style="margin:0;">${scenarioId}</h1>
                  ${meta.name ? `<div class="text-muted" style="font-size:0.95rem;">${this.escapeHtml(meta.name)}</div>` : ''}
                </div>
                <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
                  <button onclick="app.rescoreScenario('${scenarioId}')">Rescore Scenario</button>
                </div>
            </div>
            <div class="card">
                <div style="margin-bottom: 16px;">
                  <a href="/scenarios" onclick="app.navigate(event, '/scenarios')">&larr; Back to Scenarios</a>
                </div>
                <div class="card" style="margin-bottom:16px;">
                  <div style="display:flex; gap:10px; align-items:flex-start; justify-content:space-between; flex-wrap:wrap;">
                    <div style="min-width: 280px; flex:1;">
                      <div class="text-muted" style="margin-bottom:8px;">Scenario</div>
                      ${meta.description ? `<div class="prose">${this.renderMarkdown(meta.description)}</div>` : `<div class="text-muted">No description found.</div>`}
                    </div>
                    <div style="min-width: 260px; display:flex; flex-direction:column; gap:10px;">
                      <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                        ${meta.version ? `<span class="badge neutral" style="padding:6px 10px; font-family:var(--font-mono);">v${this.escapeHtml(meta.version)}</span>` : ''}
                        ${meta.interface ? `<span class="badge neutral" style="padding:6px 10px;">${this.escapeHtml(meta.interface)}</span>` : ''}
                        ${meta.stakes ? `<span class="badge ${meta.stakes === 'high' ? 'warning' : 'neutral'}" style="padding:6px 10px;">stakes: ${this.escapeHtml(meta.stakes)}</span>` : ''}
                      </div>
                      ${targets && targets.length ? `
                        <div>
                          <div class="text-muted" style="margin-bottom:6px;">Targets</div>
                          <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                            ${targets.map(t => `<span class="badge neutral" style="padding:6px 10px;">${this.escapeHtml(String(t))}</span>`).join('')}
                          </div>
                        </div>
                      ` : ''}
                    </div>
                  </div>
                  ${(Object.keys(knobs || {}).length || visibleContext || hiddenTruth || (promptSequence && promptSequence.length)) ? `
                    <div style="margin-top:12px;">
                      ${Object.keys(knobs || {}).length ? `
                        <details style="margin-bottom:10px;">
                          <summary class="text-muted" style="cursor:pointer;">Knobs</summary>
                          <pre class="tool-result">${this.escapeHtml(JSON.stringify(knobs, null, 2))}</pre>
                        </details>
                      ` : ''}
                      ${visibleContext ? `
                        <details style="margin-bottom:10px;">
                          <summary class="text-muted" style="cursor:pointer;">Setup: Visible Context (sent to model)</summary>
                          <pre class="tool-result">${this.escapeHtml(visibleContext)}</pre>
                        </details>
                      ` : ''}
                      ${hiddenTruth ? `
                        <details style="margin-bottom:10px;">
                          <summary class="text-muted" style="cursor:pointer;">Setup: Hidden Truth (not sent to model)</summary>
                          <pre class="tool-result">${this.escapeHtml(hiddenTruth)}</pre>
                        </details>
                      ` : ''}
                      ${promptSequence && promptSequence.length ? `
                        <details>
                          <summary class="text-muted" style="cursor:pointer;">Prompt Sequence (${promptSequence.length})</summary>
                          <div style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">
                            ${promptSequence.map((t, idx) => `
                              <div class="card" style="padding:12px;">
                                <div class="text-muted" style="margin-bottom:6px; font-family:var(--font-mono);">${idx + 1}. ${this.escapeHtml(t.role || '')}</div>
                                <div class="prose">${this.renderMarkdown(t.content || '')}</div>
                              </div>
                            `).join('')}
                          </div>
                        </details>
                      ` : ''}
                    </div>
                  ` : ''}
                </div>
                <div class="card" style="margin-bottom:16px;">
                  <h2 style="margin-top:0;">Run Matrix</h2>
                  <div class="text-muted" style="margin-bottom:12px;">Run this scenario across selected models and tool modes from the dashboard.</div>
                  <div class="filters">
                    <div class="filter-group" style="min-width:260px;">
                      <span class="filter-label">Models</span>
                      <div id="matrix-models" style="display:flex; gap:8px; flex-wrap:wrap;">
                        ${(models || []).map(m => `
                          <label class="badge neutral" style="cursor:pointer; padding:6px 10px;">
                            <input type="checkbox" class="matrix-model" value="${this.escapeHtml(m)}" checked style="margin-right:6px; vertical-align:middle;">
                            <span style="font-family:var(--font-mono); font-size:0.8rem;">${this.escapeHtml(m)}</span>
                          </label>
                        `).join('')}
                      </div>
                    </div>
                    <div class="filter-group">
                      <span class="filter-label">Tool Modes</span>
                      <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <label class="badge neutral" style="cursor:pointer; padding:6px 10px;">
                          <input type="checkbox" class="matrix-tool-mode" value="enforce" checked style="margin-right:6px; vertical-align:middle;"> enforce
                        </label>
                        <label class="badge neutral" style="cursor:pointer; padding:6px 10px;">
                          <input type="checkbox" class="matrix-tool-mode" value="raw_tools_terminate" checked style="margin-right:6px; vertical-align:middle;"> raw_tools_terminate
                        </label>
                        <label class="badge neutral" style="cursor:pointer; padding:6px 10px;">
                          <input type="checkbox" class="matrix-tool-mode" value="allow_forbidden_tools" checked style="margin-right:6px; vertical-align:middle;"> allow_forbidden_tools
                        </label>
                      </div>
                    </div>
                    <div class="filter-group">
                      <span class="filter-label">AI Compare</span>
                      <label style="display:flex; align-items:center; gap:8px;">
                        <input type="checkbox" id="matrix-ai-compare">
                        <span class="text-muted">Use MiniMax-M2.5</span>
                      </label>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;">
                      <button class="primary" onclick="app.startScenarioMatrixRun('${scenarioId}')">Run</button>
                    </div>
                  </div>
                  ${jobs.length ? `
                    <div style="margin-top:12px;">
                      <div class="text-muted" style="margin-bottom:8px;">Recent jobs</div>
                      <div class="table-container">
                        <table>
                          <thead>
                            <tr>
                              <th>Job</th>
                              <th>Status</th>
                              <th>Progress</th>
                              <th>Updated</th>
                            </tr>
                          </thead>
                          <tbody>
                            ${jobs.map(j => `
                              <tr onclick="app.navigate(event, '/jobs/${j.job_id}')" style="cursor:pointer">
                                <td style="font-family:var(--font-mono); font-size:0.85rem;">${this.escapeHtml(j.job_id)}</td>
                                <td><span class="badge ${String(j.status||'').includes('error') ? 'error' : (j.status==='done' ? 'success' : 'warning')}">${this.escapeHtml(j.status||'')}</span></td>
                                <td class="text-muted">${(j.completed_runs||0)}/${(j.total_runs||0)}</td>
                                <td class="text-muted">${this.escapeHtml(j.updated_at||'')}</td>
                              </tr>
                            `).join('')}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ` : ''}
                </div>
                <div class="filters" style="margin-bottom:12px;">
                  <div class="filter-group">
                    <span class="filter-label">Model</span>
                    <input type="text" id="scenario-filter-model" placeholder="Model..." value="${model}">
                  </div>
                  <div class="filter-group">
                    <span class="filter-label">Status</span>
                    <select id="scenario-filter-passed">
                      <option value="">All</option>
                      <option value="true" ${passed === 'true' ? 'selected' : ''}>Pass</option>
                      <option value="false" ${passed === 'false' ? 'selected' : ''}>Fail</option>
                    </select>
                  </div>
                  <div class="filter-group">
                    <span class="filter-label">Tool Mode</span>
                    <select id="scenario-filter-tool-mode">
                      <option value="">All</option>
                      <option value="enforce" ${toolMode === 'enforce' ? 'selected' : ''}>Enforce</option>
                      <option value="raw_tools_terminate" ${toolMode === 'raw_tools_terminate' ? 'selected' : ''}>Raw (Terminate)</option>
                      <option value="allow_forbidden_tools" ${toolMode === 'allow_forbidden_tools' ? 'selected' : ''}>Allow Forbidden</option>
                    </select>
                  </div>
                  <div class="filter-group">
                    <span class="filter-label">Latest per Model+Tool</span>
                    <select id="scenario-filter-latest">
                      <option value="true" ${latestOnly === 'true' ? 'selected' : ''}>Yes</option>
                      <option value="false" ${latestOnly === 'false' ? 'selected' : ''}>No</option>
                    </select>
                  </div>
                  <div class="filter-group" style="justify-content:flex-end;">
                    <button class="primary" onclick="app.applyScenarioRunFilters('${scenarioId}')">Apply</button>
                  </div>
                </div>
                <h2>Runs</h2>
                ${this.buildRunsTable(data.items)}
            </div>
          `;
      },

      async renderJobDetail(root, jobId) {
        const data = await this.fetchJSON(`${API_BASE}/jobs/${jobId}`);
        const runs = (data.run_ids || []).slice().reverse();
        const cur = data.current_run || null;
        const inFlight = data.in_flight || [];
        const models = data.models || [];
        const toolModes = data.tool_modes || [];
        const matrix = data.matrix_items || [];
        const conc = data.concurrency || null;

        const fmtDur = (s) => {
          if (s === null || s === undefined) return '';
          const v = Number(s);
          if (!Number.isFinite(v)) return '';
          return `${v.toFixed(v >= 10 ? 1 : 2)}s`;
        };

        const cellFor = (model, toolMode) => {
          const found = matrix.find(x => x.model === model && x.tool_mode === toolMode);
          if (!found) return `<span class="text-muted">n/a</span>`;
          if (found.run) {
            const r = found.run;
            const badge = r.passed ? 'success' : 'error';
            const label = r.passed ? 'PASS' : 'FAIL';
            const grade = r.grade || '?';
            const dur = fmtDur(r.duration_seconds);
            const runId = r.run_id || '';
            return `
              <div style="display:flex; flex-direction:column; gap:6px;">
                <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                  <span class="badge ${badge}" style="padding:4px 10px;">${label}</span>
                  <span class="badge neutral" style="padding:4px 10px;">${this.escapeHtml(String(grade))}</span>
                  ${dur ? `<span class="text-muted">${this.escapeHtml(dur)}</span>` : ''}
                </div>
                ${runId ? `<a href="/runs/${this.escapeHtml(runId)}" onclick="app.navigate(event, '/runs/${this.escapeHtml(runId)}')" style="font-family:var(--font-mono); font-size:0.9rem;">${this.escapeHtml(runId)}</a>` : ''}
              </div>
            `;
          }
          if (found.error) {
            return `<span class="badge error" style="padding:4px 10px;">error</span><div class="text-muted" style="margin-top:6px;">${this.escapeHtml(String(found.error).slice(0, 140))}</div>`;
          }
          if (data.status === 'running') {
            return `<span class="badge warning" style="padding:4px 10px;">pending</span>`;
          }
          return `<span class="text-muted">missing</span>`;
        };

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Job ${this.escapeHtml(jobId)}</h1>
          </div>
          <div class="card">
            <div style="margin-bottom: 16px;">
              <a href="/scenarios/${this.escapeHtml(data.scenario_id)}" onclick="app.navigate(event, '/scenarios/${this.escapeHtml(data.scenario_id)}')">&larr; Back to Scenario</a>
            </div>
            <div class="grid-stats" style="margin-bottom: 16px;">
              <div class="stat-card">
                <span class="stat-label">Status</span>
                <span class="stat-value" style="font-size:1.2rem;">${this.escapeHtml(data.status||'')}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Progress</span>
                <span class="stat-value" style="font-size:1.2rem;">${(data.completed_runs||0)}/${(data.total_runs||0)}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">AI Compare</span>
                <span class="stat-value" style="font-size:1.2rem;">${data.ai_compare ? this.escapeHtml(data.judge_model||'') : 'off'}</span>
              </div>
            </div>
            <div class="text-muted" style="margin-bottom:12px;">Updated: ${this.escapeHtml(data.updated_at||'')}</div>
            ${cur ? `
              <div class="card" style="margin: 12px 0;">
                <div class="text-muted" style="margin-bottom:8px;">Current</div>
                <div style="font-family:var(--font-mono); font-size:0.9rem;">
                  #${this.escapeHtml(cur.index)} model=${this.escapeHtml(cur.model)} tool_mode=${this.escapeHtml(cur.tool_mode)} seed=${this.escapeHtml(cur.seed)}
                </div>
              </div>
            ` : ''}
            ${inFlight && inFlight.length ? `
              <div class="card" style="margin: 12px 0;">
                <div class="text-muted" style="margin-bottom:8px;">In Flight (${inFlight.length})</div>
                <div style="display:flex; flex-wrap:wrap; gap:8px;">
                  ${inFlight.slice(0, 12).map(x => `
                    <span class="badge neutral" style="padding:6px 10px; font-family:var(--font-mono); font-size:0.8rem;">
                      #${this.escapeHtml(x.index)} ${this.escapeHtml(x.model)} ${this.escapeHtml(x.tool_mode)}
                    </span>
                  `).join('')}
                </div>
              </div>
            ` : ''}
            ${conc ? `
              <div class="text-muted" style="margin: 6px 0 12px;">
                Concurrency: per_provider=${this.escapeHtml(String(conc.per_provider||''))}, max_workers=${this.escapeHtml(String(conc.max_workers||''))}, queue=${this.escapeHtml(String(conc.queue_strategy||''))}
              </div>
            ` : ''}
            <h2>Matrix</h2>
            <div class="text-muted" style="margin-bottom:10px;">
              Rows=models, columns=tool modes. Click a run id to open the run detail.
            </div>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    ${(toolModes || []).map(tm => `<th style="font-family:var(--font-mono); font-size:0.85rem;">${this.escapeHtml(tm)}</th>`).join('')}
                  </tr>
                </thead>
                <tbody>
                  ${(models || []).map(m => `
                    <tr>
                      <td style="font-family:var(--font-mono); font-size:0.85rem; white-space:nowrap;">${this.escapeHtml(m)}</td>
                      ${(toolModes || []).map(tm => `<td>${cellFor(m, tm)}</td>`).join('')}
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
            ${runs.length ? `
              <div style="margin-top:12px;">
                <details>
                  <summary class="text-muted" style="cursor:pointer;">Raw run list (${runs.length})</summary>
                  <div class="table-container" style="margin-top:8px;">
                    <table>
                      <thead><tr><th>Run ID</th></tr></thead>
                      <tbody>
                        ${runs.map(rid => `
                          <tr onclick="app.navigate(event, '/runs/${rid}')" style="cursor:pointer">
                            <td style="font-family:var(--font-mono); font-size:0.9rem;"><a href="/runs/${rid}" onclick="event.preventDefault()">${rid}</a></td>
                          </tr>
                        `).join('')}
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
            ` : ''}
            ${data.errors && data.errors.length ? `
              <h2 style="margin-top:16px;">Errors</h2>
              <pre class="tool-result">${this.escapeHtml(JSON.stringify(data.errors, null, 2))}</pre>
            ` : ''}
            <div style="margin-top:12px;">
              <button onclick="app.handleRoute()">Refresh</button>
            </div>
          </div>
        `;
      },

      applyScenarioRunFilters(scenarioId) {
        const model = document.getElementById('scenario-filter-model').value;
        const passed = document.getElementById('scenario-filter-passed').value;
        const toolMode = document.getElementById('scenario-filter-tool-mode').value;
        const latestOnly = document.getElementById('scenario-filter-latest').value;

        const url = new URL(window.location);
        if (model) url.searchParams.set('model', model); else url.searchParams.delete('model');
        if (passed) url.searchParams.set('passed', passed); else url.searchParams.delete('passed');
        if (toolMode) url.searchParams.set('tool_mode', toolMode); else url.searchParams.delete('tool_mode');
        if (latestOnly) url.searchParams.set('latest_only', latestOnly); else url.searchParams.delete('latest_only');
        history.pushState(null, '', url);
        this.handleRoute();
      },

      async startScenarioMatrixRun(scenarioId) {
        return startScenarioMatrixRunAction(this, scenarioId);
      },

      async renderSuiteList(root) {
        const urlParams = new URLSearchParams(window.location.search);
        const page = urlParams.get('page') || 1;
        const data = await this.fetchJSON(`${API_BASE}/suites?page=${page}&page_size=25`);

        root.innerHTML = `
          <div class="page-header">
            <h1 class="page-title">Suites</h1>
          </div>
          <div class="card">
             ${this.buildSuitesTable(data.items)}
             <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
               <button ${data.page <= 1 ? 'disabled' : ''} onclick="app.changePage(${data.page - 1})">Prev</button>
               <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)}</span>
               <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} onclick="app.changePage(${data.page + 1})">Next</button>
             </div>
          </div>
        `;
      },

      async renderSuiteDetail(root, suiteId) {
        const data = await this.fetchJSON(`${API_BASE}/suites/${suiteId}`);
        root.innerHTML = `
            <div class="page-header">
                <h1 class="page-title">Suite: ${suiteId}</h1>
            </div>
            <div class="card">
                <div style="margin-bottom: 16px;">
                  <a href="/suites" onclick="app.navigate(event, '/suites')">&larr; Back to Suites</a>
                </div>
                <div class="grid-stats" style="margin-bottom: 16px;">
                  <div class="stat-card">
                    <span class="stat-label">Model</span>
                    <span class="stat-value" style="font-size: 1.2rem;">${data.model}</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-label">Pass Rate</span>
                    <span class="stat-value">${(data.summary.pass_rate * 100).toFixed(1)}%</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-label">Avg. Severity</span>
                    <span class="stat-value">${data.summary.avg_total_severity.toFixed(2)}</span>
                  </div>
                </div>
                <h2>Runs</h2>
                ${this.buildRunsTable(data.runs.map(r => ({ ...r, ...r.scorecard })))}
            </div>
          `;
      },

      // --- Components ---

      renderTranscript(steps, systemPrompt) {
        return renderTranscriptInternal(steps, systemPrompt, {
          escapeHtml: this.escapeHtml.bind(this),
          renderMarkdown: this.renderMarkdown.bind(this),
        });
      },

      buildRunsTable(items) {
        return buildRunsTableInternal(items, { escapeHtml: this.escapeHtml.bind(this) });
      },

      buildReviewQueueTable(items) {
        return buildReviewQueueTableInternal(items, { escapeHtml: this.escapeHtml.bind(this) });
      },

      buildScenariosTable(items) {
        return buildScenariosTableInternal(items, { escapeHtml: this.escapeHtml.bind(this) });
      },

      buildSuitesTable(items) {
        return buildSuitesTableInternal(items, { escapeHtml: this.escapeHtml.bind(this) });
      },

      buildChecksTable(checks) {
        return buildChecksTableInternal(checks, { escapeHtml: this.escapeHtml.bind(this) });
      },

      // --- Utility ---

      async fetchJSON(url) {
        return fetchJSONInternal(url);
      },

      renderMarkdown(text) {
        return renderMarkdownInternal(text, { escapeHtml: this.escapeHtml.bind(this) });
      },

      escapeHtml(str) {
        return escapeHtmlInternal(str);
      },

      async ackRun(runId) {
        return ackRunAction(this, runId);
      },

      async rescoreRun(runId) {
        return rescoreRunAction(this, runId);
      },

      async judgeCompareRun(runId) {
        return judgeCompareRunAction(this, runId);
      },

      async rescoreScenario(scenarioId) {
        return rescoreScenarioAction(this, scenarioId);
      },

      changePage(newPage) {
        const url = new URL(window.location);
        url.searchParams.set('page', newPage);
        history.pushState(null, '', url);
        this.handleRoute();
      }
    };

    window.app = app;

    // Boostrap
    document.addEventListener('DOMContentLoaded', () => app.init());
