import { NavLink } from 'react-router-dom'
import useAuthStore from './useAuthStore'

export default function Sidebar() {
  const { accessToken } = useAuthStore()
  return (
    <aside className="sidebar">
      <h1>ZeroPain</h1>
      {accessToken ? (
        <nav>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/">
            Dashboard
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/compounds">
            Compounds
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/builder">
            Builder
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/docking">
            Docking
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/admet">
            ADMET
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/simulation">
            Simulation
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/runs">
            Runs
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/settings">
            Settings
          </NavLink>
        </nav>
      ) : (
        <NavLink className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} to="/login">
          Login
        </NavLink>
      )}
    </aside>
  )
}
