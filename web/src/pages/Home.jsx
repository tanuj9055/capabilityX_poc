import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { api } from '../api'
import { Badge, ErrorBox, Spinner } from '../components/ui.jsx'

const MODE = { chat: 'Chat-built', upload: 'Uploaded', form: 'From template' }

export default function Home() {
  const [rfqs, setRfqs] = useState(null)
  const [err, setErr] = useState(null)
  const load = () => api.get('/rfqs').then(setRfqs).catch(setErr)
  useEffect(() => { load() }, [])
  const del = async (id) => { await api.del(`/rfqs/${id}`); load() }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">My RFQs</h1>
      </div>
      <ErrorBox error={err} />
      {!rfqs && !err && <Spinner label="Loading…" />}
      {rfqs?.length === 0 && (
        <div className="card p-10 text-center text-sm text-slate-500">
          No RFQs yet. <Link to="/new" className="text-indigo-600 underline">Create your first RFQ</Link> — chat with the assistant, upload one, or start from a template.
        </div>
      )}
      {rfqs?.length > 0 && (
        <div className="card divide-y divide-slate-100">
          {rfqs.map(r => (
            <div key={r.id} className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50">
              <Link to={`/rfq/${r.id}`} className="flex-1">
                <div className="text-sm font-medium">{r.title || 'Untitled RFQ'}</div>
                <div className="text-xs text-slate-500">{r.ref} · {MODE[r.mode]} · {new Date(r.updated_at || r.created_at).toLocaleString()}</div>
              </Link>
              <Badge k={r.status}>{{ draft: 'Draft', review: 'In review', results: 'Matched' }[r.status]}</Badge>
              <button className="text-slate-400 hover:text-red-600" title="Delete" onClick={() => del(r.id)}><Trash2 size={16} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
