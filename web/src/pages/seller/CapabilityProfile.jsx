import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Building2, CheckCircle2, Factory } from 'lucide-react'
import { api, getSession } from '../../api'
import { ErrorBox, Spinner } from '../../components/ui.jsx'

function DataPointCard({ label, value, source, isFi }) {
  let displayValue = value
  let valueColor = 'text-slate-900'

  const str = value != null ? String(value).trim() : ''

  if (str.toLowerCase() === 'yes') {
    displayValue = (
      <span className="flex items-center gap-1.5 text-emerald-700">
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" className="shrink-0">
          <circle cx="8" cy="8" r="8" fill="#10B981" fillOpacity="0.2" />
          <path d="M5 8l2 2 4-4" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Yes
      </span>
    )
    valueColor = 'text-emerald-700'
  } else if (str.toLowerCase() === 'no') {
    displayValue = (
      <span className="flex items-center gap-1.5 text-slate-700">
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" className="shrink-0">
          <circle cx="8" cy="8" r="8" fill="#EF4444" fillOpacity="0.15" />
          <path d="M5 5l6 6m0-6l-6 6" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" />
        </svg>
        No
      </span>
    )
    valueColor = 'text-slate-800'
  } else if (!str || str.toLowerCase() === 'null' || str.toLowerCase() === 'not available') {
    displayValue = 'Not available'
    valueColor = 'text-slate-400 font-normal italic'
  }

  return (
    <div className={`relative flex flex-col rounded-xl border border-slate-200 bg-white p-5 ${isFi ? 'hover:border-purple-300' : 'hover:border-indigo-300'} hover:shadow-sm transition-all h-full`}>
      <span className="text-[11px] font-bold text-slate-500 mb-2 uppercase tracking-[0.06em]">
        {label}
      </span>
      <div className={`text-base font-bold mb-4 leading-tight ${valueColor} whitespace-pre-line`}>
        {displayValue}
      </div>
      <div className="mt-auto pt-3 border-t border-slate-100">
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-50 text-[10px] font-bold text-slate-500 uppercase tracking-widest border border-slate-100">
          {source}
        </span>
      </div>
    </div>
  )
}

function DomainAccordion({ category, points, sellerValues, defaultOpen, isFi }) {
  const [open, setOpen] = useState(defaultOpen)
  const filledCount = points.filter(p => {
    const v = sellerValues[p.id]
    return v != null && String(v).trim() !== '' && String(v).toLowerCase() !== 'null' && String(v).toLowerCase() !== 'not available'
  }).length

  return (
    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden mb-3 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 sm:p-5 hover:bg-slate-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3.5">
          <div className={`flex items-center justify-center w-6 h-6 rounded-md transition-colors ${
            open
              ? isFi ? 'bg-purple-100 text-purple-700' : 'bg-indigo-100 text-indigo-700'
              : 'bg-slate-100 text-slate-400'
          }`}>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className={`transition-transform duration-200 ${open ? 'rotate-90' : ''}`}>
              <path d="M5 2L11 8L5 14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="font-bold text-sm text-slate-900 uppercase tracking-wide">{category.label}</span>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="text-xs text-slate-500 hidden sm:inline">
            <b className="text-slate-800">{filledCount}</b> of {points.length} verified
          </span>
          <span className="text-xs font-semibold text-slate-600 px-3 py-1 rounded-full bg-slate-100">
            {points.length} data points
          </span>
        </div>
      </button>

      {open && (
        <div className="p-4 sm:p-5 bg-slate-50/50 border-t border-slate-100">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {points.map(pt => (
              <DataPointCard
                key={pt.id}
                label={pt.label}
                value={sellerValues[pt.id]}
                source={pt.source}
                isFi={isFi}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function CapabilityProfile() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sellerParam = searchParams.get('seller')

  const [catalog, setCatalog] = useState(null)
  const [activeSeller, setActiveSeller] = useState(null)
  const [allSellers, setAllSellers] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const session = getSession()
  const role = session?.role
  const isSeller = role === 'seller'
  const isFi = role === 'fi'

  useEffect(() => {
    const fetchMe = isSeller ? api.get('/seller/me').catch(() => null) : Promise.resolve(null)

    Promise.all([api.get('/catalog'), fetchMe, api.get('/sellers')])
      .then(([cat, me, sellers]) => {
        setCatalog(cat)
        setAllSellers(sellers)
        
        let initial = null
        if (isSeller) {
          // Under each supplier account, strictly lock to that company
          initial = sellers.find(s => s.id === session?.id || s.id === me?.id) || me || sellers[0]
        } else {
          if (sellerParam) {
            initial = sellers.find(s => s.id === sellerParam)
          }
          if (!initial && me?.id) {
            initial = sellers.find(s => s.id === me.id)
          }
          if (!initial && sellers && sellers.length > 0) {
            initial = sellers[0]
          }
        }
        setActiveSeller(initial)
        setLoading(false)
      })
      .catch(e => {
        setErr(e)
        setLoading(false)
      })
  }, [isSeller, sellerParam, session?.id])

  if (loading) return <Spinner label="Loading capability data points…" />
  if (err) return <ErrorBox error={err} />
  if (!catalog || !activeSeller) return null

  const sellerValues = activeSeller.values || {}
  const totalPoints = catalog.data_points.length
  const completedPoints = catalog.data_points.filter(p => {
    const v = sellerValues[p.id]
    return v != null && String(v).trim() !== '' && String(v).toLowerCase() !== 'null' && String(v).toLowerCase() !== 'not available'
  }).length
  const completionPct = Math.round((completedPoints / totalPoints) * 100)

  // Compute capability domain graph metrics for this specific company
  const domainGraph = catalog.categories.map(cat => {
    const points = catalog.data_points.filter(p => p.category === cat.id)
    const filled = points.filter(p => {
      const v = sellerValues[p.id]
      return v != null && String(v).trim() !== '' && String(v).toLowerCase() !== 'null' && String(v).toLowerCase() !== 'not available'
    }).length
    const pct = points.length ? Math.round((filled / points.length) * 100) : 0
    return {
      id: cat.id,
      label: cat.label,
      total: points.length,
      filled,
      pct,
    }
  })

  return (
    <div>
      {/* Supplier selector bar (only visible for FI assessing MSMEs; hidden for supplier accounts) */}
      {!isSeller && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <Factory size={15} className={isFi ? 'text-purple-600' : 'text-indigo-600'} />
            <span>Select MSME to Assess:</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {allSellers.map(s => {
              const isSelected = s.id === activeSeller.id
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => {
                    setActiveSeller(s)
                    setSearchParams({ seller: s.id })
                  }}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    isSelected
                      ? isFi ? 'bg-purple-600 text-white shadow-sm' : 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s.name} <span className="text-[10px] opacity-75">({s.category_label?.split(' ')[0] || s.category})</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Header matching Image 2 */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Capability Data Points</h1>
            <span className={`rounded px-2.5 py-0.5 text-xs font-semibold border flex items-center gap-1 ${
              isFi
                ? 'bg-purple-50 text-purple-700 border-purple-100'
                : 'bg-indigo-50 text-indigo-700 border-indigo-100'
            }`}>
              <Building2 size={12} /> {activeSeller.name} {activeSeller.city && activeSeller.city !== '—' ? `· ${activeSeller.city}` : ''}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500 max-w-xl">{activeSeller.profile}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <span className={`font-semibold ${isFi ? 'text-purple-600' : 'text-indigo-600'}`}>
              {totalPoints} structured data points across {catalog.categories.length} capability domains
            </span>
            <span className="text-slate-300">·</span>
            <span className="flex items-center gap-1 text-emerald-700 font-medium">
              <CheckCircle2 size={13} /> {completedPoints} verified data points ({completionPct}% completeness)
            </span>
          </div>
        </div>
        <div className="text-xs font-medium text-slate-400 flex items-center gap-1.5 flex-wrap max-w-sm sm:text-right sm:justify-end">
          <span className="font-bold text-slate-500 uppercase tracking-widest mr-1">Sources:</span>
          SME Survey &middot; OpportunityX &middot; MetalCapital &middot; Financials &middot; GST &middot; Certifications
        </div>
      </div>

      {/* Capability Graph for this specific company */}
      <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-4 border-b border-slate-100 gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold uppercase tracking-wider ${isFi ? 'text-purple-700' : 'text-indigo-700'}`}>
                Capability Graph & Domain Health
              </span>
              <span className="text-slate-300">·</span>
              <span className="text-xs font-semibold text-slate-800">{activeSeller.name}</span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Verified strength and data coverage across all 6 capability domains
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-[11px] text-slate-400 font-medium">Readiness Score</div>
              <div className="text-lg font-bold text-slate-900">{completionPct}%</div>
            </div>
            <div className={`h-11 w-11 rounded-xl flex flex-col items-center justify-center font-bold text-xs ${
              completionPct >= 75
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
            }`}>
              <span>{completedPoints}</span>
              <span className="text-[9px] font-normal opacity-70">/ {totalPoints}</span>
            </div>
          </div>
        </div>

        {/* 6 Domain Bar Graph Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {domainGraph.map(domain => {
            let barColor = 'bg-emerald-500'
            let badgeColor = 'text-emerald-700 bg-emerald-50'
            if (domain.pct < 50) {
              barColor = 'bg-slate-400'
              badgeColor = 'text-slate-600 bg-slate-100'
            } else if (domain.pct < 75) {
              barColor = isFi ? 'bg-purple-500' : 'bg-indigo-500'
              badgeColor = isFi ? 'text-purple-700 bg-purple-50' : 'text-indigo-700 bg-indigo-50'
            }

            return (
              <div key={domain.id} className="rounded-lg border border-slate-100 bg-slate-50/70 p-3.5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-800 truncate pr-2" title={domain.label}>
                    {domain.label}
                  </span>
                  <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded ${badgeColor} shrink-0`}>
                    {domain.pct}%
                  </span>
                </div>
                {/* Visual score graph bar */}
                <div className="h-2 w-full rounded-full bg-slate-200/80 overflow-hidden mb-1.5">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${domain.pct}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px] text-slate-500">
                  <span>{domain.filled} of {domain.total} verified</span>
                  <span className="text-[10px] text-slate-400">data points</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 6 Domain Accordions */}
      <div className="space-y-3">
        {catalog.categories.map((cat, idx) => {
          const points = catalog.data_points.filter(p => p.category === cat.id)
          return (
            <DomainAccordion
              key={cat.id}
              category={cat}
              points={points}
              sellerValues={sellerValues}
              defaultOpen={idx === 0}
              isFi={isFi}
            />
          )
        })}
      </div>
    </div>
  )
}
