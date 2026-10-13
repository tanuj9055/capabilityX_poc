import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, BookmarkPlus, CheckCircle2, Download, Eye, FileText, Lock, Pencil, Save, Send, Sparkles, Upload, XCircle } from 'lucide-react'
import { api, inr, poDocxUrl, poFileUrl } from '../api'
import { Badge, Busy, ErrorBox, Spinner } from '../components/ui.jsx'
import Preview from '../components/Preview.jsx'
import TableEdit from '../components/TableEdit.jsx'

const MODE = { template: 'Template', ai: 'AI-assisted draft', upload: 'Uploaded PO' }
const SCHEDULE = ['Stage', 'Quantity', 'Required timing', 'Release and acceptance gate']
const CLARIFY = ['Quotation topic', 'Buyer position and PO condition']
const n = (v) => (v === '' || v == null || isNaN(Number(v)) ? null : Number(v))

export default function PurchaseOrder() {
  const { id } = useParams()
  const nav = useNavigate()
  const [po, setPo] = useState(null)
  const [d, setD] = useState(null)        // edits on screen
  const [lib, setLib] = useState([])      // the buyer's saved terms library
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [preview, setPreview] = useState(null)
  const [answers, setAnswers] = useState({})
  const [tpl, setTpl] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [tplName, setTplName] = useState(null)

  const take = (p) => { setPo(p); setD(p.mode ? { fields: { ...p.fields }, lines: p.lines, gst_pct: p.gst_pct, freight: p.freight, stated_total: p.stated_total, key_controls: p.key_controls || [], schedule: p.schedule || [], clarifications: p.clarifications || [], terms: p.terms || [] } : null) }
  useEffect(() => {
    api.get(`/rfqs/${id}/po`).then(take).catch(setErr)
    api.get('/buyer/profile').then(p => setLib(p.terms || [])).catch(() => {})
  }, [id])
  const run = async (label, fn) => {
    setBusy(label); setErr(null)
    try { const r = await fn(); if (r) take(r); return r } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  if (!po) return err ? <ErrorBox error={err} /> : <Spinner label="Loading the purchase order…" />

  const issued = po.status === 'issued'
  const q = po.quotation
  const locked = po.mode !== 'upload'
  const back = <Link to={`/quotes/${id}`} className="inline-flex items-center gap-1 text-sm text-indigo-600"><ArrowLeft size={14} />Quote Evaluation</Link>

  const save = () => api.put(`/rfqs/${id}/po`, d)
  const cancel = () => run('Cancelling the selection…', async () => { await api.del(`/rfqs/${id}/po`); nav(`/quotes/${id}`) })
  const showPreview = async () => {
    setPreview([])
    try { setPreview((await api.post(`/rfqs/${id}/po/preview`, issued ? {} : d)).blocks) } catch (e) { setErr(e); setPreview(null) }
  }
  const issue = () => run('Issuing the PO and sending it to the supplier…', async () => {
    const saved = await save()
    if (saved.checks.some(c => c.level === 'error')) { setConfirm(false); return saved }
    const r = await api.post(`/rfqs/${id}/po/issue`)
    setConfirm(false)
    return r.po
  })

  // ── issued: read-only ────────────────────────────────────────────────────
  if (issued) {
    return (
      <div className="space-y-4">
        {back}
        <div className="card p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-xs text-slate-500">{po.rfq.ref}</div>
              <h1 className="text-xl font-semibold">Purchase order {po.fields.po_number}</h1>
              <div className="text-sm text-slate-600">To <b>{po.seller_name}</b> · {inr(po.totals.total)} · issued {po.issued_at?.slice(0, 16).replace('T', ' ')}</div>
            </div>
            <Badge k="issued" />
          </div>
          <div className="mt-3 flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-800">
            <CheckCircle2 size={15} />Issued and delivered to {po.seller_name}. The quotation is Accepted; the other quotations are Not selected.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <a className="btn-ghost" href={poDocxUrl(id)}><Download size={14} />Download PO (.docx)</a>
            {po.file && <a className="btn-ghost" href={poFileUrl(id)}><FileText size={14} />Your uploaded file ({po.file.name})</a>}
            {!preview && <button className="btn-ghost" onClick={showPreview}><Eye size={14} />View PO</button>}
          </div>
        </div>
        {preview && <div className="card p-6">{preview.length ? <Preview blocks={preview} /> : <Spinner label="Loading…" />}</div>}
      </div>
    )
  }

  // ── draft ────────────────────────────────────────────────────────────────
  const header = (
    <div className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-xs text-slate-500">{po.rfq.ref} · {po.rfq.title}</div>
          <h1 className="text-xl font-semibold">Purchase order for {po.seller_name}</h1>
          <div className="text-sm text-slate-600">Selected quotation: <b>{inr(q.totals.landed_total)}</b> total landed
            {q.valid_until ? <> · valid until <b>{q.valid_until}</b></> : ' · validity not stated'}
            {po.mode && <> · {MODE[po.mode]}{po.file && ` (${po.file.name})`}</>}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge k="selected" /><Badge k="draft">PO draft</Badge>
          <button className="btn-ghost py-1 text-xs text-red-600" onClick={cancel}><XCircle size={13} />Cancel selection</button>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">Nothing is accepted yet and the supplier sees nothing until you click <b>Generate PO</b>. You can save the draft and come back later.</p>
    </div>
  )

  const chooser = (
    <div className="card p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{po.mode ? 'Start again with' : 'How do you want to create the PO?'}</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="mb-1 flex items-center gap-2 font-medium"><FileText size={16} className="text-indigo-600" />Template</div>
          <p className="mb-2 text-xs text-slate-500">The standard PO or one of your saved templates, filled from the quotation. You edit delivery, terms and notes.</p>
          <select className="input mb-2 py-1 text-sm" value={tpl} onChange={e => setTpl(e.target.value)}>
            <option value="">Standard PO template</option>
            {(po.templates || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button className="btn-primary w-full justify-center" onClick={() => run('Building the PO…', () => api.post(`/rfqs/${id}/po/start`, { mode: 'template', template_id: tpl || null }))}>Use template</button>
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="mb-1 flex items-center gap-2 font-medium"><Sparkles size={16} className="text-indigo-600" />AI-assisted draft</div>
          <p className="mb-2 text-xs text-slate-500">AI builds the PO from the quotation, the RFQ and both profiles, picks clauses from your saved terms, and asks only what it can't know.</p>
          <button className="btn-primary w-full justify-center" onClick={() => run('AI is drafting the PO…', () => api.post(`/rfqs/${id}/po/start`, { mode: 'ai' }))}>Draft with AI</button>
        </div>
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="mb-1 flex items-center gap-2 font-medium"><Upload size={16} className="text-indigo-600" />Upload your PO</div>
          <p className="mb-2 text-xs text-slate-500">PDF, DOCX or an image. AI reads it and every difference from the quotation is flagged. Your file is what the supplier receives.</p>
          <label className="btn-primary w-full cursor-pointer justify-center">Choose file
            <input type="file" className="hidden" accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={e => {
              const f = e.target.files?.[0]; e.target.value = ''
              if (f) run('Reading your PO…', () => api.upload(`/rfqs/${id}/po/upload`, f))
            }} />
          </label>
        </div>
      </div>
    </div>
  )

  if (!po.mode) return <div className="space-y-4">{busy && <Busy label={busy} />}{back}{header}<ErrorBox error={err} />{chooser}</div>

  if (po.questions?.length > 0) {
    return (
      <div className="space-y-4">
        {busy && <Busy label={busy} />}{back}{header}<ErrorBox error={err} />
        <div className="card p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500"><Sparkles size={14} className="text-indigo-600" />AI draft — a few things only you know</h2>
          <p className="mb-3 text-sm text-slate-500">Supplier, items, prices, taxes, payment and your addresses are already filled from the quotation, the RFQ and your profile.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {po.questions.map(x => (
              <label key={x.id} className="text-sm">{x.question}
                {x.options ? (
                  <select className="input mt-1" value={answers[x.id] || ''} onChange={e => setAnswers({ ...answers, [x.id]: e.target.value })}>
                    <option value="">Choose…</option>{x.options.map(o => <option key={o}>{o}</option>)}
                  </select>
                ) : x.id === 'inspection' || x.id === 'special_terms'
                  ? <textarea className="input mt-1" rows={2} value={answers[x.id] || ''} onChange={e => setAnswers({ ...answers, [x.id]: e.target.value })} />
                  : <input className="input mt-1" type={x.type || 'text'} value={answers[x.id] || ''} onChange={e => setAnswers({ ...answers, [x.id]: e.target.value })} />}
              </label>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <button className="btn-primary" onClick={() => run('Completing the PO…', () => api.post(`/rfqs/${id}/po/ai-answers`, { answers }))}>Complete the PO</button>
            <button className="btn-ghost" onClick={() => run('Opening the editor…', () => api.post(`/rfqs/${id}/po/ai-answers`, { answers: {} }))}>Skip, edit manually</button>
          </div>
        </div>
      </div>
    )
  }

  const f = d.fields
  const setF = (k, v) => setD({ ...d, fields: { ...f, [k]: v } })
  const set = (k, v) => setD({ ...d, [k]: v })
  const errors = po.checks.filter(c => c.level === 'error')
  const sub = d.lines.reduce((s, li) => s + (n(li.qty) || 0) * (n(li.unit_price) || 0), 0)
  const tax = sub * (n(d.gst_pct) || 0) / 100
  const total = sub + tax + (n(d.freight) || 0)
  const inPo = new Set(d.terms.map(t => t.id))
  // a plain function, not a component: inputs keep focus while typing
  const F = ({ k, label, req, type, ro, wide }) => (
    <label key={k} className={`block text-xs text-slate-500 ${wide ? 'sm:col-span-2' : ''}`}>{label}{req && <span className="text-red-600"> *</span>}
      {ro ? <div className="mt-1 text-sm text-slate-800">{f[k] || '—'}</div>
        : <input className={`input mt-1 py-1 ${req && !f[k] ? 'border-red-300' : ''}`} type={type || 'text'} value={f[k] || ''} onChange={e => setF(k, e.target.value)} />}
    </label>
  )

  return (
    <div className="space-y-4">
      {busy && <Busy label={busy} />}
      {back}{header}
      <ErrorBox error={err} />

      <div className="card p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Purchase order · {MODE[po.mode]}</h2>
          <div className="flex flex-wrap gap-2">
            {preview === null
              ? <button className="btn-ghost py-1 text-xs" onClick={showPreview}><Eye size={13} />Preview PO</button>
              : <button className="btn-ghost py-1 text-xs" onClick={() => setPreview(null)}><Pencil size={13} />Back to editing</button>}
            <a className="btn-ghost py-1 text-xs" href={poDocxUrl(id)} onClick={async (e) => { e.preventDefault(); await run('Saving…', save); window.location.href = poDocxUrl(id) }}><Download size={13} />Download .docx</a>
            {tplName === null
              ? <button className="btn-ghost py-1 text-xs" onClick={() => setTplName('')}><BookmarkPlus size={13} />Save as template</button>
              : <span className="flex items-center gap-1"><input className="input w-44 py-1 text-xs" autoFocus placeholder="Template name" value={tplName} onChange={e => setTplName(e.target.value)} />
                <button className="btn-ghost py-1 text-xs" onClick={() => run('Saving template…', async () => { await save(); const r = await api.post(`/rfqs/${id}/po/save-template`, { name: tplName }); setTplName(null); return { ...po, templates: r.templates } })}>Save</button>
                <button className="text-xs text-slate-400" onClick={() => setTplName(null)}>Cancel</button></span>}
          </div>
        </div>

        {preview !== null ? (preview.length === 0 ? <Spinner label="Building the PO…" /> : (
          <div className="rounded border border-slate-200 bg-white p-6">
            <p className="mb-4 text-xs text-slate-400">This is the PO the supplier receives; highlighted parts are still empty.</p>
            <Preview blocks={preview} />
          </div>
        )) : (<>
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Items {locked ? <span className="flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 normal-case tracking-normal text-slate-500"><Lock size={11} />From the quotation — cannot be edited</span>
              : <span className="normal-case tracking-normal text-slate-400">· extracted from your file — must match the quotation</span>}
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-2 py-1">Description</th><th className="px-2 py-1 text-right">Qty</th><th className="px-2 py-1">Unit</th><th className="px-2 py-1 text-right">Unit price</th><th className="px-2 py-1 text-right">Value</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {d.lines.map((li, i) => {
                  const setL = (k, v) => set('lines', d.lines.map((x, j) => j === i ? { ...x, [k]: v } : x))
                  return (
                    <tr key={i}>
                      <td className="px-2 py-1">{locked ? li.desc : <input className="input py-1" value={li.desc} onChange={e => setL('desc', e.target.value)} />}</td>
                      <td className="px-2 py-1 text-right">{locked ? li.qty : <input className="input w-20 py-1 text-right" value={li.qty ?? ''} onChange={e => setL('qty', e.target.value)} />}</td>
                      <td className="px-2 py-1">{li.unit}</td>
                      <td className="px-2 py-1 text-right">{locked ? inr(li.unit_price) : <input className="input w-28 py-1 text-right" value={li.unit_price ?? ''} onChange={e => setL('unit_price', e.target.value)} />}</td>
                      <td className="px-2 py-1 text-right tabular-nums">{inr((n(li.qty) || 0) * (n(li.unit_price) || 0))}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap justify-end gap-x-6 gap-y-1 text-sm">
            <span className="text-slate-500">Subtotal <b className="text-slate-800">{inr(sub)}</b></span>
            <span className="text-slate-500">GST {locked ? `${d.gst_pct}%` : <input className="input inline w-14 py-0.5 text-right" value={d.gst_pct ?? ''} onChange={e => set('gst_pct', e.target.value)} />} <b className="text-slate-800">{inr(tax)}</b></span>
            <span className="text-slate-500">Freight {locked ? <b className="text-slate-800">{inr(d.freight)}</b> : <input className="input inline w-24 py-0.5 text-right" value={d.freight ?? ''} onChange={e => set('freight', e.target.value)} />}</span>
            <span>Total PO value <b>{inr(total)}</b> <span className="text-xs text-slate-400">(quotation {inr(q.totals.landed_total)})</span></span>
          </div>

          <h3 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Buyer, supplier and delivery</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {F({ k: "po_number", label: "PO number", req: true })}{F({ k: "po_date", label: "PO date", req: true, type: "date" })}{F({ k: "po_type", label: "PO type" })}{F({ k: "quote_ref", label: "Quotation reference", ro: true })}
            {F({ k: "buyer_name", label: "Buyer", req: true })}{F({ k: "buyer_gstin", label: "Buyer GSTIN" })}{F({ k: "buyer_address", label: "Registered office", req: true, wide: true })}
            {F({ k: "bill_to", label: "Bill to", req: true, wide: true })}{F({ k: "ship_to", label: "Ship to", req: true, wide: true })}
            {F({ k: "supplier_name", label: "Supplier", req: true, ro: locked })}{F({ k: "supplier_address", label: "Supplier address" })}{F({ k: "supplier_gstin", label: "Supplier GSTIN" })}{F({ k: "supplier_code", label: "Supplier code" })}
            {F({ k: "supplier_contact", label: "Supplier contact" })}{F({ k: "delivery_date", label: "Required delivery date", req: true, type: "date" })}{F({ k: "delivery_basis", label: "Delivery basis", wide: true })}
            {F({ k: "payment_terms", label: "Payment terms", req: true, wide: true })}{F({ k: "buyer_signatory", label: "Authorised signatory", req: true })}{F({ k: "buyer_designation", label: "Designation" })}
          </div>
          {d.stated_total != null && <p className="mt-2 text-xs text-slate-500">Total stated in your file: {inr(d.stated_total)}</p>}

          <label className="mt-4 block text-xs text-slate-500">Opening paragraph<textarea className="input mt-1" rows={2} value={f.intro || ''} onChange={e => setF('intro', e.target.value)} /></label>
          <label className="mt-3 block text-xs text-slate-500">Key controls <span className="text-slate-400">(one per line)</span>
            <textarea className="input mt-1" rows={3} value={d.key_controls.join('\n')} onChange={e => set('key_controls', e.target.value.split('\n'))} /></label>

          <h3 className="mt-5 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Delivery schedule</h3>
          <TableEdit cols={SCHEDULE} rows={d.schedule} on={v => set('schedule', v)} />
          <h3 className="mt-5 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Accepted clarifications and buyer conditions</h3>
          <TableEdit cols={CLARIFY} rows={d.clarifications} on={v => set('clarifications', v)} />

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <label className="text-xs text-slate-500">Inspection and acceptance<textarea className="input mt-1" rows={3} value={f.inspection || ''} onChange={e => setF('inspection', e.target.value)} /></label>
            <label className="text-xs text-slate-500">Special terms<textarea className="input mt-1" rows={3} value={f.special_terms || ''} onChange={e => setF('special_terms', e.target.value)} /></label>
            <label className="text-xs text-slate-500">Notes<textarea className="input mt-1" rows={3} value={f.notes || ''} onChange={e => setF('notes', e.target.value)} /></label>
          </div>

          <h3 className="mt-5 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Terms and conditions</h3>
          <p className="mb-2 text-xs text-slate-500">From your saved terms (edit the library in <Link to="/profile" className="text-indigo-600">Profile</Link>). Tick the clauses this PO carries.</p>
          <div className="space-y-1">
            {[...lib, ...d.terms.filter(t => !lib.some(l => l.id === t.id))].map(t => {
              const cur = d.terms.find(x => x.id === t.id)
              return (
                <div key={t.id} className="rounded border border-slate-100 p-2 text-sm">
                  <label className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1" checked={inPo.has(t.id)} onChange={e => set('terms', e.target.checked ? [...d.terms, { id: t.id, title: t.title, text: t.text }] : d.terms.filter(x => x.id !== t.id))} />
                    <span><b>{t.title}</b> <span className="text-xs text-slate-500">{(cur || t).text}</span></span>
                  </label>
                </div>
              )
            })}
          </div>
        </>)}

        <div className="mt-5 space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pre-issue checks</h3>
          {po.checks.length === 0 && <div className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={14} />All checks pass.</div>}
          {po.checks.map((c, i) => (
            <div key={i} className={`flex items-center gap-2 rounded px-2 py-1 text-sm ${c.level === 'error' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800'}`}>
              {c.level === 'error' ? <XCircle size={14} /> : <AlertTriangle size={14} />}{c.message}
            </div>
          ))}
          <p className="text-xs text-slate-400">Checks are re-run every time you save.</p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          <button className="btn-ghost" onClick={() => run('Saving the draft…', save)}><Save size={14} />Save draft &amp; check</button>
          {!confirm
            ? <button className="btn-primary" disabled={errors.length > 0} onClick={() => setConfirm(true)}><Send size={14} />Generate PO</button>
            : <span className="flex flex-wrap items-center gap-2 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm">
                Issue this PO to <b>{po.seller_name}</b>, mark the quotation Accepted and the others Not selected?
                <button className="btn-primary py-1" onClick={issue}>Confirm &amp; send</button>
                <button className="text-xs text-slate-500" onClick={() => setConfirm(false)}>Cancel</button>
              </span>}
          {errors.length > 0 && <span className="text-xs text-red-600">{errors.length} issue{errors.length > 1 ? 's' : ''} must be fixed before issue</span>}
        </div>
      </div>
      {chooser}
    </div>
  )
}
