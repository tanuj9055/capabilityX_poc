// Renders the RFQ blocks (same structure the backend writes into the .docx).
// Unfilled required values come back as "[Label?]" and are highlighted.
const mark = (text) => {
  const parts = String(text).split(/(\[[^\]]+\?\])/g)
  return parts.map((p, i) => /^\[[^\]]+\?\]$/.test(p)
    ? <span key={i} className="rounded bg-amber-200 px-1 text-amber-900">{p}</span>
    : p)
}

export default function Preview({ blocks }) {
  let num = 0
  return (
    <div className="space-y-2 text-[13px] leading-relaxed">
      {blocks.map((b, i) => {
        if (b.t !== 'num') num = 0
        switch (b.t) {
          case 'title': return <h1 key={i} className="text-2xl font-semibold text-[#17365D]">{b.text}</h1>
          case 'sub': return <div key={i} className="text-base text-slate-600">{mark(b.text)}</div>
          case 'h1': return <h2 key={i} className="mt-5 border-b border-slate-200 pb-1 text-base font-semibold text-[#17365D]">{b.text}</h2>
          case 'h2': return <h3 key={i} className="mt-3 text-sm font-semibold text-[#17365D]">{mark(b.text)}</h3>
          case 'bullet': return <div key={i} className="flex gap-2 pl-2"><span>•</span><span>{mark(b.text)}</span></div>
          case 'num': num += 1; return <div key={i} className="flex gap-2 pl-2"><span>{num}.</span><span>{mark(b.text)}</span></div>
          case 'table': return (
            <div key={i} className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <tbody>
                  {b.rows.map((r, j) => (
                    <tr key={j} className={j === 0 && b.header ? 'bg-[#17365D] text-white' : 'odd:bg-white even:bg-slate-50'}>
                      {r.map((c, k) => <td key={k} className={`border border-slate-200 px-2 py-1 ${j === 0 && b.header ? 'font-semibold' : ''}`}>{mark(c)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
          default: return <p key={i}>{mark(b.text)}</p>
        }
      })}
    </div>
  )
}
