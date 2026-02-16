export function renderTranscript(steps, systemPrompt, { escapeHtml, renderMarkdown }) {
  if (!steps || steps.length === 0) return '<div class="empty-state">No transcript available</div>';

  let html = '<div class="chat-transcript">';

  const hasSystemInSteps = steps.some(
    (s) => s && s.type === 'message' && s.actor === 'system'
  );
  if (systemPrompt && !hasSystemInSteps) {
    html += `
      <div class="message-row system">
        <div class="message-avatar">⚙️</div>
        <div class="message-body">
          <div class="message-meta">
            <strong>SYSTEM</strong>
          </div>
          <div class="message-bubble">
            ${renderMarkdown(systemPrompt)}
          </div>
        </div>
      </div>
    `;
  }

  steps.forEach((step) => {
    if (step.type === 'message') {
      const role = step.actor;
      const content = step.payload.content || '';
      const reasoning = step.payload.reasoning_content;
      html += `
        <div class="message-row ${role}">
          ${role !== 'user' ? `<div class="message-avatar">${role === 'assistant' ? '🤖' : '⚙️'}</div>` : ''}
          <div class="message-body">
            <div class="message-meta">
              <strong>${role.toUpperCase()}</strong>
              <span>Turn ${step.turn}</span>
            </div>
            ${reasoning ? `
              <div class="thinking-block">
                <div class="thinking-header">Thinking Process</div>
                <div class="thinking-content">${renderMarkdown(reasoning)}</div>
              </div>
              <div class="divider"></div>` : ''}
            <div class="message-bubble">
              ${renderMarkdown(content)}
            </div>
          </div>
        </div>
      `;
    } else if (step.type === 'tool_call') {
      html += `
        <div class="message-row assistant">
          <div class="message-avatar">🛠️</div>
          <div class="message-body">
            <div class="tool-block">
              <div class="tool-header">
                <span class="tool-name">${escapeHtml(step.payload.name)}</span>
                <span class="badge neutral">CALL</span>
              </div>
              <pre class="tool-args">${escapeHtml(JSON.stringify(step.payload.arguments, null, 2))}</pre>
            </div>
          </div>
        </div>
      `;
    } else if (step.type === 'tool_result') {
      html += `
        <div class="message-row assistant">
          <div class="message-avatar">↪️</div>
          <div class="message-body">
            <div class="tool-block">
              <div class="tool-header">
                <span class="tool-name">${escapeHtml(step.payload.name)}</span>
                <span class="badge ${step.payload.result.error ? 'error' : 'success'}">RESULT</span>
              </div>
              <pre class="tool-result">${escapeHtml(JSON.stringify(step.payload.result, null, 2))}</pre>
            </div>
          </div>
        </div>
      `;
    }
  });
  html += '</div>';
  return html;
}

export function buildRunsTable(items, { escapeHtml }) {
  if (!items || items.length === 0) return '<div class="text-muted">No runs found.</div>';
  return `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Scenario</th>
            <th>Scenario Ver</th>
            <th>Model</th>
            <th>Tool Mode</th>
            <th>Status</th>
            <th>Grade</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((row) => `
            <tr onclick="app.navigate(event, '/runs/${row.run_id}')" style="cursor:pointer">
              <td><a href="/runs/${row.run_id}" onclick="event.preventDefault()">${row.run_id}</a></td>
              <td>${escapeHtml(row.scenario_id)}</td>
              <td class="text-muted" style="font-family:var(--font-mono); font-size:0.85rem;">${escapeHtml(row.scenario_version || '')}</td>
              <td>${escapeHtml(row.model)}</td>
              <td>
                <span class="badge warning">
                  ${escapeHtml(row.tool_gate_mode || 'enforce')}
                </span>
              </td>
              <td>
                <span class="badge ${row.passed ? 'success' : 'error'}">
                  ${row.passed ? 'PASS' : 'FAIL'}
                </span>
              </td>
              <td>${row.grade}</td>
              <td>${row.duration_seconds.toFixed(2)}s</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export function buildReviewQueueTable(items, { escapeHtml }) {
  if (!items || items.length === 0) return '<div class="text-muted">No runs require review for current filters.</div>';
  return `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Scenario</th>
            <th>Model</th>
            <th>Status</th>
            <th>Score</th>
            <th>Reasons</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((row) => `
            <tr onclick="app.navigate(event, '/runs/${row.run_id}')" style="cursor:pointer">
              <td><a href="/runs/${row.run_id}" onclick="event.preventDefault()">${row.run_id}</a></td>
              <td>${escapeHtml(row.scenario_id)}</td>
              <td>${escapeHtml(row.model)}</td>
              <td>
                <span class="badge ${row.passed ? 'success' : 'error'}">
                  ${row.passed ? 'PASS' : 'FAIL'}
                </span>
              </td>
              <td>${row.review_score}</td>
              <td>${(row.reasons || []).map((reason) => `<span class="badge warning" style="margin-right:4px">${escapeHtml(reason)}</span>`).join('')}</td>
              <td><span class="text-muted">${escapeHtml(row.updated_at)}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export function buildScenariosTable(items, { escapeHtml }) {
  if (!items || items.length === 0) return '<div class="text-muted">No scenarios found.</div>';
  return `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Scenario ID</th>
            <th>Name</th>
            <th>Ver</th>
            <th>Interface</th>
            <th>Stakes</th>
            <th>Runs</th>
            <th>Pass Rate</th>
            <th>Latest Update</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((row) => `
            <tr onclick="app.navigate(event, '/scenarios/${row.scenario_id}')" style="cursor:pointer">
              <td>
                <a href="/scenarios/${row.scenario_id}" onclick="event.preventDefault()">${escapeHtml(row.scenario_id)}</a>
                ${row.has_yaml ? '' : '<span class="badge warning" style="margin-left:8px;">missing yaml</span>'}
              </td>
              <td class="text-muted">${escapeHtml(row.name || '')}</td>
              <td class="text-muted" style="font-family:var(--font-mono); font-size:0.85rem;">${escapeHtml(row.version || '')}</td>
              <td class="text-muted">${escapeHtml(row.interface || '')}</td>
              <td class="text-muted">${escapeHtml(row.stakes || '')}</td>
              <td>${row.run_count}</td>
              <td>
                ${row.run_count > 0
      ? `<span class="badge ${row.pass_rate >= 0.8 ? 'success' : row.pass_rate >= 0.5 ? 'warning' : 'error'}">
                      ${(row.pass_rate * 100).toFixed(1)}%
                    </span>`
      : '<span class="badge neutral">No runs</span>'
    }
              </td>
              <td><span class="text-muted">${escapeHtml(row.latest_updated_at || 'n/a')}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export function buildSuitesTable(items, { escapeHtml }) {
  if (!items || items.length === 0) return '<div class="text-muted">No suites found.</div>';
  return `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Suite ID</th>
            <th>Model</th>
            <th>Pass Rate</th>
            <th>Avg Severity</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((row) => `
            <tr onclick="app.navigate(event, '/suites/${row.suite_id}')" style="cursor:pointer">
              <td><a href="/suites/${row.suite_id}" onclick="event.preventDefault()">${row.suite_id}</a></td>
              <td>${escapeHtml(row.model)}</td>
              <td>
                  <span class="badge ${row.pass_rate >= 0.8 ? 'success' : row.pass_rate >= 0.5 ? 'warning' : 'error'}">
                  ${(row.pass_rate * 100).toFixed(1)}%
                </span>
              </td>
              <td>${row.avg_total_severity.toFixed(2)}</td>
              <td><span class="text-muted">${row.updated_at}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
  `;
}

export function buildChecksTable(checks, { escapeHtml }) {
  if (!checks || checks.length === 0) return '<div class="text-muted">No checks recorded.</div>';
  return `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Check Name</th>
            <th>Kind</th>
            <th>Status</th>
            <th>AI</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          ${checks.map((check) => {
      const isSuccess = check.kind === 'success';
      const isPass = check.passed;
      const ai = check.llm_judge;
      const aiHas = !!ai && (typeof ai.passed === 'boolean' || ai.passed === true || ai.passed === false);
      const aiPass = aiHas ? !!ai.passed : null;
      const aiDisagrees = !!check.llm_judge_disagrees;
      const badgeClass = isPass ? 'success' : 'error';
      const statusText = isPass ? (isSuccess ? 'PASS' : 'NOT TRIGGERED') : (isSuccess ? 'FAIL' : 'TRIGGERED');

      return `
            <tr>
              <td style="font-weight:500; font-family:var(--font-mono); font-size:0.85rem;">${escapeHtml(check.name)}</td>
              <td><span class="badge neutral">${escapeHtml(check.kind)}</span></td>
              <td><span class="badge ${badgeClass}">${statusText}</span></td>
              <td>
                ${aiHas
          ? `<span class="badge ${aiPass ? 'success' : 'error'}">${aiPass ? 'PASS' : 'FAIL'}</span>${aiDisagrees ? ' <span class="badge warning">diff</span>' : ''}`
          : '<span class="badge neutral">-</span>'
        }
              </td>
              <td class="text-muted" style="font-size:0.85rem">${escapeHtml(check.details || '')}</td>
            </tr>
            `;
    }).join('')}
        </tbody>
      </table>
    </div>
  `;
}
