// Structured tender understanding (AI-extracted for uploads, built from the fields for chat/template RFQs).
const FIELDS = [
  ['item', 'Item'], ['quantity', 'Quantity'], ['contract_period', 'Contract period'],
  ['delivery_location', 'Delivery location'], ['delivery_schedule', 'Delivery schedule'],
  ['payment_terms', 'Payment terms'], ['commercial_terms', 'Commercial terms'],
]

export default function Understanding({ u, summary }) {
  if (!u) return summary ? <p className="text-sm">{summary}</p> : null
  const fields = FIELDS.filter(([k]) => u[k])
  return (
    <div className="space-y-4 text-sm">
      {summary && <p>{summary}</p>}
      {fields.length > 0 && (
        <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
          {fields.map(([k, l]) => (
            <div key={k}>
              <div className="text-[11px] uppercase tracking-wide text-slate-400">{l}</div>
              <div className="font-medium">{u[k]}</div>
            </div>
          ))}
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        {u.technical_specs?.length > 0 && (
          <Section title="Technical specs">
            {u.technical_specs.map((x, i) => <Row key={i} l={x.label} v={x.value} />)}
          </Section>
        )}
        {u.key_dates?.length > 0 && (
          <Section title="Key dates">
            {u.key_dates.map((x, i) => <Row key={i} l={x.label} v={x.date} />)}
          </Section>
        )}
        {u.documents_required?.length > 0 && (
          <Section title="Documents required">
            <ul className="list-disc pl-4 text-xs">{u.documents_required.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </Section>
        )}
      </div>
      {u.evaluation_basis && (
        <div className="text-xs text-slate-600"><span className="font-semibold text-slate-500">Evaluation: </span>{u.evaluation_basis}</div>
      )}
    </div>
  )
}

const Section = ({ title, children }) => (
  <div className="rounded-md border border-slate-200 p-3">
    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</div>
    {children}
  </div>
)
const Row = ({ l, v }) => (
  <div className="flex gap-2 text-xs"><span className="w-28 shrink-0 text-slate-500">{l}</span><span>{v}</span></div>
)
