import { Plus, Trash2 } from 'lucide-react'

// Small editable grid: rows of strings under fixed column names.
export default function TableEdit({ cols, rows, on, edit = true }) {
  const setCell = (i, j, v) => on(rows.map((r, a) => a === i ? r.map((c, b) => b === j ? v : c) : r))
  if (!edit) {
    return rows.length === 0 ? <p className="text-sm text-slate-400">None</p> : (
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr>{cols.map(c => <th key={c} className="px-2 py-1 font-medium">{c}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="px-2 py-1 align-top">{c}</td>)}</tr>)}</tbody>
      </table>
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs text-slate-500">
          <tr>{cols.map(c => <th key={c} className="px-1 py-1 font-medium">{c}</th>)}<th className="w-6" /></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((_, j) => (
                <td key={j} className="px-1 py-0.5 align-top">
                  <textarea className="input min-h-0 py-1 text-sm" rows={Math.min(4, Math.max(1, Math.ceil(((r[j] || '').length + 1) / 40)))}
                    value={r[j] || ''} onChange={e => setCell(i, j, e.target.value)} />
                </td>
              ))}
              <td className="px-1 align-top"><button className="mt-1.5 text-slate-400 hover:text-red-600" title="Remove row" onClick={() => on(rows.filter((_, a) => a !== i))}><Trash2 size={14} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="mt-1 text-xs text-indigo-600" onClick={() => on([...rows, cols.map(() => '')])}><Plus size={12} className="inline" /> Add row</button>
    </div>
  )
}
