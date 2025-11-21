import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import useAuthStore from './useAuthStore'

export default function Login() {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const { login, loading, error } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSubmit = async (e) => {
    e.preventDefault()
    const ok = await login(username, password)
    if (ok) {
      const from = location.state?.from?.pathname || '/'
      navigate(from)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 400 }}>
      <h3>Secure Login</h3>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <label>Username</label>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="form-row">
          <label>Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <div style={{ color: '#ffb3b3', marginBottom: 12 }}>{error}</div>}
        <button className="button" type="submit" disabled={loading}>
          {loading ? 'Signing in...' : 'Login'}
        </button>
      </form>
    </div>
  )
}
