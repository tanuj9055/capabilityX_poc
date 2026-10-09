import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, Download, Send, Trophy, XCircle } from 'lucide-react'
import { api, docxUrl } from '../api'
import { Badge, ErrorBox, ScoreBar, Spinner, Steps } from '../components/ui.jsx'

const SHORT = { org: 'Org', policy: 'Policy', ops: 'Ops', fin: 'Finance', cert: 'Certs', cust: 'Customers' }

export default function Results() {
  const { id } = useParams()
  const [rfq, setRfq] = useState(null)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const [reqs, setReqs] = useState([])
  const [pick, setPick] = useState({})
  const [deadline, setDeadline] = useState(() => new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10))
  const [validity, setValidity] = useState('')
  const [sending, setSending] = useState(false)
  const [sendErr, setSendErr] = useState(null)
  useEffect(() => {
    Promise.all([api.get(`/rfqs/${id}`), api.get(`/rfqs/${id}/results`), api.get(`/rfqs/${id}/quotes`)])
      .then(([r, x, q]) => { setRfq(r); setRes(x); setReqs(q.requests) }).catch(setErr)
  }, [id])
  const byS = Object.fromEntries(reqs.map(q => [q.seller_id, q]))
  const chosen = Object.keys(pick).filter(k => pick[k] && !byS[k])
  const send = async () => {
    setSending(true); setSendErr(null)
    try {
      const r = await api.post(`/rfqs/${id}/quote-requests`, { seller_ids: chosen, deadline, required_validity_days: validity || null })
      setReqs(r.requests); setPick({})
    } catch (e) { setSendErr(e) } finally { setSending(false) }
  }

  if (err) return <ErrorBox error={err} />
  if (!res) return <Spinner label="Loading…" />
  const cats = res.categories

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{rfq.title}</h1>
          <div className="text-xs text-slate-500">{rfq.ref} · {rfq.requirements.length} requirements · <Link className="text-indigo-600 underline" to={`/rfq/${id}/review`}>view requirements</Link>
            {rfq.has_docx && <> · <a className="text-indigo-600 underline" href={docxUrl(id)}><Download size={11} className="inline" /> RFQ .docx</a></>}
          </div>
        </div>
        <Steps status="results" />
      </div>

      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <Stat icon={Trophy} n={res.ranked.length} label="Qualified & ranked" tone="text-emerald-600" />
        <Stat icon={XCircle} n={res.rejected.length} label="Rejected on a mandatory gate" tone="text-red-600" />
      </div>

      {res.gate && res.gate.checked > 0 && (
        <div className="card mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3 text-xs text-slate-600">
          <span><b className="text-slate-800">Stage 1 · Mandatory gate:</b> all {res.gate.checked} MSMEs checked on {res.gate.mandatory} mandatory requirement{res.gate.mandatory === 1 ? '' : 's'} → <b className="text-emerald-700">{res.gate.passed} passed</b>, <b className="text-red-700">{res.gate.checked - res.gate.passed} rejected</b></span>
          <span><b className="text-slate-800">Stage 2 · Scoring:</b> {res.gate.passed} passing supplier{res.gate.passed === 1 ? '' : 's'} scored on all requirements (mandatory included)</span>
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase text-slate-500">Ranked suppliers</h2>
      {res.ranked.length === 0
        ? <div className="card p-6 text-sm text-slate-500">No supplier passed every mandatory requirement — see the rejected list below.</div>
        : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2" title="Select for a quote request" />
                  <th className="px-3 py-2">#</th><th className="px-3 py-2">Supplier</th><th className="px-3 py-2">Score</th>
                  {cats.map(c => <th key={c.id} className="px-2 py-2 text-center" title={c.label}>{SHORT[c.id]}</th>)}
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {res.ranked.map(x => (
                  <tr key={x.seller_id} className="hover:bg-slate-50">
                    <td className="px-3 py-3">{byS[x.seller_id]
                      ? <Badge k={byS[x.seller_id].outcome || byS[x.seller_id].status} />
                      : <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={!!pick[x.seller_id]} onChange={e => setPick({ ...pick, [x.seller_id]: e.target.checked })} />}</td>
                    <td className="px-3 py-3 font-semibold text-indigo-700">{x.rank}</td>
                    <td className="px-3 py-3">
                      <div className="font-medium">{x.name}</div>
                      <div className="text-xs text-slate-500">{x.city} · {x.line}</div>
                      <div className="text-xs text-slate-400">{x.counts.full} met · {x.counts.partial} partial · {x.counts.not} not met · {x.counts.na} data not available</div>
                    </td>
                    <td className="px-3 py-3"><ScoreBar value={x.total} /></td>
                    {cats.map(c => <td key={c.id} className="px-2 py-3 text-center text-xs tabular-nums">{x.categories[c.id] ? Math.round(x.categories[c.id].score) : '–'}</td>)}
                    <td className="px-3 py-3"><Link to={`/rfq/${id}/sellers/${x.seller_id}`} className="btn-ghost">Details <ChevronRight size={14} /></Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      {res.ranked.length > 0 && (
        <div className="card mt-3 flex flex-wrap items-end gap-3 p-3">
          <div className="text-sm"><b>Request quotes</b> <span className="text-xs text-slate-500">— tick the suppliers above ({chosen.length} selected){reqs.length > 0 && <> · {reqs.length} already sent · <Link className="text-indigo-600 underline" to={`/quotes/${id}`}>track &amp; compare quotes</Link></>}</span></div>
          <div className="ml-auto flex flex-wrap items-end gap-3">
            <label className="text-xs text-slate-600">Quote deadline<input type="date" className="input mt-1 py-1" value={deadline} min={new Date().toISOString().slice(0, 10)} onChange={e => setDeadline(e.target.value)} /></label>
            <label className="text-xs text-slate-600">Required validity (days, optional)<input type="number" min="1" className="input mt-1 w-40 py-1" value={validity} onChange={e => setValidity(e.target.value)} /></label>
            <button className="btn-primary" disabled={!chosen.length || !deadline || sending} onClick={send}><Send size={14} />{sending ? 'Sending…' : 'Send quote request'}</button>
          </div>
          <div className="w-full"><ErrorBox error={sendErr} /></div>
        </div>
      )}
      <p className="mt-1 text-xs text-slate-400">Score = equal-weight mean of the category scores (Met 1, Partial 0.5, Not met / Data not available 0). Any mandatory requirement not met rejects the supplier.</p>

      {res.rejected.length > 0 && <>
        <h2 className="mb-2 mt-6 text-sm font-semibold uppercase text-slate-500">Rejected at the mandatory gate</h2>
        <div className="card divide-y divide-slate-100">
          {res.rejected.map(x => (
            <div key={x.seller_id} className="flex items-start gap-4 px-4 py-3">
              <div className="flex-1">
                <div className="text-sm font-medium">{x.name} <span className="text-xs font-normal text-slate-500">· {x.city}</span></div>
                {x.failed.map(f => (
                  <div key={f.req_id} className="mt-1 text-xs"><span className="font-medium text-red-700">✗ {f.text}</span> <span className="text-slate-500">— {f.reason}</span></div>
                ))}
              </div>
              <Link to={`/rfq/${id}/sellers/${x.seller_id}`} className="btn-ghost">Details <ChevronRight size={14} /></Link>
            </div>
          ))}
        </div>
      </>}

      {res.errors?.length > 0 && (
        <div className="mt-6 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {res.errors.map(x => <div key={x.seller_id}><b>{x.name}</b> — {x.reason}</div>)}
        </div>
      )}
    </div>
  )
}

const Stat = ({ icon: Icon, n, label, tone }) => (
  <div className="card flex items-center gap-3 p-4">
    <Icon className={tone} size={22} />
    <div><div className="text-xl font-semibold">{n}</div><div className="text-xs text-slate-500">{label}</div></div>
  </div>
)
