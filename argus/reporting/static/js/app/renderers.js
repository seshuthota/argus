import { API_BASE } from './constants.js';

export async function renderDashboard(app, root) {
  const runsData = await app.fetchJSON(`${API_BASE}/runs?page_size=5`);
  const scenariosData = await app.fetchJSON(`${API_BASE}/scenarios?page_size=5`);
  const reviewQueueData = await app.fetchJSON(`${API_BASE}/review-queue?page_size=5&latest_only=true`);
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
      ${app.buildRunsTable(runsData.items)}
    </div>

    <div class="card">
      <div style="display:flex; justify-content: space-between; align-items:center; margin-bottom:12px;">
        <h2 style="margin:0;">Review Queue</h2>
        <a href="/review-queue" data-nav-path="/review-queue">Open full queue &rarr;</a>
      </div>
      <div class="text-muted" style="margin-bottom:12px;">
        Reasons: ${Object.entries(reasonCounts).map(([k, v]) => `${k}=${v}`).join(' • ') || 'none'}
      </div>
      ${app.buildReviewQueueTable(reviewQueueData.items || [])}
    </div>
  `;
  root.innerHTML = html;
}

export async function renderRunList(app, root) {
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

  const data = await app.fetchJSON(apiUrl);

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Run Reports</h1>
      <div style="margin-left:auto; display:flex; gap:8px; align-items:center;">
        <button data-action="rescore-filtered-runs">Rescore Filtered</button>
        <button class="primary" data-action="rescore-all-runs">Rescore All</button>
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
            <button class="primary" data-action="apply-run-filters">Apply Filters</button>
        </div>
      </div>
    </div>

    <div class="card">
      ${app.buildRunsTable(data.items)}
      <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
        <button ${data.page <= 1 ? 'disabled' : ''} data-action="change-page" data-page="${data.page - 1}">Prev</button>
        <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)} (${data.total} total)</span>
        <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} data-action="change-page" data-page="${data.page + 1}">Next</button>
      </div>
    </div>
  `;
}

export async function renderReviewQueue(app, root) {
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

  const data = await app.fetchJSON(apiUrl);
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
            <button class="primary" data-action="apply-review-filters">Apply Filters</button>
        </div>
      </div>
      <div class="text-muted">
        Reasons: ${Object.entries(reasons).map(([k, v]) => `${k}=${v}`).join(' • ') || 'none'}
      </div>
    </div>

    <div class="card">
      ${app.buildReviewQueueTable(data.items || [])}
      <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
        <button ${data.page <= 1 ? 'disabled' : ''} data-action="change-page" data-page="${data.page - 1}">Prev</button>
        <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)} (${data.total} total)</span>
        <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} data-action="change-page" data-page="${data.page + 1}">Next</button>
      </div>
    </div>
  `;
}

export async function renderScenarioList(app, root) {
  const data = await app.fetchJSON(`${API_BASE}/scenarios?page=1&page_size=500`);

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Scenarios</h1>
    </div>
    <div class="card">
      ${app.buildScenariosTable(data.items)}
    </div>
  `;
}

export async function renderSuiteList(app, root) {
  const urlParams = new URLSearchParams(window.location.search);
  const page = urlParams.get('page') || 1;
  const data = await app.fetchJSON(`${API_BASE}/suites?page=${page}&page_size=25`);

  root.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Suites</h1>
    </div>
    <div class="card">
      ${app.buildSuitesTable(data.items)}
      <div class="pagination" style="margin-top: 16px; display: flex; gap: 8px;">
        <button ${data.page <= 1 ? 'disabled' : ''} data-action="change-page" data-page="${data.page - 1}">Prev</button>
        <span style="align-self:center">Page ${data.page} of ${Math.ceil(data.total / data.page_size)}</span>
        <button ${data.page * data.page_size >= data.total ? 'disabled' : ''} data-action="change-page" data-page="${data.page + 1}">Next</button>
      </div>
    </div>
  `;
}
