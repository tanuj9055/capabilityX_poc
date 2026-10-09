import { useEffect, useState } from 'react'

// One slot input: chips for choice/level/multi, text box for the rest.
// onCommit fires with the final value (chips: immediately; text: on blur / Enter).
export default function SlotField({ slot, value, onCommit, compact }) {
  const [text, setText] = useState(value ?? '')
  useEffect(() => { setText(value ?? '') }, [value])

  if (slot.type === 'choice' || slot.type === 'level') {
    return (
      <div className="flex flex-wrap gap-1.5">
        {slot.options.map(o => (
          <button key={o} type="button" onClick={() => onCommit(o)}
            className={`chip ${value === o ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-700 hover:border-indigo-400'}`}>
            {o}
          </button>
        ))}
      </div>
    )
  }
  if (slot.type === 'multi') {
    const cur = Array.isArray(value) ? value : []
    const toggle = (o) => onCommit(cur.includes(o) ? cur.filter(x => x !== o) : [...cur, o])
    return (
      <div className="flex flex-wrap gap-1.5">
        {slot.options.map(o => (
          <button key={o} type="button" onClick={() => toggle(o)}
            className={`chip ${cur.includes(o) ? 'border-indigo-600 bg-indigo-100 text-indigo-800' : 'border-slate-300 bg-white text-slate-700 hover:border-indigo-400'}`}>
            {cur.includes(o) ? '✓ ' : ''}{o}
          </button>
        ))}
      </div>
    )
  }
  const commit = () => { if (String(text) !== String(value ?? '')) onCommit(text) }
  return (
    <div className="flex items-center gap-2">
      <input className={`input ${compact ? 'py-1' : ''}`} value={text} placeholder={slot.hint || ''}
        type={slot.type === 'number' ? 'number' : 'text'}
        onChange={e => setText(e.target.value)} onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); commit() } }} />
      {slot.unit && <span className="whitespace-nowrap text-xs text-slate-500">{slot.unit}</span>}
    </div>
  )
}
