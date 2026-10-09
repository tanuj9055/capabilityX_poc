// Demo sign-in (no password): {role: buyer|seller, id, name} kept in sessionStorage, i.e. per browser tab,
// so a buyer and a seller can be open side by side in the same browser.
const KEY = 'cx_session'
let memory = null

export const getSession = () => {
  try { return JSON.parse(sessionStorage.getItem(KEY)) || null } catch { return memory }
}
export const setSession = (s) => {
  memory = s
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY) } catch { /* memory only */ }
}

// buyer id = slug of the company name, so the same name sees the same RFQs in any tab
export const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64)

async function req(method, path, body, isForm) {
  const s = getSession()
  const headers = {}
  if (s) {
    headers['X-Role'] = s.role
    headers['X-User-Id'] = s.id
    headers['X-User-Name'] = encodeURIComponent(s.name || '')
  }
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  const r = await fetch('/api' + path, {
    method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })
  if (!r.ok) {
    let msg = r.statusText
    try { msg = (await r.json()).detail || msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}

export const api = {
  get: (p) => req('GET', p),
  post: (p, b) => req('POST', p, b || {}),
  put: (p, b) => req('PUT', p, b),
  del: (p) => req('DELETE', p),
  upload: (p, file) => { const f = new FormData(); f.append('file', file); return req('POST', p, f, true) },
}

// plain <a href> downloads cannot send headers, so the session goes in the query string
const auth = () => { const s = getSession() || {}; return `role=${s.role}&uid=${encodeURIComponent(s.id || '')}` }
export const docxUrl = (id) => `/api/rfqs/${id}/docx?${auth()}`
export const sellerDocxUrl = (qid) => `/api/seller/requests/${qid}/rfq.docx?${auth()}`

export const inr = (n) => n == null ? '—' : '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 })
