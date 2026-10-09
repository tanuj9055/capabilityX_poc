import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Award, Plus, Sparkles, Trash2, X } from 'lucide-react'
import { api, inr } from '../api'
import { Badge, Busy, ErrorBox, ScoreBar, Spinner } from '../components/ui.jsx'

const KIND = { numeric: 'Numeric (calculated)', threshold: 'Threshold (calculated)', descriptive: 'Descriptive (AI)' }
const day = (s) => s ? s.slice(0, 16).replace('T', ' ') : '—'
const deviations = (q) => (q.compliance || []).filter(c => c.response === 'deviation')

export default function QuoteEvalRfq() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [criteria, setCriteria] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [open, setOpen] = useState(null)  // request id shown in the drawer

  const load = () => api.get(`/rfqs/${id}/quotes`).then(d => {
    setData(d)
    setCriteria(c => c || (d.evaluation?.criteria || d.default_criteria).map(x => ({ ...x })))
  }).catch(setErr)
  useEffect(() => { load() }, [id])  // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (label, fn) => {
    setBusy(label); setErr(null)
    try { await fn() } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  if (!data) return err ? <ErrorBox error={err} /> : <Spinner label="Loading…" />

  const { rfq, requests, evaluation, fields } = data
  const quoted = requests.filter(r => r.status === 'quoted')
  const accepted = requests.find(r => r.outcome === 'accepted')
  const byId = Object.fromEntries(requests.map(r => [r.id, r]))
  const weightSum = (criteria || []).reduce((s, c) => s + (Number(c.weight) || 0), 0)

  const runAnalysis = () => run('Scoring quotes…', async () => {
    const ev = await api.post(`/rfqs/${id}/evaluation/run`, { criteria })
    setData(d => ({ ...d, evaluation: ev }))
    setCriteria(ev.criteria.map(x => ({ ...x })))
  })
  const accept = (qid) => run('Accepting…', async () => {
    const r = await api.post(`/rfqs/${id}/quotes/${qid}/accept`)
    setData(d => ({ ...d, requests: r.requests }))
    setOpen(null)
  })

  return (
    <div className="space-y-4">
      {busy && <Busy label={busy} />}
      <Link to="/quotes" className="inline-flex items-center gap-1 text-sm text-indigo-600"><ArrowLeft size={14} />Quote Evaluation</Link>
      <div className="card p-4">
        <div className="text-xs text-slate-500">{rfq.ref}</div>
        <h1 className="text-xl font-semibold">{rfq.title}</h1>
        {rfq.summary && <p className="mt-1 text-sm text-slate-600">{rfq.summary}</p>}
        {accepted && <div className="mt-3 rounded-md border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-800"><Award size={14} className="mr-1 inline" />Accepted quote: <b>{accepted.seller_name}</b></div>}
      </div>
      <ErrorBox error={err} />

      {/* tracker */}
      <section className="card overflow-x-auto">
        <h2 className="px-4 pt-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Response tracker</h2>
        <table className="mt-2 w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr><th className="px-4 py-2">Supplier</th><th className="px-4 py-2">Status</th><th className="px-4 py-2">Sent</th><th className="px-4 py-2">Viewed</th>
              <th className="px-4 py-2">Quoted</th><th className="px-4 py-2">Deadline</th><th className="px-4 py-2">Note</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {requests.map(r => (
              <tr key={r.id}>
                <td className="px-4 py-2 font-medium">{r.seller_name}</td>
                <td className="px-4 py-2"><div className="flex gap-1"><Badge k={r.status} />{r.outcome && <Badge k={r.outcome} />}</div></td>
                <td className="px-4 py-2 text-xs text-slate-500">{day(r.sent_at)}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{day(r.viewed_at)}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{day(r.submitted_at)}{r.revision > 1 && ` (rev ${r.revision})`}</td>
                <td className="px-4 py-2 text-xs">{r.deadline}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{r.decline_reason ? `Declined: ${r.decline_reason}` : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* side-by-side comparison */}
      {quoted.length > 0 && (
        <section className="card overflow-x-auto p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Quotes side by side</h2>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th className="py-2 pr-4" />
              {quoted.map(r => <th key={r.id} className="min-w-44 px-3 py-2">
                <button className="font-semibold text-indigo-700 hover:underline" onClick={() => setOpen(r.id)}>{r.seller_name}</button>
                {r.outcome && <div className="mt-1"><Badge k={r.outcome} /></div>}
              </th>)}</tr></thead>
            <tbody className="divide-y divide-slate-100">
              <CmpRow k="Items" qs={quoted} f={q => q.lines.map((l, i) => <div key={i} className="text-xs">{l.desc} · {l.qty} {l.unit} × {inr(l.unit_price)}</div>)} />
              <CmpRow k="Subtotal" qs={quoted} f={q => inr(q.totals.subtotal)} />
              <CmpRow k="GST" qs={quoted} f={q => `${q.gst_pct ?? 0}% · ${inr(q.totals.tax)}`} />
              <CmpRow k="Freight" qs={quoted} f={q => inr(q.totals.freight)} />
              <CmpRow k={<b>Total landed price</b>} qs={quoted} f={q => <b>{inr(q.totals.landed_total)}</b>} best={q => q.totals.landed_total} />
              <CmpRow k="Lead time" qs={quoted} f={q => q.lead_time_days != null ? `${q.lead_time_days} days` : '—'} best={q => q.lead_time_days} />
              <CmpRow k="Quote validity" qs={quoted} f={q => q.validity_days != null ? `${q.validity_days} days` : '—'} />
              <CmpRow k="Payment" qs={quoted} f={q => <>{q.payment_days != null && <div>{q.payment_days} days credit</div>}<div className="text-xs text-slate-500">{q.payment_terms || '—'}</div></>} />
              <CmpRow k="Minimum order" qs={quoted} f={q => q.min_order ?? '—'} />
              <CmpRow k="Deviations" qs={quoted} f={q => deviations(q).length
                ? deviations(q).map(c => <div key={c.req_id} className="text-xs text-red-700">{c.text}{c.note && ` — ${c.note}`}</div>)
                : <span className="text-xs text-emerald-700">None — complies with all</span>} />
              <CmpRow k="How quoted" qs={quoted} f={q => <span className="text-xs text-slate-500">{q.mode === 'ai' ? 'AI-assisted draft' : q.mode === 'upload' ? `Uploaded${q.filename ? ` (${q.filename})` : ''}` : 'Standard template'}</span>} />
            </tbody>
          </table>
        </section>
      )}

      {quoted.length === 0 && <div className="card p-6 text-center text-sm text-slate-500">No quotations received yet. Analysis opens once at least one supplier sends a quote.</div>}

      {/* criteria + analysis */}
      {quoted.length > 0 && criteria && (
        <section className="card p-4">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">Evaluation criteria</h2>
          <p className="mb-3 text-sm text-slate-500">Numeric and threshold criteria are calculated by rule (same result every run). Descriptive criteria are judged by AI, with a reason.</p>
          <div className="space-y-2">
            {criteria.map((c, i) => {
              const set = (k, v) => setCriteria(criteria.map((x, j) => j === i ? { ...x, [k]: v } : x))
              return (
                <div key={i} className="flex flex-wrap items-center gap-2 rounded border border-slate-100 p-2 text-sm">
                  <input className="input w-56 py-1" value={c.name} onChange={e => set('name', e.target.value)} placeholder="Criterion name" />
                  <select className="input w-48 py-1" value={c.kind} onChange={e => set('kind', e.target.value)}>
                    {Object.entries(KIND).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                  {c.kind !== 'descriptive' && (
                    <select className="input w-52 py-1" value={c.field || ''} onChange={e => setCriteria(criteria.map((x, j) => j === i ? { ...x, field: e.target.value, better: fields[e.target.value]?.better } : x))}>
                      <option value="">Calculated from…</option>
                      {Object.entries(fields).map(([k, f]) => <option key={k} value={k}>{f.label}</option>)}
                    </select>
                  )}
                  {c.kind === 'numeric' && (
                    <select className="input w-36 py-1" value={c.better || 'lower'} onChange={e => set('better', e.target.value)}>
                      <option value="lower">Lower is better</option><option value="higher">Higher is better</option>
                    </select>
                  )}
                  {c.kind === 'threshold' && <label className="flex items-center gap-1 text-xs text-slate-500">{(c.better || fields[c.field]?.better) === 'higher' ? 'at least' : 'at most'}
                    <input className="input w-20 py-1 text-right" inputMode="decimal" value={c.limit ?? ''} onChange={e => set('limit', e.target.value)} /></label>}
                  {c.kind === 'descriptive' && <input className="input min-w-64 flex-1 py-1" value={c.description || ''} onChange={e => set('description', e.target.value)} placeholder="How should the AI judge this?" />}
                  <label className="ml-auto flex items-center gap-1 text-xs text-slate-500">Weight
                    <input className="input w-16 py-1 text-right" inputMode="decimal" value={c.weight} onChange={e => set('weight', e.target.value)} />%</label>
                  <button className="text-slate-400 hover:text-red-600" title="Remove" onClick={() => setCriteria(criteria.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
                </div>
              )
            })}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button className="text-xs text-indigo-600" onClick={() => setCriteria([...criteria, { name: '', kind: 'descriptive', description: '', weight: 0 }])}><Plus size={12} className="inline" /> Add criterion</button>
            <span className={`text-sm ${Math.abs(weightSum - 100) < 0.01 ? 'text-emerald-700' : 'text-red-600'}`}>Total weight: <b>{weightSum}%</b>{Math.abs(weightSum - 100) >= 0.01 && ' — must be 100%'}</span>
            <button className="btn-primary ml-auto" disabled={Math.abs(weightSum - 100) >= 0.01} onClick={runAnalysis}><Sparkles size={14} />{evaluation ? 'Re-run analysis' : 'Run analysis'}</button>
          </div>
        </section>
      )}

      {evaluation && (
        <section className="card p-4">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">Ranking</h2>
          <p className="mb-3 text-xs text-slate-400">Analysis run {day(evaluation.run_at)} — saved; reopening this page shows the same result until you re-run it.</p>
          <div className="space-y-3">
            {evaluation.results.map(x => {
              const req = byId[x.request_id]
              return (
                <div key={x.request_id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-sm font-semibold text-white">{x.rank}</span>
                    <button className="font-semibold text-indigo-700 hover:underline" onClick={() => setOpen(x.request_id)}>{x.seller_name}</button>
                    <span className="text-sm text-slate-500">{inr(x.landed_total)}</span>
                    {req?.outcome && <Badge k={req.outcome} />}
                    <span className="ml-auto text-sm">Weighted score <b className="text-lg tabular-nums">{x.total}</b> / 100</span>
                  </div>
                  <table className="mt-2 w-full text-sm">
                    <tbody className="divide-y divide-slate-100">
                      {evaluation.criteria.map(c => {
                        const s = x.scores[c.id] || { score: 0, reason: '' }
                        return (
                          <tr key={c.id}>
                            <td className="w-56 py-1 pr-2">{c.name} <span className="text-xs text-slate-400">· {c.weight}%{c.kind === 'descriptive' && ' · AI'}</span></td>
                            <td className="w-40 py-1"><ScoreBar value={s.score} /></td>
                            <td className="py-1 text-xs text-slate-600">{s.reason}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  {(x.risks.length > 0 || x.points_to_confirm.length > 0) && (
                    <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                      {x.risks.length > 0 && <div><div className="font-semibold text-red-700">Risks</div><ul className="list-disc pl-4 text-slate-600">{x.risks.map((t, i) => <li key={i}>{t}</li>)}</ul></div>}
                      {x.points_to_confirm.length > 0 && <div><div className="font-semibold text-amber-700">Points to confirm</div><ul className="list-disc pl-4 text-slate-600">{x.points_to_confirm.map((t, i) => <li key={i}>{t}</li>)}</ul></div>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {open && byId[open] && <Drawer r={byId[open]} canAccept={!accepted} onAccept={() => accept(open)} onClose={() => setOpen(null)} />}
    </div>
  )
}

function CmpRow({ k, qs, f, best }) {
  const vals = best ? qs.map(r => best(r.quotation)).filter(v => v != null && v > 0) : []
  const min = vals.length > 1 ? Math.min(...vals) : null
  return (
    <tr>
      <td className="py-2 pr-4 align-top text-xs text-slate-500">{k}</td>
      {qs.map(r => <td key={r.id} className={`px-3 py-2 align-top ${min != null && best(r.quotation) === min ? 'bg-emerald-50' : ''}`}>{f(r.quotation)}</td>)}
    </tr>
  )
}

function Drawer({ r, canAccept, onAccept, onClose }) {
  const q = r.quotation
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/30" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-white p-5 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold">{r.seller_name}</h2>
            <div className="text-xs text-slate-500">Sent {day(r.submitted_at)} · revision {r.revision}</div>
          </div>
          <button className="text-slate-400 hover:text-slate-700" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="mb-3 flex gap-1"><Badge k={r.status} />{r.outcome && <Badge k={r.outcome} />}</div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-2 py-1">Item</th><th className="px-2 py-1 text-right">Qty</th><th className="px-2 py-1 text-right">Unit price</th><th className="px-2 py-1 text-right">Amount</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {q.lines.map((l, i) => <tr key={i}><td className="px-2 py-1">{l.desc}</td><td className="px-2 py-1 text-right">{l.qty} {l.unit}</td><td className="px-2 py-1 text-right">{inr(l.unit_price)}</td><td className="px-2 py-1 text-right">{inr(l.amount)}</td></tr>)}
          </tbody>
        </table>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-slate-500">Subtotal</dt><dd className="text-right">{inr(q.totals.subtotal)}</dd>
          <dt className="text-slate-500">GST ({q.gst_pct ?? 0}%)</dt><dd className="text-right">{inr(q.totals.tax)}</dd>
          <dt className="text-slate-500">Freight</dt><dd className="text-right">{inr(q.totals.freight)}</dd>
          <dt className="font-semibold">Total landed price</dt><dd className="text-right font-semibold">{inr(q.totals.landed_total)}</dd>
          <dt className="text-slate-500">Lead time</dt><dd className="text-right">{q.lead_time_days ?? '—'} days</dd>
          <dt className="text-slate-500">Validity</dt><dd className="text-right">{q.validity_days ?? '—'} days</dd>
          <dt className="text-slate-500">Payment</dt><dd className="text-right">{q.payment_terms || '—'}{q.payment_days != null && ` (${q.payment_days} d credit)`}</dd>
          <dt className="text-slate-500">Minimum order</dt><dd className="text-right">{q.min_order ?? '—'}</dd>
        </dl>
        {q.assumptions && <p className="mt-3 text-sm"><span className="text-slate-500">Assumptions: </span>{q.assumptions}</p>}
        <h3 className="mt-4 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Compliance</h3>
        {(q.compliance || []).length === 0 ? <p className="text-sm text-slate-500">No mandatory requirements.</p> : q.compliance.map(c => (
          <div key={c.req_id} className="flex items-start gap-2 py-1 text-sm">
            <Badge k={c.response === 'deviation' ? 'not' : 'full'}>{c.response === 'deviation' ? 'Deviation' : 'Comply'}</Badge>
            <span>{c.text}{c.note && <span className="text-xs text-slate-500"> — {c.note}</span>}</span>
          </div>
        ))}
        <h3 className="mt-4 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Supporting information</h3>
        {q.supporting?.company && <p className="text-sm">{q.supporting.company}</p>}
        {q.supporting?.certifications?.length > 0 && <p className="mt-1 text-sm"><span className="text-slate-500">Certifications: </span>{q.supporting.certifications.join(', ')}</p>}
        {q.supporting?.past_orders?.length > 0 && <ul className="mt-1 list-disc pl-4 text-sm">{q.supporting.past_orders.map((x, i) => <li key={i}>{x}</li>)}</ul>}
        {(r.checks || []).length > 0 && <div className="mt-3 space-y-1">{r.checks.map((c, i) => <div key={i} className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">{c.message}</div>)}</div>}
        {canAccept && <button className="btn-primary mt-5 w-full justify-center" onClick={onAccept}><Award size={14} />Accept this quote</button>}
      </div>
    </div>
  )
}
