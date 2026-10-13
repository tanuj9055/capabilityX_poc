import { Component, useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { LogOut, Plus } from 'lucide-react'
import { api, getSession, setSession } from './api'
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
import PurchaseOrder from './pages/PurchaseOrder.jsx'
import Profile from './pages/Profile.jsx'
import PurchaseOrders from './pages/seller/PurchaseOrders.jsx'
import PurchaseOrderView from './pages/seller/PurchaseOrderView.jsx'
import CapabilityProfile from './pages/seller/CapabilityProfile.jsx'
import FIDashboard from './pages/FIDashboard.jsx'

export default function App() {
  const [session, setS] = useState(getSession)
  const nav = useNavigate()
  const loc = useLocation()
  const logout = () => { setSession(null); setS(null); nav('/') }
  const role = session?.role
  const buyer = role === 'buyer'
  const fi = role === 'fi'
  const seller = role === 'seller'

  // supplier notification: unread purchase orders, refreshed on every page change
  const [unread, setUnread] = useState(0)
  const refreshUnread = () => api.get('/seller/pos').then(r => setUnread(r.filter(x => x.unread).length)).catch(() => {})
  useEffect(() => { if (session?.role === 'seller') refreshUnread() }, [session, loc.pathname])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-indigo-700">
            CapabilityX <span className="text-xs font-normal text-slate-400">
              {seller ? 'supplier portal' : fi ? 'financial institution workspace' : 'supplier capability match'}
            </span>
          </Link>
          {session && (
            <div className="flex items-center gap-4 text-sm">
              {buyer && <>
                <Link to="/" className="text-slate-600 hover:text-indigo-700">My RFQs</Link>
                <Link to="/quotes" className="text-slate-600 hover:text-indigo-700">Quote Evaluation</Link>
                <Link to="/profile" className="text-slate-600 hover:text-indigo-700">Profile</Link>
                <Link to="/new" className="btn-primary"><Plus size={14} />New RFQ</Link>
              </>}
              {seller && <>
                <Link to="/" className={`hover:text-indigo-700 ${loc.pathname === '/' ? 'font-medium text-indigo-700' : 'text-slate-600'}`}>Quote Requests</Link>
                <Link to="/pos" className="flex items-center gap-1 text-slate-600 hover:text-indigo-700">Purchase Orders
                  {unread > 0 && <span className="rounded-full bg-red-600 px-1.5 text-[11px] font-semibold text-white" title={`${unread} new purchase order${unread > 1 ? 's' : ''}`}>{unread}</span>}</Link>
                <Link to="/capability" className={`hover:text-indigo-700 ${loc.pathname === '/capability' ? 'font-medium text-indigo-700' : 'text-slate-600'}`}>Capability Data Points</Link>
              </>}
              {fi && <>
                <Link to="/" className={`hover:text-purple-700 ${loc.pathname === '/' ? 'font-medium text-purple-700' : 'text-slate-600'}`}>SME Network</Link>
                <Link to="/capability" className={`hover:text-purple-700 ${loc.pathname === '/capability' ? 'font-medium text-purple-700' : 'text-slate-600'}`}>Capability Data Points</Link>
              </>}
              <span className="text-xs text-slate-500">
                {buyer ? 'Buyer' : fi ? 'FI' : 'Supplier'} · <b className="text-slate-700">{session.name}</b>
              </span>
              <button className="text-slate-400 hover:text-red-600" title="Sign out" onClick={logout}><LogOut size={16} /></button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <PageErrorBoundary key={loc.pathname}>
        {!session ? (
          <Login onLogin={(s) => { setS(s); nav('/') }} />
        ) : buyer ? (
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
            <Route path="/quotes/:id/po" element={<PurchaseOrder />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/capability" element={<CapabilityProfile />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        ) : fi ? (
          <Routes>
            <Route path="/" element={<FIDashboard fiName={session.name} />} />
            <Route path="/capability" element={<CapabilityProfile />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        ) : (
          <Routes>
            <Route path="/" element={<QuoteRequests />} />
            <Route path="/capability" element={<CapabilityProfile />} />
            <Route path="/requests/:qid" element={<QuoteRequest />} />
            <Route path="/pos" element={<PurchaseOrders />} />
            <Route path="/pos/:pid" element={<PurchaseOrderView onRead={refreshUnread} />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        )}
        </PageErrorBoundary>
      </main>
    </div>
  )
}

// A render error in one page shows a message instead of blanking the app; keyed on the path, so
// navigating (or Back) resets it.
class PageErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="card p-6 text-sm">
        <p className="font-medium text-red-700">This page hit an error and couldn't be shown.</p>
        <p className="mt-1 text-slate-500">{String(this.state.error.message || this.state.error)}</p>
      </div>
    )
  }
}
