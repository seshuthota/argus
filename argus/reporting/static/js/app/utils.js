export function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[m]);
}

export function renderMarkdown(text, { escapeHtml: esc } = { escapeHtml }) {
  if (!text) return '';
  try {
    if (window.marked && typeof window.marked.parse === 'function') {
      return window.marked.parse(text);
    }
    return esc(text);
  } catch (err) {
    console.error('Markdown rendering failed', err);
    return esc(text);
  }
}
