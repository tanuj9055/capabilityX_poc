import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api, inr } from '../../api'
import { ErrorBox, Spinner } from '../../components/ui.jsx'

export default function PurchaseOrders() {
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get('/seller/pos').then(setRows).catch(setErr) }, [])

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Purchase Orders</h1>
      <p className="mb-4 text-sm text-slate-500">Orders buyers have issued to you on your accepted quotations.</p>
      <ErrorBox error={err} />
      {!rows && !err && <Spinner label="Loading…" />}
      {rows?.length === 0 && <div className="card p-10 text-center text-sm text-slate-500">No purchase orders yet. When a buyer accepts your quotation, the PO arrives here.</div>}
      {rows?.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr><th className="px-3 py-2">PO</th><th className="px-3 py-2">Buyer</th><th className="px-3 py-2">RFQ</th><th className="px-3 py-2 text-right">Value</th><th className="px-3 py-2">Deliver by</th><th className="px-3 py-2">Received</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map(r => (
                <tr key={r.id} className={r.unread ? 'bg-indigo-50/60' : 'hover:bg-slate-50'}>
                  <td className="px-3 py-2"><Link to={`/pos/${r.id}`} className="font-medium text-indigo-700 hover:underline">{r.po_number}</Link>
                    {r.unread && <span className="ml-2 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-white">New</span>}</td>
                  <td className="px-3 py-2">{r.buyer_name}</td>
                  <td className="px-3 py-2"><div>{r.title}</div><div className="text-xs text-slate-500">{r.rfq_ref}</div></td>
                  <td className="px-3 py-2 text-right tabular-nums">{inr(r.total)}</td>
                  <td className="px-3 py-2 tabular-nums">{r.delivery_date || '—'}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{r.issued_at?.slice(0, 16).replace('T', ' ')}</td>
                  <td className="px-3 py-2 text-right"><Link to={`/pos/${r.id}`}><ChevronRight size={16} className="text-slate-400" /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
