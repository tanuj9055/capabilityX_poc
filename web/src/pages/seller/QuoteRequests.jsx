import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api } from '../../api'
import { Badge, ErrorBox, Spinner } from '../../components/ui.jsx'

export default function QuoteRequests() {
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get('/seller/requests').then(setRows).catch(setErr) }, [])

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Quote Requests</h1>
      <p className="mb-4 text-sm text-slate-500">Buyers who matched your profile and want a quotation from you. Open one to read the RFQ and quote or decline.</p>
      <ErrorBox error={err} />
      {!rows && !err && <Spinner label="Loading…" />}
      {rows?.length === 0 && <div className="card p-10 text-center text-sm text-slate-500">No quote requests yet.</div>}
      {rows?.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-3 py-2">RFQ</th><th className="px-3 py-2">Buyer</th><th className="px-3 py-2">Deadline</th><th className="px-3 py-2">Status</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map(r => (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2"><Link to={`/requests/${r.id}`} className="font-medium text-indigo-700 hover:underline">{r.rfq.title}</Link><div className="text-xs text-slate-500">{r.rfq.ref}</div></td>
                  <td className="px-3 py-2">{r.buyer_name}</td>
                  <td className="px-3 py-2 tabular-nums">{r.deadline}</td>
                  <td className="px-3 py-2 space-x-1">
                    <Badge k={r.status} />
                    {r.status === 'quoted' && r.revision > 1 && <span className="text-xs text-slate-400">rev {r.revision}</span>}
                    {r.outcome && <Badge k={r.outcome} />}
                  </td>
                  <td className="px-3 py-2 text-right"><Link to={`/requests/${r.id}`}><ChevronRight size={16} className="text-slate-400" /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
