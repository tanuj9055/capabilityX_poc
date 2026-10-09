import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Spinner } from '../components/ui.jsx'

export default function RfqRedirect() {
  const { id } = useParams()
  const [rfq, setRfq] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api.get(`/rfqs/${id}`).then(setRfq).catch(setErr) }, [id])
  if (err) return <ErrorBox error={err} />
  if (!rfq) return <Spinner label="Loading…" />
  const step = { draft: 'build', review: 'review', results: 'results' }[rfq.status]
  return <Navigate replace to={`/rfq/${id}/${step}`} />
}
