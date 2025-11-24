import useAuthStore from './useAuthStore'
import useUiSettings from './useUiSettings'

export default function Header() {
  const { user, logout, accessToken } = useAuthStore()
  const ui = useUiSettings()

  return (
    <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div>
        <div style={{ fontSize: 12, color: '#7ba0bf' }}>TEMPEST Class C</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>ZeroPain Operations Console</div>
        <div className="muted" style={{ fontSize: 12 }}>
          Backend: {ui.backend} • Resume: {ui.resume ? 'on' : 'off'} • Batch: {ui.batch_size}
        </div>
      </div>
      {accessToken && (
        <div className="inline-actions">
          <button className="button secondary" onClick={() => ui.update({ animations: !ui.animations })}>
            Animations {ui.animations ? 'on' : 'off'}
          </button>
          <span className="badge">{user?.role || 'operator'}</span>
          <span>{user?.username || 'anon'}</span>
          <button className="button secondary" onClick={logout}>Logout</button>
        </div>
      )}
    </div>
  )
}
