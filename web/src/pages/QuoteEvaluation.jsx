import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api } from '../api'
import { Badge, ErrorBox, Spinner } from '../components/ui.jsx'

const ORDER = ['sent', 'viewed', 'quoted', 'declined', 'expired']

export default function QuoteEvaluation() {
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    Promise.all([api.get('/quote-eval'), api.get('/rfqs')])
      .then(([evalRows, allRfqs]) => {
        const existingIds = new Set(evalRows.map(r => r.id))
        const extra = []
        for (const r of allRfqs || []) {
          if (!existingIds.has(r.id)) {
            try {
              const ext = JSON.parse(localStorage.getItem(`cx_ext_suppliers_${r.id}`) || '[]')
              if (ext.length > 0) {
                extra.push({
                  id: r.id,
                  ref: r.ref,
                  title: r.title,
                  requests: 0,
                  counts: {},
                  deadline: '—',
                  evaluated: false,
                  accepted: null,
                  externalCount: ext.length,
                })
              }
            } catch {}
          }
        }
        setRows([...evalRows, ...extra])
      })
      .catch(setErr)
  }, [])

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Quote Evaluation</h1>
      <p className="mb-4 text-sm text-slate-500">RFQs you have requested quotes for. Open one to track responses, compare quotes and run the AI analysis.</p>
      <ErrorBox error={err} />
      {!rows && !err && <Spinner label="Loading…" />}
      {rows?.length === 0 && (
        <div className="card p-10 text-center text-sm text-slate-500">
          No quote requests yet. Open an RFQ's <b>Results</b>, tick the suppliers that passed the gate and send a quote request.
        </div>
      )}
      {rows?.length > 0 && (
        <div className="card divide-y divide-slate-100">
          {rows.map(r => (
            <Link key={r.id} to={`/quotes/${r.id}`} className="flex flex-wrap items-center gap-4 px-4 py-3 hover:bg-slate-50">
              <div className="min-w-60 flex-1">
                <div className="text-sm font-medium">{r.title}</div>
                <div className="text-xs text-slate-500">
                  {r.ref} · {r.requests > 0 ? `${r.requests} supplier${r.requests > 1 ? 's' : ''} asked` : 'External invites only'} {r.deadline !== '—' && `· deadline ${r.deadline}`}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {ORDER.filter(k => r.counts[k]).map(k => <Badge key={k} k={k}>{r.counts[k]} {k}</Badge>)}
                {r.externalCount && (
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 border border-indigo-100">
                    {r.externalCount} external invite{r.externalCount > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {r.accepted ? <Badge k="accepted">Accepted: {r.accepted}{r.po?.status === 'issued' && ` · PO ${r.po.po_number}`}</Badge>
                : r.po?.status === 'draft' ? <Badge k="selected">PO pending: {r.po.seller_name}</Badge>
                : r.evaluated && <span className="text-xs text-indigo-600">Analysed</span>}
              <ChevronRight size={16} className="text-slate-400" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
