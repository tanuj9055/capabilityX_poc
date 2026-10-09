import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Download, Plus, Quote, Trash2 } from 'lucide-react'
import { api, docxUrl } from '../api'
import { Badge, Busy, ErrorBox, Spinner, Steps } from '../components/ui.jsx'
import Understanding from '../components/Understanding.jsx'

export default function Review() {
  const { id } = useParams()
  const nav = useNavigate()
  const [rfq, setRfq] = useState(null)
  const [reqs, setReqs] = useState([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.get(`/rfqs/${id}`).then(r => {
      if (r.status === 'draft') return nav(`/rfq/${id}/build`, { replace: true })
      setRfq(r); setReqs(r.requirements)
    }).catch(setErr)
  }, [id])

  const frozen = rfq?.status === 'results'

  const upd = (i, patch) => { setReqs(rs => rs.map((r, j) => j === i ? { ...r, ...patch } : r)); setDirty(true) }
  const del = (i) => { setReqs(rs => rs.filter((_, j) => j !== i)); setDirty(true) }
  const add = () => { setReqs(rs => [...rs, { id: '', text: '', type: 'scored', data_point_ids: [], source: 'manual' }]); setDirty(true) }

  const save = async () => {
    const r = await api.put(`/rfqs/${id}/requirements`, { requirements: reqs })
    setRfq(r); setReqs(r.requirements); setDirty(false)
  }
  const confirm = async () => {
    setErr(null)
    try {
      if (dirty) { setBusy('Saving changes…'); await save() }
      setBusy('Checking every MSME against the mandatory gates, then scoring those that pass… (≈1 min)')
      await api.post(`/rfqs/${id}/confirm`)
      nav(`/rfq/${id}/results`)
    } catch (e) { setErr(e) } finally { setBusy(null) }
  }

  if (err && !rfq) return <ErrorBox error={err} />
  if (!rfq) return <Spinner label="Loading…" />
  const mand = reqs.filter(r => r.type === 'mandatory').length

  return (
    <div>
      {busy && <Busy label={busy} />}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{rfq.title}</h1>
          <div className="text-xs text-slate-500">{rfq.ref}{rfq.filename ? ` · ${rfq.filename}` : ''}</div>
        </div>
        <Steps status="review" />
      </div>
      <ErrorBox error={err} />
      <div className="card mb-4 p-4 text-sm">
        <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Tender understanding</div>
        <Understanding u={rfq.understanding} summary={rfq.summary} />
        {rfq.has_docx && (
          <div className="mt-3 flex flex-wrap gap-2">
            <a className="btn-ghost" href={docxUrl(id)}><Download size={14} />Download RFQ (.docx)</a>
          </div>
        )}
      </div>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-slate-600">
          <b>{reqs.length}</b> requirements · <b>{mand}</b> mandatory (pass/fail gates) · each is checked against the MSMEs' data automatically
        </div>
        <div className="flex gap-2">
          {!frozen && <button className="btn-ghost" onClick={add}><Plus size={14} />Add requirement</button>}
          {!frozen && dirty && <button className="btn-ghost" onClick={async () => { setBusy('Saving changes…'); try { await save() } catch (e) { setErr(e) } finally { setBusy(null) } }}>Save changes</button>}
          {frozen
            ? <button className="btn-primary" onClick={() => nav(`/rfq/${id}/results`)}>View results</button>
            : <button className="btn-primary" onClick={confirm}>Confirm & find suppliers</button>}
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr><th className="px-3 py-2">Requirement</th><th className="px-3 py-2 w-40">Type</th><th className="w-8" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {reqs.map((r, i) => (
              <tr key={i} className="align-top">
                <td className="px-3 py-2">
                  {frozen ? r.text : <textarea className="input min-h-[2.5rem] resize-y" rows={2} value={r.text} onChange={e => upd(i, { text: e.target.value })} />}
                  {r.source_quote && (
                    <div className="mt-1 flex gap-1 text-xs italic text-slate-500"><Quote size={12} className="mt-0.5 shrink-0" />{r.source_quote}</div>
                  )}
                  {r.source?.startsWith('slot:') && <div className="mt-1 text-xs text-slate-400">From RFQ field</div>}
                </td>
                <td className="px-3 py-2">
                  {frozen ? <Badge k={r.type} /> : (
                    <select className="input" value={r.type} onChange={e => upd(i, { type: e.target.value })}>
                      <option value="mandatory">Mandatory</option><option value="scored">Scored</option>
                    </select>
                  )}
                </td>
                <td className="py-2 pr-2">{!frozen && <button className="text-slate-400 hover:text-red-600" onClick={() => del(i)}><Trash2 size={15} /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
