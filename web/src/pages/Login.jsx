import { useEffect, useState } from 'react'
import { Building2, Factory, Landmark } from 'lucide-react'
import { api, setSession, slug } from '../api'
import { ErrorBox } from '../components/ui.jsx'

// Demo sign-in: no password. Buyer or FI types a name; seller picks one of the MSMEs.
export default function Login({ onLogin }) {
  const [company, setCompany] = useState('')
  const [fiCompany, setFiCompany] = useState('')
  const [sellers, setSellers] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get('/sellers').then(setSellers).catch(setErr) }, [])

  const go = (s) => { setSession(s); onLogin(s) }
  const buyer = (e) => {
    e.preventDefault()
    const name = company.trim()
    if (slug(name).length >= 2) go({ role: 'buyer', id: slug(name), name })
  }
  const fiLogin = (e) => {
    e.preventDefault()
    const name = fiCompany.trim()
    if (slug(name).length >= 2) go({ role: 'fi', id: slug(name), name })
  }

  return (
    <div className="mx-auto mt-10 max-w-5xl">
      <h1 className="mb-1 text-center text-2xl font-semibold text-indigo-700">CapabilityX</h1>
      <p className="mb-8 text-center text-sm text-slate-500">Demo sign-in — choose how you want to use CapabilityX. No password needed.</p>
      <ErrorBox error={err} />
      <div className="grid gap-4 md:grid-cols-3">
        {/* Buyer */}
        <form className="card flex flex-col p-5" onSubmit={buyer}>
          <div className="mb-3 flex items-center gap-2 font-semibold text-slate-800">
            <Building2 size={18} className="text-indigo-600" />Buyer
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Create RFQs, match MSMEs, request quotes and compare them.
          </p>
          <label className="mb-1 block text-xs font-medium text-slate-600">Company name</label>
          <input
            className="input mb-3"
            placeholder="e.g. VoltEdge"
            value={company}
            onChange={e => setCompany(e.target.value)}
            autoFocus
          />
          <button
            className="btn-primary mt-auto w-full justify-center"
            disabled={slug(company.trim()).length < 2}
          >
            Sign in as buyer
          </button>
        </form>

        {/* Supplier (MSME) */}
        <div className="card flex flex-col p-5">
          <div className="mb-3 flex items-center gap-2 font-semibold text-slate-800">
            <Factory size={18} className="text-emerald-600" />Supplier (MSME)
          </div>
          <p className="mb-3 text-xs text-slate-500">
            See quote requests from buyers and send quotations.
          </p>
          <div className="space-y-2 mt-auto">
            {sellers?.map(s => (
              <button
                key={s.id}
                className="btn-ghost w-full justify-between py-1.5 text-xs"
                onClick={() => go({ role: 'seller', id: s.id, name: s.name })}
              >
                <span className="font-medium text-slate-700">{s.name}</span>
                <span className="text-[11px] text-slate-400">{s.city !== '—' ? s.city : ''}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Financial Institution (FI) */}
        <form className="card flex flex-col p-5" onSubmit={fiLogin}>
          <div className="mb-3 flex items-center gap-2 font-semibold text-slate-800">
            <Landmark size={18} className="text-purple-600" />Financial Institution (FI)
          </div>
          <p className="mb-3 text-xs text-slate-500">
            Assess SME capability, evaluate lending risk, and fund opportunities.
          </p>
          <label className="mb-1 block text-xs font-medium text-slate-600">Institution name</label>
          <input
            className="input mb-3"
            placeholder="e.g. SBI, HDFC, MetalCapital"
            value={fiCompany}
            onChange={e => setFiCompany(e.target.value)}
          />
          <button
            className="btn-primary mt-auto w-full justify-center !bg-purple-600 hover:!bg-purple-700"
            disabled={slug(fiCompany.trim()).length < 2}
          >
            Sign in as FI
          </button>
        </form>
      </div>
      <p className="mt-4 text-center text-xs text-slate-400">
        Each browser tab keeps its own sign-in, so you can be a buyer in one tab, a supplier in another, and an FI in a third.
      </p>
    </div>
  )
}
