import { useEffect, useState } from 'react'
import { CheckCircle2, Plus, Save, Trash2 } from 'lucide-react'
import { api } from '../api'
import { Busy, ErrorBox, Spinner } from '../components/ui.jsx'

// Buyer profile: what the PO is filled from (addresses, GSTIN, signatory) and the saved terms the AI may choose from.
export default function Profile() {
  const [p, setP] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => { api.get('/buyer/profile').then(setP).catch(setErr) }, [])
  if (!p) return err ? <ErrorBox error={err} /> : <Spinner label="Loading…" />

  const set = (k, v) => { setSaved(false); setP({ ...p, [k]: v }) }
  const setTerm = (i, k, v) => set('terms', p.terms.map((t, j) => j === i ? { ...t, [k]: v } : t))
  const run = async (label, fn) => {
    setBusy(label); setErr(null)
    try { setP(await fn()); return true } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  const save = async () => { if (await run('Saving…', () => api.put('/buyer/profile', p))) setSaved(true) }
  const T = (k, label, rows, ph) => (
    <label className="block text-xs text-slate-500">{label}
      {rows ? <textarea className="input mt-1" rows={rows} placeholder={ph} value={p[k] || ''} onChange={e => set(k, e.target.value)} />
        : <input className="input mt-1" placeholder={ph} value={p[k] || ''} onChange={e => set(k, e.target.value)} />}
    </label>
  )

  return (
    <div className="space-y-4">
      {busy && <Busy label={busy} />}
      <div>
        <h1 className="text-xl font-semibold">Buyer profile</h1>
        <p className="text-sm text-slate-500">Purchase orders are filled from these details. The AI-assisted draft only chooses clauses from your saved terms; it never writes its own.</p>
      </div>
      <ErrorBox error={err} />
      <section className="card grid gap-3 p-4 sm:grid-cols-2">
        {T('name', 'Legal name')}{T('gstin', 'GSTIN', 0, 'e.g. 27AAACV1234F1Z5')}
        {T('registered_office', 'Registered office', 2)}{T('billing_address', 'Billing address', 2)}
        {T('signatory_name', 'Authorised signatory')}{T('signatory_designation', 'Designation')}
        {T('contact', 'Purchase contact', 0, 'Name, phone, email')}
        <label className="block text-xs text-slate-500">Shipping addresses <span className="text-slate-400">(one per line — with more than one, the AI draft asks which)</span>
          <textarea className="input mt-1" rows={3} value={(p.shipping_addresses || []).join('\n')} onChange={e => set('shipping_addresses', e.target.value.split('\n'))} />
        </label>
      </section>

      <section className="card p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">Saved terms and conditions</h2>
        <p className="mb-3 text-xs text-slate-500">Starts with the general clauses of your PO templates. “Default” clauses go into every template PO. Replace any <code>[insert …]</code> placeholder before issuing a PO with that clause.</p>
        <div className="space-y-2">
          {p.terms.map((t, i) => (
            <div key={i} className={`rounded border p-2 ${/\[insert/i.test(t.text) ? 'border-amber-300 bg-amber-50' : 'border-slate-100'}`}>
              <div className="flex items-center gap-2">
                <input className="input py-1 font-medium" value={t.title} onChange={e => setTerm(i, 'title', e.target.value)} />
                <label className="flex items-center gap-1 whitespace-nowrap text-xs text-slate-500"><input type="checkbox" checked={t.default !== false} onChange={e => setTerm(i, 'default', e.target.checked)} />Default</label>
                <button className="text-slate-400 hover:text-red-600" title="Remove clause" onClick={() => set('terms', p.terms.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
              </div>
              <textarea className="input mt-1 text-sm" rows={2} value={t.text} onChange={e => setTerm(i, 'text', e.target.value)} />
            </div>
          ))}
        </div>
        <button className="mt-2 text-xs text-indigo-600" onClick={() => set('terms', [...p.terms, { id: '', title: 'New clause', text: '', default: false }])}><Plus size={12} className="inline" /> Add clause</button>
      </section>

      <section className="card p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">Saved PO templates</h2>
        {(p.po_templates || []).length === 0 ? <p className="text-sm text-slate-500">None yet. On a PO draft, click <b>Save as template</b> to reuse its delivery, inspection, notes and clauses.</p> : (
          <ul className="divide-y divide-slate-100 text-sm">
            {p.po_templates.map(t => (
              <li key={t.id} className="flex items-center justify-between py-2">
                <span><b>{t.name}</b> <span className="text-xs text-slate-500">· {t.term_ids?.length || 0} clauses{t.fields?.inspection ? ' · inspection set' : ''}</span></span>
                <button className="text-slate-400 hover:text-red-600" title="Delete template" onClick={() => run('Deleting…', () => api.del(`/buyer/po-templates/${t.id}`))}><Trash2 size={14} /></button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}><Save size={14} />Save profile</button>
        {saved && <span className="flex items-center gap-1 text-sm text-emerald-700"><CheckCircle2 size={14} />Saved</span>}
      </div>
    </div>
  )
}
