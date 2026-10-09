import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Download, FileText, Sparkles, Upload, XCircle } from 'lucide-react'
import { api, sellerDocxUrl } from '../../api'
import { Badge, Busy, ErrorBox, Spinner } from '../../components/ui.jsx'
import Understanding from '../../components/Understanding.jsx'
import QuoteEditor from './QuoteEditor.jsx'

export default function QuoteRequest() {
  const { qid } = useParams()
  const [q, setQ] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')
  const file = useRef()
  useEffect(() => { api.get(`/seller/requests/${qid}`).then(setQ).catch(setErr) }, [qid])

  const run = async (label, fn) => {
    setBusy(label); setErr(null)
    try { setQ(await fn()) } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  if (!q) return err ? <ErrorBox error={err} /> : <Spinner label="Loading…" />

  const { rfq, fit } = q
  const mandatory = rfq.requirements.filter(r => r.type === 'mandatory')
  const fitRows = (fit?.rows || []).filter(r => r.type === 'mandatory')
  const editable = q.open && !q.outcome
  const started = !!q.draft

  return (
    <div className="space-y-4">
      {busy && <Busy label={busy} />}
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-indigo-600"><ArrowLeft size={14} />All quote requests</Link>

      <div className="card flex flex-wrap items-start justify-between gap-4 p-4">
        <div>
          <div className="text-xs text-slate-500">{rfq.ref}</div>
          <h1 className="text-xl font-semibold">{rfq.title}</h1>
          <div className="mt-1 text-sm text-slate-600">Buyer: <b>{q.buyer_name}</b> · Quote deadline <b>{q.deadline}</b>
            {rfq.required_validity_days && <> · validity asked: <b>{rfq.required_validity_days} days</b></>}</div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex gap-1"><Badge k={q.status} />{q.outcome && <Badge k={q.outcome} />}</div>
          {rfq.has_docx && <a className="btn-ghost py-1 text-xs" href={sellerDocxUrl(q.id)}><Download size={13} />RFQ document</a>}
        </div>
      </div>

      {q.outcome === 'accepted' && <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">The buyer <b>accepted</b> your quotation.</div>}
      {q.outcome === 'not_selected' && <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">The buyer chose another supplier for this RFQ.</div>}
      {q.status === 'declined' && <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">You declined this request: <i>{q.decline_reason}</i></div>}
      {q.status === 'expired' && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">The quote deadline has passed.</div>}

      <div className="card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Tender understanding</h2>
        <Understanding u={rfq.understanding} summary={rfq.summary} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Mandatory requirements</h2>
          {mandatory.length === 0 ? <p className="text-sm text-slate-500">None.</p> : (
            <ul className="space-y-1 text-sm">{mandatory.map(r => <li key={r.id} className="flex gap-2"><span className="text-rose-500">•</span>{r.text}</li>)}</ul>
          )}
        </div>
        <div className="card p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">How your profile matches</h2>
          {fitRows.length === 0 ? <p className="text-sm text-slate-500">No match details.</p> : (
            <div className="space-y-2 text-xs">
              {fitRows.map(r => (
                <div key={r.id} className="rounded border border-slate-100 p-2">
                  <div className="flex items-start justify-between gap-2"><span className="text-sm">{r.text}</span><Badge k={r.status} /></div>
                  {r.reason && <div className="mt-1 text-slate-500">{r.reason}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ErrorBox error={err} />

      {editable && !started && q.status !== 'quoted' && (
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Respond</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Action icon={FileText} title="Standard template" text="RFQ lines and your recorded certifications filled in; you add prices and terms."
              onClick={() => run('Preparing template…', () => api.post(`/seller/requests/${qid}/draft`, { mode: 'template' }))} />
            <Action icon={Sparkles} title="AI-assisted draft" text="AI drafts the quotation from the RFQ and your profile, then asks what it can't know."
              onClick={() => run('AI is drafting your quotation…', () => api.post(`/seller/requests/${qid}/draft`, { mode: 'ai' }))} />
            <Action icon={Upload} title="Upload my quotation" text="PDF / DOCX / XLSX. AI reads it into the standard format for you to confirm."
              onClick={() => file.current.click()} />
            <Action icon={XCircle} title="Decline" text="Tell the buyer you won't quote, with a reason." danger onClick={() => setDeclining(true)} />
          </div>
          <input ref={file} type="file" className="hidden" accept=".pdf,.docx,.xlsx,.xls,.csv,.txt"
            onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) run('Reading your quotation…', () => api.upload(`/seller/requests/${qid}/upload`, f)) }} />
          {declining && (
            <div className="mt-4 rounded-md border border-slate-200 p-3">
              <label className="text-sm font-medium">Reason for declining</label>
              <textarea className="input mt-1" rows={2} value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Capacity booked till March" />
              <div className="mt-2 flex gap-2">
                <button className="btn-primary bg-red-600 hover:bg-red-700" disabled={!reason.trim()}
                  onClick={() => run('Declining…', () => api.post(`/seller/requests/${qid}/decline`, { reason }))}>Decline request</button>
                <button className="btn-ghost" onClick={() => setDeclining(false)}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}

      {(started || q.quotation) && (
        <QuoteEditor q={q} editable={editable} onChange={setQ} run={run}
          onRestart={editable && q.status !== 'quoted' ? () => setQ({ ...q, draft: null, questions: [] }) : null} />
      )}
    </div>
  )
}

const Action = ({ icon: Icon, title, text, onClick, danger }) => (
  <button onClick={onClick} className={`rounded-lg border p-3 text-left transition hover:shadow ${danger ? 'border-red-200 hover:bg-red-50' : 'border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/40'}`}>
    <Icon size={18} className={danger ? 'text-red-600' : 'text-indigo-600'} />
    <div className="mt-2 text-sm font-medium">{title}</div>
    <div className="mt-1 text-xs text-slate-500">{text}</div>
  </button>
)
