export async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'include', ...options });
  const text = await response.text();
  let data;

  try {
    data = JSON.parse(text);
  } catch {
    data = text;
  }

  if (!response.ok) {
    throw new Error(data?.detail || data || `HTTP ${response.status}`);
  }

  return data;
}
