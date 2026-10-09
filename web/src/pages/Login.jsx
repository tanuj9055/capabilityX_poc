import { useEffect, useState } from 'react'
import { Building2, Factory } from 'lucide-react'
import { api, setSession, slug } from '../api'
import { ErrorBox } from '../components/ui.jsx'

// Demo sign-in: no password. Buyer types a company name; seller picks one of the MSMEs.
export default function Login({ onLogin }) {
  const [company, setCompany] = useState('')
  const [sellers, setSellers] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get('/sellers').then(setSellers).catch(setErr) }, [])

  const go = (s) => { setSession(s); onLogin(s) }
  const buyer = (e) => {
    e.preventDefault()
    const name = company.trim()
    if (slug(name).length >= 2) go({ role: 'buyer', id: slug(name), name })
  }

  return (
    <div className="mx-auto mt-10 max-w-3xl">
      <h1 className="mb-1 text-center text-2xl font-semibold text-indigo-700">CapabilityX</h1>
      <p className="mb-8 text-center text-sm text-slate-500">Demo sign-in — choose how you want to use CapabilityX. No password needed.</p>
      <ErrorBox error={err} />
      <div className="grid gap-4 md:grid-cols-2">
        <form className="card p-5" onSubmit={buyer}>
          <div className="mb-3 flex items-center gap-2 font-semibold"><Building2 size={18} className="text-indigo-600" />Buyer</div>
          <p className="mb-3 text-xs text-slate-500">Create RFQs, match MSMEs, request quotes and compare them.</p>
          <label className="mb-1 block text-xs font-medium text-slate-600">Company name</label>
          <input className="input mb-3" placeholder="e.g. VoltEdge" value={company} onChange={e => setCompany(e.target.value)} autoFocus />
          <button className="btn-primary w-full justify-center" disabled={slug(company.trim()).length < 2}>Sign in as buyer</button>
        </form>
        <div className="card p-5">
          <div className="mb-3 flex items-center gap-2 font-semibold"><Factory size={18} className="text-emerald-600" />Supplier (MSME)</div>
          <p className="mb-3 text-xs text-slate-500">See quote requests from buyers and send quotations.</p>
          <div className="space-y-2">
            {sellers?.map(s => (
              <button key={s.id} className="btn-ghost w-full justify-between" onClick={() => go({ role: 'seller', id: s.id, name: s.name })}>
                <span>{s.name}</span><span className="text-xs text-slate-400">{s.city !== '—' ? s.city : ''}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-4 text-center text-xs text-slate-400">Each browser tab keeps its own sign-in, so you can be a buyer in one tab and a supplier in another.</p>
    </div>
  )
}
