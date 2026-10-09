import { useState } from 'react'
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { LogOut, Plus } from 'lucide-react'
import { getSession, setSession } from './api'
import Login from './pages/Login.jsx'
import Home from './pages/Home.jsx'
import NewRfq from './pages/NewRfq.jsx'
import Builder from './pages/Builder.jsx'
import Review from './pages/Review.jsx'
import Results from './pages/Results.jsx'
import SellerDetail from './pages/SellerDetail.jsx'
import RfqRedirect from './pages/RfqRedirect.jsx'
import QuoteEvaluation from './pages/QuoteEvaluation.jsx'
import QuoteEvalRfq from './pages/QuoteEvalRfq.jsx'
import QuoteRequests from './pages/seller/QuoteRequests.jsx'
import QuoteRequest from './pages/seller/QuoteRequest.jsx'

export default function App() {
  const [session, setS] = useState(getSession)
  const nav = useNavigate()
  const logout = () => { setSession(null); setS(null); nav('/') }
  const buyer = session?.role === 'buyer'

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-indigo-700">CapabilityX <span className="text-xs font-normal text-slate-400">{session?.role === 'seller' ? 'supplier portal' : 'supplier capability match'}</span></Link>
          {session && (
            <div className="flex items-center gap-4 text-sm">
              {buyer ? <>
                <Link to="/" className="text-slate-600 hover:text-indigo-700">My RFQs</Link>
                <Link to="/quotes" className="text-slate-600 hover:text-indigo-700">Quote Evaluation</Link>
                <Link to="/new" className="btn-primary"><Plus size={14} />New RFQ</Link>
              </> : <Link to="/" className="text-slate-600 hover:text-indigo-700">Quote Requests</Link>}
              <span className="text-xs text-slate-500">{buyer ? 'Buyer' : 'Supplier'} · <b className="text-slate-700">{session.name}</b></span>
              <button className="text-slate-400 hover:text-red-600" title="Sign out" onClick={logout}><LogOut size={16} /></button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        {!session ? <Login onLogin={(s) => { setS(s); nav('/') }} /> : buyer ? (
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/new" element={<NewRfq />} />
            <Route path="/rfq/:id" element={<RfqRedirect />} />
            <Route path="/rfq/:id/build" element={<Builder />} />
            <Route path="/rfq/:id/review" element={<Review />} />
            <Route path="/rfq/:id/results" element={<Results />} />
            <Route path="/rfq/:id/sellers/:sid" element={<SellerDetail />} />
            <Route path="/quotes" element={<QuoteEvaluation />} />
            <Route path="/quotes/:id" element={<QuoteEvalRfq />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        ) : (
          <Routes>
            <Route path="/" element={<QuoteRequests />} />
            <Route path="/requests/:qid" element={<QuoteRequest />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        )}
      </main>
    </div>
  )
}
