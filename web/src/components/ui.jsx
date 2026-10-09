import { Loader2 } from 'lucide-react'

export const Spinner = ({ label }) => (
  <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="animate-spin" size={16} />{label}</div>
)

export const Busy = ({ label }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/70 backdrop-blur-sm">
    <div className="card flex items-center gap-3 px-6 py-4 text-sm"><Loader2 className="animate-spin text-indigo-600" />{label}</div>
  </div>
)

export const ErrorBox = ({ error }) => error ? (
  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{String(error.message || error)}</div>
) : null

const STATUS = {
  draft: 'bg-slate-100 text-slate-700', review: 'bg-amber-100 text-amber-800', results: 'bg-emerald-100 text-emerald-800',
  full: 'bg-emerald-100 text-emerald-800', partial: 'bg-amber-100 text-amber-800', not: 'bg-red-100 text-red-700',
  na: 'bg-slate-100 text-slate-600', unmapped: 'bg-slate-100 text-slate-400', skipped: 'bg-slate-50 text-slate-400 border border-dashed border-slate-300',
  mandatory: 'bg-rose-50 text-rose-700 border border-rose-200', scored: 'bg-sky-50 text-sky-700 border border-sky-200',
  sent: 'bg-sky-100 text-sky-800', viewed: 'bg-violet-100 text-violet-800', quoted: 'bg-emerald-100 text-emerald-800',
  declined: 'bg-slate-200 text-slate-700', expired: 'bg-red-100 text-red-700',
  accepted: 'bg-emerald-600 text-white', not_selected: 'bg-slate-100 text-slate-500',
  error: 'bg-red-100 text-red-700', warn: 'bg-amber-100 text-amber-800',
}
const LABEL = {
  full: 'Met', partial: 'Partial', not: 'Not met', na: 'Data not available', unmapped: 'Not covered', skipped: 'Not assessed', results: 'matched',
  sent: 'Sent', viewed: 'Viewed', quoted: 'Quoted', declined: 'Declined', expired: 'Expired', accepted: 'Accepted', not_selected: 'Not selected',
}

export const Badge = ({ k, children }) => (
  <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${STATUS[k] || 'bg-slate-100'}`}>
    {children || LABEL[k] || k}
  </span>
)

export const ScoreBar = ({ value }) => (
  <div className="flex items-center gap-2">
    <div className="h-2 w-24 rounded bg-slate-200">
      <div className={`h-2 rounded ${value >= 70 ? 'bg-emerald-500' : value >= 40 ? 'bg-amber-500' : 'bg-red-400'}`} style={{ width: `${value}%` }} />
    </div>
    <span className="w-10 text-right text-xs tabular-nums">{Math.round(value)}</span>
  </div>
)

export const Steps = ({ status }) => {
  const steps = [['draft', 'Build'], ['review', 'Review'], ['results', 'Results']]
  const i = steps.findIndex(s => s[0] === status)
  return (
    <div className="flex items-center gap-2 text-xs">
      {steps.map(([k, l], j) => (
        <span key={k} className={`rounded-full px-3 py-1 ${j <= i ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-500'}`}>{j + 1}. {l}</span>
      ))}
    </div>
  )
}
