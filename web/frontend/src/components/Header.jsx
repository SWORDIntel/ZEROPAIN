import useAuthStore from './useAuthStore'

export default function Header() {
  const { user, logout, accessToken } = useAuthStore()

  return (
    <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div>
        <div style={{ fontSize: 12, color: '#7ba0bf' }}>TEMPEST Class C</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>ZeroPain Operations Console</div>
      </div>
      {accessToken && (
        <div className="inline-actions">
          <span className="badge">{user?.role || 'operator'}</span>
          <span>{user?.username || 'anon'}</span>
          <button className="button secondary" onClick={logout}>Logout</button>
        </div>
      )}
    </div>
  )
}
