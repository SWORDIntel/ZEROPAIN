import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import useAuthStore, { api } from './useAuthStore'
import useUiSettings from './useUiSettings'

export default function RunDashboard() {
  const token = useAuthStore((s) => s.accessToken)
  const ui = useUiSettings()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['runs'],
    queryFn: async () => {
      const res = await api.get('/runs')
      return res.data.runs
    },
    enabled: !!token,
    refetchInterval: ui.pollIntervalMs,
  })
  const [selected, setSelected] = useState(null)
  const detailsQuery = useQuery({
    queryKey: ['run-detail', selected],
    queryFn: async () => {
      if (!selected) return null
      const res = await api.get(`/runs/${selected}`)
      return res.data
    },
    enabled: !!selected && !!token,
  })

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="eyebrow">Run registry</div>
          <h3>Audit, signature, and metrics review</h3>
        </div>
        <span className="muted">Signed with SHA-384</span>
      </div>
      {isLoading && <div>Loading runs...</div>}
      {isError && <div className="error-text">Unable to fetch runs</div>}
      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Created</th>
              <th>Backend</th>
              <th>Signature</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((run) => (
              <tr key={run.run_id} onClick={() => setSelected(run.run_id)} className={selected === run.run_id ? 'active-row' : ''}>
                <td>{run.run_id}</td>
                <td>{run.created_utc || '—'}</td>
                <td>{run.backend || 'local'}</td>
                <td>
                  <span className={run.signature_valid ? 'badge' : 'error-text'}>{run.signature_status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detailsQuery.data && (
        <div className="card nested">
          <div className="card-header">
            <div>
              <div className="eyebrow">Run {detailsQuery.data.summary.run_id}</div>
              <h4>Metadata + metrics</h4>
            </div>
            <span className={detailsQuery.data.summary.signature_valid ? 'badge' : 'error-text'}>
              {detailsQuery.data.summary.signature_status}
            </span>
          </div>
          <div className="grid two">
            <div>
              <h5>Metadata</h5>
              <pre className="code-block">{JSON.stringify(detailsQuery.data.metadata, null, 2)}</pre>
            </div>
            <div>
              <h5>Metrics</h5>
              <pre className="code-block">{JSON.stringify(detailsQuery.data.metrics, null, 2)}</pre>
            </div>
          </div>
          <div>
            <h5>Audit trail</h5>
            <pre className="code-block">{JSON.stringify(detailsQuery.data.audit, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
