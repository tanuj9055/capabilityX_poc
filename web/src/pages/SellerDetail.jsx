import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { api } from '../api'
import { Badge, ErrorBox, ScoreBar, Spinner } from '../components/ui.jsx'

export default function SellerDetail() {
  const { id, sid } = useParams()
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get(`/rfqs/${id}/sellers/${sid}`).then(setD).catch(setErr) }, [id, sid])
  if (err) return <ErrorBox error={err} />
  if (!d) return <Spinner label="Loading…" />
  const { seller, score, rows, categories } = d
  const rejected = score.status === 'rejected'

  return (
    <div>
      <Link to={`/rfq/${id}/results`} className="mb-3 inline-flex items-center gap-1 text-sm text-indigo-600"><ArrowLeft size={14} />Back to results</Link>
      <div className="card mb-4 flex flex-wrap items-start justify-between gap-4 p-4">
        <div>
          <h1 className="text-xl font-semibold">{seller.name}</h1>
          <div className="text-sm text-slate-500">{seller.city} · {seller.category_label}</div>
          <p className="mt-2 max-w-2xl text-sm">{seller.profile}</p>
        </div>
        <div className="text-right">
          {rejected
            ? <div className="rounded bg-red-100 px-3 py-1 text-sm font-semibold text-red-700">Rejected</div>
            : <div className="text-3xl font-semibold text-indigo-700">{Math.round(score.total)}<span className="text-sm text-slate-400">/100</span></div>}
          {!rejected && <div className="mt-1 text-xs text-slate-500">{score.counts.full} met · {score.counts.partial} partial · {score.counts.not} not met · {score.counts.na} data not available</div>}
        </div>
      </div>

      {rejected && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm">
          <div className="font-medium text-red-700">Failed mandatory requirement{score.failed.length > 1 ? 's' : ''}:</div>
          {score.failed.map(f => <div key={f.req_id} className="mt-1 text-xs">✗ <b>{f.text}</b> — {f.reason}</div>)}
          <div className="mt-2 text-xs text-slate-500">Rejected at the mandatory gate, so the scored requirements were not assessed.</div>
        </div>
      )}

      {!rejected && <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map(c => {
          const s = score.categories[c.id]
          return (
            <div key={c.id} className="card p-3">
              <div className="mb-1 text-xs text-slate-500">{c.label}</div>
              {s ? <><ScoreBar value={s.score} /><div className="mt-1 text-[11px] text-slate-400">{s.n} requirement{s.n > 1 ? 's' : ''}</div></>
                : <div className="text-xs text-slate-400">No requirement in this category</div>}
            </div>
          )
        })}
      </div>}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-3 py-2">Requirement</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Supplier value</th><th className="px-3 py-2">Reason</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map(r => (
              <tr key={r.id} className="align-top">
                <td className="px-3 py-2"><div>{r.text}</div><div className="mt-1"><Badge k={r.type} /></div></td>
                <td className="px-3 py-2"><Badge k={r.status} /></td>
                <td className="px-3 py-2 text-xs">
                  {r.values.map(v => <div key={v.id} className="mb-1"><span className="text-slate-500">{v.label}:</span> {v.value || <i className="text-slate-400">data not available</i>}</div>)}
                </td>
                <td className="px-3 py-2 text-xs text-slate-600">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
