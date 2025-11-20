import { useEffect } from 'react'
import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Dashboard from './components/Dashboard'
import Login from './components/Login'
import CompoundBrowser from './components/CompoundBrowser'
import DockingInterface from './components/DockingInterface'
import ADMETDashboard from './components/ADMETDashboard'
import useAuthStore from './components/useAuthStore'

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

  useEffect(() => {
    loadFromStorage()
    hydrateUser()
  }, [loadFromStorage, hydrateUser])

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
            path="/admet"
            element={
              <ProtectedRoute>
                <ADMETDashboard />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  )
}
