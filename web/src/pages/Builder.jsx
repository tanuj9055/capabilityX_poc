import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Bot, CheckCircle2, ListChecks, MessageSquare, Send, User } from 'lucide-react'
import { api } from '../api'
import { Busy, ErrorBox, Spinner, Steps } from '../components/ui.jsx'
import Preview from '../components/Preview.jsx'
import SlotField from '../components/SlotField.jsx'

export default function Builder() {
  const { id } = useParams()
  const nav = useNavigate()
  const [rfq, setRfq] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [view, setView] = useState(null) // 'chat' | 'form'

  useEffect(() => {
    api.get(`/rfqs/${id}`).then(r => {
      if (r.status !== 'draft') return nav(`/rfq/${id}`, { replace: true })
      setRfq(r); setView(r.mode === 'chat' ? 'chat' : 'form')
    }).catch(setErr)
  }, [id])

  const call = async (label, fn) => {
    setErr(null); setBusy(label)
    try { setRfq(await fn()) } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  const setSlot = (sid, v) => call(null, () => api.put(`/rfqs/${id}/slots`, { values: { [sid]: v } }))
  const approve = async () => {
    setErr(null); setBusy('Generating the RFQ document…')
    try { await api.post(`/rfqs/${id}/approve`); nav(`/rfq/${id}/review`) } catch (e) { setErr(e) } finally { setBusy(null) }
  }

  if (err && !rfq) return <ErrorBox error={err} />
  if (!rfq) return <Spinner label="Loading…" />
  const missing = rfq.missing || []

  return (
    <div>
      {busy && <Busy label={busy} />}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{rfq.title || 'New RFQ'}</h1>
          <div className="text-xs text-slate-500">{rfq.ref} · Template: <b>{rfq.template.name}</b>{rfq.template_reason ? ` — ${rfq.template_reason}` : ''}</div>
        </div>
        <Steps status="draft" />
      </div>
      <ErrorBox error={err} />
      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="card flex h-[calc(100vh-200px)] min-h-[500px] flex-col">
          <div className="flex border-b border-slate-200 text-sm">
            {rfq.mode === 'chat' && <button onClick={() => setView('chat')} className={`flex items-center gap-1 px-4 py-2 ${view === 'chat' ? 'border-b-2 border-indigo-600 font-medium text-indigo-700' : 'text-slate-500'}`}><MessageSquare size={14} />Chat</button>}
            <button onClick={() => setView('form')} className={`flex items-center gap-1 px-4 py-2 ${view === 'form' ? 'border-b-2 border-indigo-600 font-medium text-indigo-700' : 'text-slate-500'}`}><ListChecks size={14} />All fields</button>
          </div>
          {view === 'chat'
            ? <Chat rfq={rfq} send={(message, values) => call('Thinking…', () => api.post(`/rfqs/${id}/chat`, { message, values }))} />
            : <Form rfq={rfq} setSlot={setSlot} />}
        </div>

        <div className="card flex h-[calc(100vh-200px)] min-h-[500px] flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
            <div className="text-sm font-medium">Live RFQ preview</div>
            <div className="flex items-center gap-2">
              {missing.length > 0
                ? <span className="text-xs text-amber-700">{missing.length} required field{missing.length > 1 ? 's' : ''} left</span>
                : <span className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 size={14} />Ready</span>}
              <button className="btn-primary" disabled={missing.length > 0} onClick={approve}>Approve RFQ</button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-4"><Preview blocks={rfq.preview} /></div>
        </div>
      </div>
    </div>
  )
}

function Chat({ rfq, send }) {
  const [text, setText] = useState('')
  const [answers, setAnswers] = useState({})
  const end = useRef(null)
  const msgs = rfq.messages || []
  const last = msgs[msgs.length - 1]
  const questions = last?.role === 'bot' ? last.questions || [] : []
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth' })
    // pre-select the suggested / current answer so the buyer can just confirm
    setAnswers(Object.fromEntries(questions.filter(q => q.value !== undefined).map(q => [q.id, q.value])))
  }, [msgs.length])

  const submit = () => {
    const vals = Object.fromEntries(Object.entries(answers).filter(([, v]) => v !== '' && v != null && !(Array.isArray(v) && !v.length)))
    if (!text.trim() && !Object.keys(vals).length && !questions.length) return
    send(text.trim() || null, vals); setText('')
  }
  return (
    <>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.map((m, i) => (
          <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${m.role === 'user' ? 'bg-slate-200' : 'bg-indigo-100 text-indigo-700'}`}>
              {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-100'}`}>{m.text}</div>
          </div>
        ))}
        {questions.length > 0 && (
          <div className="ml-9 space-y-3 rounded-lg border border-indigo-100 bg-indigo-50/40 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-indigo-700">{(rfq.template.buckets.find(b => b.id === questions[0].bucket) || {}).label}</div>
            {questions.map(q => (
              <div key={q.id}>
                <div className="mb-1 text-xs font-medium text-slate-700">{q.question}</div>
                <SlotField compact slot={q} value={answers[q.id]} onCommit={v => setAnswers(a => ({ ...a, [q.id]: v }))} />
              </div>
            ))}
            <div className="flex justify-end pt-1">
              <button className="btn-primary py-1 text-xs" onClick={submit}>Confirm & continue</button>
            </div>
          </div>
        )}
        <div ref={end} />
      </div>
      <div className="flex gap-2 border-t border-slate-200 p-3">
        <input className="input" value={text} onChange={e => setText(e.target.value)} placeholder="Answer above, or type freely — e.g. 'ask about quality', 'deliver weekly to Chakan, 45 days payment'"
          onKeyDown={e => { if (e.key === 'Enter') submit() }} />
        <button className="btn-primary" onClick={submit}><Send size={14} /></button>
      </div>
    </>
  )
}

function Form({ rfq, setSlot }) {
  const t = rfq.template
  const vals = rfq.effective || {}
  const missing = new Set(rfq.missing || [])
  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      {t.buckets.map(b => {
        const slots = t.all_slots.filter(s => s.bucket === b.id)
        if (!slots.length) return null
        return (
          <div key={b.id}>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{b.label}</div>
            <div className="space-y-3">
              {slots.map(s => (
                <div key={s.id}>
                  <div className="mb-1 text-xs text-slate-700">
                    {s.label}{s.ask && (s.data_point_ids?.length > 0 || s.id === 'buyer') && <span className="text-red-500"> *</span>}
                    {missing.has(s.id) && <span className="ml-2 rounded bg-amber-100 px-1 text-[10px] text-amber-800">required</span>}
                  </div>
                  <SlotField slot={s} value={vals[s.id]} onCommit={v => setSlot(s.id, v)} />
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

