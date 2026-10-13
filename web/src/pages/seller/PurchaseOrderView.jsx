import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Download, FileText } from 'lucide-react'
import { api, inr, sellerPoDocxUrl, sellerPoFileUrl } from '../../api'
import { Badge, ErrorBox, Spinner } from '../../components/ui.jsx'
import Preview from '../../components/Preview.jsx'

export default function PurchaseOrderView({ onRead }) {
  const { pid } = useParams()
  const [p, setP] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get(`/seller/pos/${pid}`).then(x => { setP(x); onRead?.() }).catch(setErr) }, [pid])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!p) return err ? <ErrorBox error={err} /> : <Spinner label="Loading…" />

  return (
    <div className="space-y-4">
      <Link to="/pos" className="inline-flex items-center gap-1 text-sm text-indigo-600"><ArrowLeft size={14} />Purchase Orders</Link>
      <div className="card p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-xs text-slate-500">{p.rfq_ref} · {p.title}</div>
            <h1 className="text-xl font-semibold">Purchase order {p.po_number}</h1>
            <div className="text-sm text-slate-600">From <b>{p.buyer_name}</b> · {inr(p.total)} incl. GST · deliver by <b>{p.delivery_date || '—'}</b></div>
          </div>
          <Badge k="issued">Received {p.issued_at?.slice(0, 10)}</Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <a className="btn-primary" href={sellerPoDocxUrl(p.id)}><Download size={14} />Download PO (.docx)</a>
          {p.file && <a className="btn-ghost" href={sellerPoFileUrl(p.id)}><FileText size={14} />Buyer's PO file ({p.file.name})</a>}
        </div>
      </div>
      <div className="card p-6"><Preview blocks={p.blocks} /></div>
    </div>
  )
}
