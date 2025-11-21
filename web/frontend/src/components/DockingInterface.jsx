import { useState } from 'react'
import useAuthStore, { api } from './useAuthStore'

export default function DockingInterface() {
  const token = useAuthStore((s) => s.accessToken)
  const [smiles, setSmiles] = useState('CC(=O)Oc1ccccc1C(=O)O')
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!token) return
    setLoading(true)
    setStatus(null)
    try {
      const res = await api.post('/dock', { smiles })
      setStatus(res.data)
    } catch (err) {
      setStatus({ error: err.response?.data?.detail || 'Docking failed' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h3>Docking Runner</h3>
      <div className="form-row">
        <label>Ligand SMILES</label>
        <input className="input" value={smiles} onChange={(e) => setSmiles(e.target.value)} />
      </div>
      <button className="button" onClick={submit} disabled={loading || !token}>
        {loading ? 'Submitting...' : 'Run Docking'}
      </button>
      {status && (
        <div style={{ marginTop: 16 }}>
          {status.error ? (
            <div style={{ color: '#ffb3b3' }}>{status.error}</div>
          ) : (
            <div>
              <div>Job ID: {status.job_id}</div>
              <div>Affinity (kcal/mol): {status.affinity}</div>
              <div>Estimated Ki (nM): {status.ki}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
