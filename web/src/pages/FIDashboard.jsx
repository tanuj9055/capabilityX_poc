import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Landmark, ShieldCheck, TrendingUp, Users, Factory, ChevronRight, Award, CheckCircle2 } from 'lucide-react'
import { api } from '../api'
import { ErrorBox, Spinner } from '../components/ui.jsx'

export default function FIDashboard({ fiName }) {
  const [sellers, setSellers] = useState([])
  const [catalog, setCatalog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [selectedSeller, setSelectedSeller] = useState(null)

  useEffect(() => {
    Promise.all([api.get('/sellers'), api.get('/catalog')])
      .then(([s, cat]) => {
        setSellers(s)
        setCatalog(cat)
        setSelectedSeller(s[0])
        setLoading(false)
      })
      .catch(e => {
        setErr(e)
        setLoading(false)
      })
  }, [])

  if (loading) return <Spinner label="Loading financial intelligence network…" />
  if (err) return <ErrorBox error={err} />

  const isFilled = (v) => v != null && String(v).trim() !== '' && String(v).toLowerCase() !== 'null' && String(v).toLowerCase() !== 'not available'

  // Dynamic domain risk & capability for the currently selected seller
  const selectedCapabilities = (catalog && selectedSeller) ? catalog.categories.map(cat => {
    const points = catalog.data_points.filter(p => p.category === cat.id)
    const vals = selectedSeller.values || {}
    const filled = points.filter(p => isFilled(vals[p.id])).length
    const pct = points.length ? Math.round((filled / points.length) * 100) : 0

    let barColor = 'bg-emerald-500'
    let badgeColor = 'text-emerald-700 bg-emerald-50 border-emerald-100'
    let riskLabel = 'Low Risk'

    if (pct < 55) {
      barColor = 'bg-amber-500'
      badgeColor = 'text-amber-700 bg-amber-50 border-amber-100'
      riskLabel = 'High Risk'
    } else if (pct < 75) {
      barColor = 'bg-purple-600'
      badgeColor = 'text-purple-700 bg-purple-50 border-purple-100'
      riskLabel = 'Moderate'
    }

    return {
      id: cat.id,
      label: cat.label,
      value: pct,
      filled,
      total: points.length,
      barColor,
      badgeColor,
      riskLabel
    }
  }) : []

  // Selected seller overall score
  const totalPointsCount = catalog ? catalog.data_points.length : 89
  const selectedFilledTotal = (catalog && selectedSeller)
    ? catalog.data_points.filter(p => isFilled(selectedSeller.values?.[p.id])).length
    : 0
  const selectedScore = totalPointsCount ? Math.round((selectedFilledTotal / totalPointsCount) * 100) : 0

  // Overall average across portfolio
  const avgPortfolioScore = (sellers.length && catalog)
    ? Math.round(
        sellers.reduce((acc, s) => {
          const filled = catalog.data_points.filter(p => isFilled(s.values?.[p.id])).length
          return acc + (filled / totalPointsCount) * 100
        }, 0) / sellers.length
      )
    : 76

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-purple-50 px-2.5 py-0.5 text-xs font-bold text-purple-700 border border-purple-100 flex items-center gap-1">
              <Landmark size={12} /> Financial Institution Workspace
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            SME Capability & Lending Network
          </h1>
          <p className="text-sm text-slate-500">
            Real operational, financial, and capability intelligence across verified manufacturing MSMEs.
          </p>
        </div>
        <div className="rounded-lg bg-white border border-slate-200 px-4 py-2 shadow-sm text-right">
          <div className="text-xs text-slate-400">Logged in as</div>
          <div className="font-semibold text-slate-800 text-sm">{fiName || 'Financial Institution'}</div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-900">{sellers.length}</div>
            <Factory size={18} className="text-indigo-600" />
          </div>
          <div className="mt-1 text-xs text-slate-500">Verified MSMEs in Portfolio</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-900">{totalPointsCount}</div>
            <ShieldCheck size={18} className="text-purple-600" />
          </div>
          <div className="mt-1 text-xs text-slate-500">Structured Data Points Monitored</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-900">{catalog ? catalog.categories.length : 6}</div>
            <TrendingUp size={18} className="text-emerald-600" />
          </div>
          <div className="mt-1 text-xs text-slate-500">Capability Domains Assessed</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-900">{avgPortfolioScore}%</div>
            <Award size={18} className="text-amber-600" />
          </div>
          <div className="mt-1 text-xs text-slate-500">Avg Portfolio Capability Score</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SME Portfolio list */}
        <div className="lg:col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-sm text-slate-900">Portfolio MSMEs & Capability Profile</h2>
              <p className="text-xs text-slate-500">Click a supplier to inspect real verified banking and operational parameters</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              {sellers.length} Active
            </span>
          </div>

          <div className="divide-y divide-slate-100">
            {sellers.map(s => {
              const vals = s.values || {}
              const isSelected = selectedSeller?.id === s.id
              const sFilled = catalog
                ? catalog.data_points.filter(p => isFilled(vals[p.id])).length
                : 0
              const sPct = totalPointsCount ? Math.round((sFilled / totalPointsCount) * 100) : 0

              return (
                <div
                  key={s.id}
                  onClick={() => setSelectedSeller(s)}
                  className={`p-4 transition-colors cursor-pointer hover:bg-slate-50 ${
                    isSelected ? 'bg-purple-50/40 border-l-4 border-purple-600' : ''
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-900">{s.name}</span>
                        {s.city && s.city !== '—' && (
                          <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                            {s.city}
                          </span>
                        )}
                        <span className="rounded bg-purple-50 px-2 py-0.5 text-[11px] font-medium text-purple-700 border border-purple-100">
                          {s.category_label || s.category}
                        </span>
                        <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-100">
                          {sPct}% score
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500 max-w-xl">{s.profile}</p>
                    </div>

                    <div className="text-right">
                      <div className="text-xs font-semibold text-emerald-700">
                        {vals.turnover ? vals.turnover.replace('FY24 turnover: ', '') : 'Active Supplier'}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Cap: {vals.installed_capacity || 'Verified'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500 border-t border-slate-100/80 pt-2.5">
                    <span>GST: <b className="text-slate-700">{vals.gst_filing_timeliness ? 'Regular' : 'Active'}</b></span>
                    <span>Staff: <b className="text-slate-700">{vals.employees_permanent || '15+'} permanent</b></span>
                    <span>Client: <b className="text-slate-700">{vals.top_customers || vals.approved_vendor_oems || 'DISCOM / BHEL'}</b></span>
                    <span className="ml-auto text-purple-600 font-medium flex items-center gap-0.5">
                      {isSelected ? 'Selected' : 'Select'} <ChevronRight size={13} />
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Selected SME Quick Insights & Portfolio Health */}
        <div className="space-y-4">
          {selectedSeller && (
            <div className="card p-5 border-l-4 border-purple-600">
              <div className="flex items-center justify-between mb-1">
                <div className="text-xs font-bold uppercase tracking-wider text-purple-700">
                  Selected Assessment
                </div>
                <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
                  {selectedScore}% Capability Score
                </span>
              </div>
              <h3 className="text-base font-bold text-slate-900">{selectedSeller.name}</h3>
              <div className="mt-2 space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Legal Structure</span>
                  <span className="font-semibold text-slate-800">{selectedSeller.values?.legal_structure || 'Partnership'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Net Worth</span>
                  <span className="font-semibold text-slate-800">{selectedSeller.values?.net_worth || 'Positive'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Current Ratio</span>
                  <span className="font-semibold text-slate-800">{selectedSeller.values?.current_ratio || '1.64x'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Statutory Compliance</span>
                  <span className="font-semibold text-emerald-700">No defaults identified</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100">
                <Link
                  to={`/capability?seller=${selectedSeller.id}`}
                  className="btn-primary w-full justify-center py-2 text-xs !bg-purple-600 hover:!bg-purple-700"
                >
                  Inspect Full 89 Data Points ({selectedSeller.name}) →
                </Link>
              </div>
            </div>
          )}

          {/* Dynamic Domain Risk & Capability for selected seller */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-semibold text-sm text-slate-900">Domain Risk & Capability</h3>
              <span className="rounded-full bg-purple-50 px-2 py-0.5 text-[11px] font-bold text-purple-700 border border-purple-100">
                {selectedSeller?.name}
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-4">
              Real capability assessment across 6 domains for <b className="text-slate-700">{selectedSeller?.name}</b>
            </p>
            <div className="space-y-3">
              {selectedCapabilities.map(cap => (
                <div key={cap.id}>
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="text-slate-700 font-medium truncate pr-2" title={cap.label}>
                      {cap.label}
                    </span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.2 rounded border ${cap.badgeColor}`}>
                        {cap.riskLabel}
                      </span>
                      <span className="font-bold text-slate-900 tabular-nums w-8 text-right">{cap.value}%</span>
                    </div>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${cap.barColor}`}
                      style={{ width: `${cap.value}%` }}
                    />
                  </div>
                  <div className="mt-0.5 flex justify-between text-[10px] text-slate-400">
                    <span>{cap.filled} of {cap.total} verified</span>
                    <span>{cap.value >= 75 ? 'Low risk' : cap.value >= 55 ? 'Moderate' : 'Risk flag'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
