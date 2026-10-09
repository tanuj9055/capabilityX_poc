import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Pencil, Plus, RotateCcw, Save, Send, Sparkles, Trash2, XCircle } from 'lucide-react'
import { api, inr } from '../../api'
import { Badge } from '../../components/ui.jsx'

const MODE = { template: 'Standard template', ai: 'AI-assisted draft', upload: 'Uploaded quotation' }
const n = (v) => (v === '' || v == null || isNaN(Number(v)) ? null : Number(v))

// live totals by the same rule as the backend (quotes.compute_totals); the server recomputes on save
function totals(d) {
  const sub = d.lines.reduce((s, li) => s + (n(li.qty) || 0) * (n(li.unit_price) || 0), 0)
  const tax = sub * (n(d.gst_pct) || 0) / 100
  const fr = n(d.freight) || 0
  return { subtotal: sub, tax, freight: fr, landed_total: sub + tax + fr }
}

export default function QuoteEditor({ q, editable, onChange, run, onRestart }) {
  const source = q.draft || q.quotation
  const [d, setD] = useState(source)
  const [revising, setRevising] = useState(false)
  const [answers, setAnswers] = useState({})
  useEffect(() => { setD(q.draft || q.quotation) }, [q])

  const submitted = q.status === 'quoted'
  const canEdit = editable && (!submitted || revising)
  const questions = q.questions || []
  if (!d) return null

  const set = (k, v) => setD({ ...d, [k]: v })
  const setLine = (i, k, v) => set('lines', d.lines.map((li, j) => j === i ? { ...li, [k]: v } : li))
  const setComp = (i, k, v) => set('compliance', d.compliance.map((c, j) => j === i ? { ...c, [k]: v } : c))
  const setSup = (k, v) => set('supporting', { ...d.supporting, [k]: v })
  const t = totals(d)
  const checks = q.checks || []
  const errors = checks.filter(c => c.level === 'error')

  const save = () => run('Saving…', () => api.put(`/seller/requests/${q.id}/quotation`, { quotation: d }))
  const submit = () => run('Sending quotation…', async () => {
    const saved = await api.put(`/seller/requests/${q.id}/quotation`, { quotation: d })
    if (saved.checks.some(c => c.level === 'error')) return saved  // flags shown; nothing sent
    setRevising(false)
    return api.post(`/seller/requests/${q.id}/submit`)
  })

  if (canEdit && questions.length > 0) {
    return (
      <div className="card p-4">
        <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500"><Sparkles size={14} className="text-indigo-600" />AI draft — a few things only you know</h2>
        <p className="mb-3 text-sm text-slate-500">The AI filled in the lines and your supporting proof. Answer these and it completes the quotation; you can still edit everything afterwards.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {questions.map(x => (
            <label key={x.id} className="text-sm">{x.question}
              <input className="input mt-1" value={answers[x.id] || ''} onChange={e => setAnswers({ ...answers, [x.id]: e.target.value })}
                inputMode={/price|days|order/.test(x.id) ? 'decimal' : undefined} />
            </label>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <button className="btn-primary" onClick={() => run('Completing the draft…', () => api.post(`/seller/requests/${q.id}/ai-answers`, { answers }))}>Complete the draft</button>
          <button className="btn-ghost" onClick={() => run('Opening editor…', () => api.post(`/seller/requests/${q.id}/ai-answers`, { answers: {} }))}>Skip, edit manually</button>
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Quotation <span className="ml-1 normal-case tracking-normal text-slate-400">· {MODE[d.mode] || d.mode}{d.filename && ` (${d.filename})`}</span>
        </h2>
        <div className="flex items-center gap-2">
          {submitted && <span className="text-xs text-slate-500">Sent {q.submitted_at?.slice(0, 16).replace('T', ' ')} · revision {q.revision}</span>}
          {submitted && editable && !revising && <button className="btn-ghost py-1 text-xs" onClick={() => setRevising(true)}><Pencil size={13} />Revise before deadline</button>}
          {canEdit && onRestart && <button className="btn-ghost py-1 text-xs" onClick={onRestart}><RotateCcw size={13} />Start over</button>}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr><th className="px-2 py-2">Item</th><th className="px-2 py-2 text-right">Qty</th><th className="px-2 py-2">Unit</th>
              <th className="px-2 py-2 text-right">Unit price (₹)</th><th className="px-2 py-2 text-right">Amount</th>{canEdit && <th />}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {d.lines.map((li, i) => (
              <tr key={i}>
                <td className="px-2 py-1">{canEdit ? <input className="input py-1" value={li.desc} onChange={e => setLine(i, 'desc', e.target.value)} /> : li.desc}</td>
                <td className="px-2 py-1 text-right"><Num e={canEdit} v={li.qty} on={v => setLine(i, 'qty', v)} /></td>
                <td className="px-2 py-1">{canEdit ? <input className="input w-20 py-1" value={li.unit} onChange={e => setLine(i, 'unit', e.target.value)} /> : li.unit}</td>
                <td className="px-2 py-1 text-right"><Num e={canEdit} v={li.unit_price} on={v => setLine(i, 'unit_price', v)} w="w-32" /></td>
                <td className="px-2 py-1 text-right tabular-nums">{n(li.unit_price) != null ? inr((n(li.qty) || 0) * n(li.unit_price)) : '—'}</td>
                {canEdit && <td className="px-1"><button className="text-slate-400 hover:text-red-600" title="Remove line" onClick={() => set('lines', d.lines.filter((_, j) => j !== i))}><Trash2 size={14} /></button></td>}
              </tr>
            ))}
          </tbody>
        </table>
        {canEdit && <button className="mt-2 text-xs text-indigo-600" onClick={() => set('lines', [...d.lines, { desc: 'New item', qty: 1, unit: 'units', unit_price: null }])}><Plus size={12} className="inline" /> Add line</button>}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="space-y-2 text-sm lg:col-span-2">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="GST %"><Num e={canEdit} v={d.gst_pct} on={v => set('gst_pct', v)} w="w-full" /></Field>
            <Field label="Freight (₹)"><Num e={canEdit} v={d.freight} on={v => set('freight', v)} w="w-full" /></Field>
            <Field label="Lead time (days)"><Num e={canEdit} v={d.lead_time_days} on={v => set('lead_time_days', v)} w="w-full" /></Field>
            <Field label={`Quote validity (days)${q.rfq.required_validity_days ? ` · RFQ asks ${q.rfq.required_validity_days}` : ''}`}><Num e={canEdit} v={d.validity_days} on={v => set('validity_days', v)} w="w-full" /></Field>
            <Field label="Payment credit (days)"><Num e={canEdit} v={d.payment_days} on={v => set('payment_days', v)} w="w-full" /></Field>
            <Field label="Minimum order (units)"><Num e={canEdit} v={d.min_order} on={v => set('min_order', v)} w="w-full" /></Field>
          </div>
          <Field label="Payment terms">{canEdit ? <input className="input" value={d.payment_terms} onChange={e => set('payment_terms', e.target.value)} placeholder="e.g. 30% advance, balance 60 days after delivery" /> : (d.payment_terms || '—')}</Field>
          <Field label="Material / pricing assumptions">{canEdit ? <textarea className="input" rows={2} value={d.assumptions} onChange={e => set('assumptions', e.target.value)} /> : (d.assumptions || '—')}</Field>
          {d.mode === 'upload' && <Field label="Total stated in your document (₹)"><Num e={canEdit} v={d.stated_total} on={v => set('stated_total', v)} w="w-40" /></Field>}
        </div>
        <div className="rounded-md bg-slate-50 p-3 text-sm">
          <Row k="Subtotal" v={inr(t.subtotal)} />
          <Row k={`GST (${n(d.gst_pct) || 0}%)`} v={inr(t.tax)} />
          <Row k="Freight" v={inr(t.freight)} />
          <div className="mt-2 border-t border-slate-200 pt-2"><Row k={<b>Total landed price</b>} v={<b>{inr(t.landed_total)}</b>} /></div>
          <p className="mt-2 text-xs text-slate-400">Calculated by rule from your lines — not by AI.</p>
        </div>
      </div>

      <h3 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Compliance with mandatory requirements</h3>
      {d.compliance.length === 0 ? <p className="text-sm text-slate-500">The RFQ has no mandatory requirements.</p> : (
        <div className="space-y-2">
          {d.compliance.map((c, i) => (
            <div key={c.req_id} className="flex flex-wrap items-center gap-2 rounded border border-slate-100 p-2 text-sm">
              <span className="min-w-60 flex-1">{c.text}</span>
              {canEdit ? (
                <select className="input w-36 py-1" value={c.response} onChange={e => setComp(i, 'response', e.target.value)}>
                  <option value="comply">Comply</option><option value="deviation">Deviation</option>
                </select>
              ) : <Badge k={c.response === 'deviation' ? 'not' : 'full'}>{c.response === 'deviation' ? 'Deviation' : 'Comply'}</Badge>}
              {(canEdit || c.note) && (canEdit
                ? <input className="input w-full py-1 sm:w-64" placeholder="Note (optional)" value={c.note} onChange={e => setComp(i, 'note', e.target.value)} />
                : <span className="text-xs text-slate-500">{c.note}</span>)}
            </div>
          ))}
        </div>
      )}

      <h3 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Supporting information</h3>
      <div className="grid gap-3 text-sm sm:grid-cols-3">
        <Field label="Company">{canEdit ? <textarea className="input" rows={3} value={d.supporting.company} onChange={e => setSup('company', e.target.value)} /> : d.supporting.company || '—'}</Field>
        <ListField label="Certifications" items={d.supporting.certifications} edit={canEdit} on={v => setSup('certifications', v)} />
        <ListField label="Past orders / references" items={d.supporting.past_orders} edit={canEdit} on={v => setSup('past_orders', v)} />
      </div>

      {checks.length > 0 && (
        <div className="mt-5 space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pre-send checks</h3>
          {checks.map((c, i) => (
            <div key={i} className={`flex items-center gap-2 rounded px-2 py-1 text-sm ${c.level === 'error' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'}`}>
              {c.level === 'error' ? <XCircle size={14} /> : <AlertTriangle size={14} />}{c.message}
            </div>
          ))}
        </div>
      )}
      {checks.length === 0 && q.draft && <div className="mt-5 flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={14} />All pre-send checks pass.</div>}

      {canEdit && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button className="btn-ghost" onClick={save}><Save size={14} />Save &amp; check</button>
          <button className="btn-primary" onClick={submit}><Send size={14} />{submitted ? 'Send revised quotation' : 'Send quotation'}</button>
          {errors.length > 0 && <span className="text-xs text-red-600">{errors.length} issue{errors.length > 1 ? 's' : ''} must be fixed before sending</span>}
          {revising && <button className="btn-ghost" onClick={() => { setRevising(false); setD(q.draft || q.quotation) }}>Cancel</button>}
        </div>
      )}
    </div>
  )
}

const Num = ({ e, v, on, w = 'w-24' }) => e
  ? <input className={`input py-1 text-right ${w}`} inputMode="decimal" value={v ?? ''} onChange={x => on(x.target.value)} />
  : <span className="tabular-nums">{v ?? '—'}</span>
const Field = ({ label, children }) => <label className="block text-xs text-slate-500">{label}<div className="mt-1 text-sm text-slate-800">{children}</div></label>
const Row = ({ k, v }) => <div className="flex justify-between py-0.5"><span className="text-slate-600">{k}</span><span className="tabular-nums">{v}</span></div>
const ListField = ({ label, items, edit, on }) => (
  <Field label={label}>
    {edit ? <textarea className="input" rows={3} value={(items || []).join('\n')} onChange={e => on(e.target.value.split('\n').map(s => s.trim()).filter(Boolean))} placeholder="One per line" />
      : (items?.length ? <ul className="list-disc pl-4">{items.map((x, i) => <li key={i}>{x}</li>)}</ul> : '—')}
  </Field>
)
