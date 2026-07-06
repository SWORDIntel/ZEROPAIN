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
      <div className="card-header">
        <div>
          <div className="eyebrow">Molecular docking</div>
          <h3>Docking Runner</h3>
        </div>
        {status?.provenance && (
          <span className={status.provenance.decision_grade === 'true' ? 'badge' : 'badge warning'}>
            {status.provenance.decision_grade === 'true' ? 'decision grade' : 'research only'}
          </span>
        )}
      </div>
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
            <div className="grid two nested">
              <div className="stat">
                <div className="eyebrow">Affinity</div>
                <div className="stat-value">{status.affinity}</div>
                <div className="muted">kcal/mol</div>
              </div>
              <div className="stat">
                <div className="eyebrow">Estimated Ki</div>
                <div className="stat-value">{status.ki}</div>
                <div className="muted">nM</div>
              </div>
              <div className="provenance-panel full-span">
                <div className="status-line">
                  <span className="badge warning">non-decision-grade</span>
                  <span className="muted">Job ID: {status.job_id}</span>
                  {status.job_record_id && <span className="muted">Record: {status.job_record_id}</span>}
                  <span className="muted">Backend: {status.backend}</span>
                  <span className="muted">Device: {status.device}</span>
                  <span className="muted">Poses: {status.poses}</span>
                </div>
                {status.provenance && (
                  <div className="provenance-grid">
                    <span>Engine: {status.provenance.engine}</span>
                    <span>Model: {status.provenance.model}</span>
                    <span>Mode: {status.provenance.mode}</span>
                    {status.provenance.training_profile && <span>Training: {status.provenance.training_profile}</span>}
                    {status.provenance.input_hash && <span>Input hash: {status.provenance.input_hash.slice(0, 18)}</span>}
                    {status.provenance.model_hash && <span>Model hash: {status.provenance.model_hash.slice(0, 18)}</span>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
