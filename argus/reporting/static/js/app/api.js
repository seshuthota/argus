export async function fetchJSON(url) {
  const separator = url.includes('?') ? '&' : '?';
  const bustedUrl = `${url}${separator}_=${Date.now()}`;
  const res = await fetch(bustedUrl);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}
