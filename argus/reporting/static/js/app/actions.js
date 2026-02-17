import { API_BASE } from './constants.js';

export async function ackRun(app, runId) {
  if (!confirm('Mark this run as reviewed? It will be removed from the active queue.')) return;

  const btn = document.getElementById('btn-ack');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/runs/${runId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'acknowledge' }),
    });
    if (!res.ok) throw new Error('Failed to acknowledge run');
    app.navigate(null, '/review-queue');
  } catch (err) {
    alert('Error: ' + err.message);
    if (btn) btn.disabled = false;
  }
}

export async function rescoreRun(app, runId) {
  if (!confirm('Rescore this run using the latest scenario YAML?')) return;
  try {
    const res = await fetch(`${API_BASE}/runs/${runId}/rescore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'dashboard_rescore' }),
    });
    if (!res.ok) throw new Error('Failed to rescore run');
    app.handleRoute();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

export async function judgeCompareRun(app, runId) {
  if (!confirm('Run AI Compare for this run using MiniMax-M2.5? This will call the model and may cost money.')) return;
  try {
    const res = await fetch(`${API_BASE}/runs/${runId}/judge-compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ judge_model: 'MiniMax-M2.5' }),
    });
    if (!res.ok) throw new Error('Failed to run AI compare');
    app.handleRoute();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

export async function rescoreScenario(app, scenarioId) {
  if (!confirm(`Rescore all runs for ${scenarioId} using the latest scenario YAML?`)) return;
  try {
    const res = await fetch(`${API_BASE}/scenarios/${scenarioId}/rescore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'dashboard_bulk_rescore' }),
    });
    if (!res.ok) throw new Error('Failed to rescore scenario');
    const data = await res.json();
    const skipped = (data.skipped_runs ?? 0);
    alert(`Rescore complete. Candidate=${data.candidate_runs} Rescored=${data.rescored_runs} Skipped=${skipped} Changed=${data.changed_runs} Errors=${(data.errors || []).length}`);
    app.handleRoute();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

export function compareFromRun(app, runId) {
  const other = prompt('Compare this run against run_id:');
  if (!other) return;
  const url = new URL(window.location.origin + '/compare');
  url.searchParams.set('left', runId);
  url.searchParams.set('right', other.trim());
  app.navigate(null, url.pathname + url.search);
}

export async function startScenarioMatrixRun(app, scenarioId) {
  const models = Array.from(document.querySelectorAll('.matrix-model:checked')).map((x) => x.value);
  const toolModes = Array.from(document.querySelectorAll('.matrix-tool-mode:checked')).map((x) => x.value);
  const aiCompare = !!document.getElementById('matrix-ai-compare')?.checked;
  if (models.length === 0) return alert('Select at least one model.');
  if (toolModes.length === 0) return alert('Select at least one tool mode.');
  if (!confirm(`Run ${scenarioId} across ${models.length} model(s) x ${toolModes.length} tool mode(s)?`)) return;
  try {
    const res = await fetch(`${API_BASE}/scenarios/${scenarioId}/run-matrix`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ models, tool_modes: toolModes, ai_compare: aiCompare, judge_model: 'MiniMax-M2.5' }),
    });
    if (!res.ok) throw new Error('Failed to start run');
    const out = await res.json();
    if (out.job_id) app.navigate(null, `/jobs/${out.job_id}`);
    else alert('Started, but no job_id returned.');
  } catch (err) {
    alert('Error: ' + err.message);
  }
}
