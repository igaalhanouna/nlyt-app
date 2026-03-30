/**
 * safeFetchJson — Standard fetch wrapper for NLYT.
 *
 * Reads the response body as text first, then parses JSON manually.
 * This avoids the "body stream already read" error that can occur
 * when network/proxy layers interfere with resp.json().
 *
 * @param {string} url - The URL to fetch
 * @param {RequestInit} [options] - Standard fetch options
 * @returns {Promise<{ ok: boolean, status: number, data: any }>}
 */
export async function safeFetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  const text = await resp.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { detail: text || 'Réponse invalide du serveur' };
  }
  return { ok: resp.ok, status: resp.status, data };
}
