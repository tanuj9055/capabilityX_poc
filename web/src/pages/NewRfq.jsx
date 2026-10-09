import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUp, LayoutTemplate, MessageSquare } from 'lucide-react'
import { api } from '../api'
import { Busy, ErrorBox } from '../components/ui.jsx'

const EXAMPLES = [
  '10,000 steel mounting brackets for an EV sub-assembly, JIT delivery to our Pune plant every 3 days',
  'Need 5000 M10 hex bolts, zinc plated, class 8.8',
  '200 nos 100 kVA 11kV distribution transformers for our DISCOM',
  'Welded MS frames for railway coach interiors, about 1.5 tonnes each',
]

export default function NewRfq() {
  const [tab, setTab] = useState('chat')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState(null)
  const [templates, setTemplates] = useState([])
  const nav = useNavigate()
  useEffect(() => { api.get('/templates').then(setTemplates).catch(setErr) }, [])

  const run = async (label, fn) => {
    setErr(null); setBusy(label)
    try { await fn() } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  const startChat = () => run('Choosing the right RFQ template…', async () => {
    const r = await api.post('/rfqs/chat', { message: msg }); nav(`/rfq/${r.id}/build`)
  })
  const upload = (f) => f && run('Reading the RFQ and extracting requirements… (≈30–60 s)', async () => {
    const r = await api.upload('/rfqs/upload', f); nav(`/rfq/${r.id}/review`)
  })
  const fromTemplate = (tid) => run('Creating draft…', async () => {
    const r = await api.post('/rfqs/from-template', { template_id: tid }); nav(`/rfq/${r.id}/build`)
  })

  const TabBtn = ({ k, icon: Icon, children }) => (
    <button onClick={() => setTab(k)}
      className={`flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-3 text-sm font-medium ${tab === k ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`}>
      <Icon size={16} />{children}
    </button>
  )

  return (
    <div className="mx-auto max-w-3xl">
      {busy && <Busy label={busy} />}
      <h1 className="mb-4 text-xl font-semibold">New RFQ</h1>
      <div className="card mb-4 flex gap-2 p-2">
        <TabBtn k="chat" icon={MessageSquare}>Chat to build</TabBtn>
        <TabBtn k="upload" icon={FileUp}>Upload RFQ</TabBtn>
        <TabBtn k="template" icon={LayoutTemplate}>From template</TabBtn>
      </div>
      <ErrorBox error={err} />

      {tab === 'chat' && (
        <div className="card p-5">
          <div className="mb-2 text-sm font-medium">What do you need to source?</div>
          <textarea className="input h-28" value={msg} onChange={e => setMsg(e.target.value)}
            placeholder="Describe the item, quantity, delivery… the assistant will ask for the rest." />
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map(x => (
              <button key={x} className="chip border-slate-300 text-slate-600 hover:border-indigo-400" onClick={() => setMsg(x)}>{x}</button>
            ))}
          </div>
          <div className="mt-4 text-right">
            <button className="btn-primary" disabled={!msg.trim()} onClick={startChat}>Start building</button>
          </div>
        </div>
      )}

      {tab === 'upload' && (
        <label className="card flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed p-10 text-center hover:border-indigo-400">
          <FileUp className="text-indigo-500" size={32} />
          <div className="text-sm font-medium">Upload your RFQ / tender document</div>
          <div className="text-xs text-slate-500">.docx, .pdf (text or scanned), .png / .jpg — requirements are extracted and mapped to supplier data points</div>
          <input type="file" className="hidden" accept=".docx,.pdf,.png,.jpg,.jpeg,.txt" onChange={e => upload(e.target.files[0])} />
        </label>
      )}

      {tab === 'template' && (
        <div className="grid gap-3 sm:grid-cols-2">
          {templates.map(t => (
            <button key={t.id} onClick={() => fromTemplate(t.id)} className="card p-4 text-left hover:border-indigo-400">
              <div className="text-sm font-medium">{t.name}</div>
              <div className="mt-1 text-xs text-slate-500">{t.description}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
