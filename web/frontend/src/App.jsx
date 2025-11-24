import { useEffect } from 'react'
import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import Login from './components/Login'
import CompoundBrowser from './components/CompoundBrowser'
import CompoundBuilder from './components/CompoundBuilder'
import DockingInterface from './components/DockingInterface'
import ADMETDashboard from './components/ADMETDashboard'
import RunDashboard from './components/RunDashboard'
import Simulation from './components/Simulation'
import Settings from './components/Settings'
import useAuthStore from './components/useAuthStore'
import useUiSettings from './components/useUiSettings'

function ProtectedRoute({ children }) {
  const token = useAuthStore((s) => s.accessToken)
  const location = useLocation()
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

export default function App() {
  const { loadFromStorage, hydrateUser } = useAuthStore()
  const { hydrate, animations } = useUiSettings()

  useEffect(() => {
    loadFromStorage()
    hydrateUser()
    hydrate()
  }, [hydrate, loadFromStorage, hydrateUser])

  useEffect(() => {
    document.body.classList.toggle('reduced-motion', !animations)
  }, [animations])

  return (
    <div className="layout">
      <Sidebar />
      <main className="main">
        <Header />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/compounds"
            element={
              <ProtectedRoute>
                <CompoundBrowser />
              </ProtectedRoute>
            }
          />
          <Route
            path="/docking"
            element={
              <ProtectedRoute>
                <DockingInterface />
              </ProtectedRoute>
            }
          />
          <Route
            path="/builder"
            element={
              <ProtectedRoute>
                <CompoundBuilder />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admet"
            element={
              <ProtectedRoute>
                <ADMETDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/simulation"
            element={
              <ProtectedRoute>
                <Simulation />
              </ProtectedRoute>
            }
          />
          <Route
            path="/runs"
            element={
              <ProtectedRoute>
                <RunDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  )
}
