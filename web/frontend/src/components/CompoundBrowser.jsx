import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import useAuthStore, { api } from './useAuthStore'

export default function CompoundBrowser() {
  const token = useAuthStore((s) => s.accessToken)
  const [filter, setFilter] = useState('')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['compounds'],
    queryFn: async () => {
      const res = await api.get('/compounds/library')
      return res.data.compounds
    },
    enabled: !!token,
  })

  const compounds = useMemo(() => {
    if (!data) return []
    const lowered = filter.toLowerCase()
    return data.filter((c) => c.name.toLowerCase().includes(lowered) || c.receptor_type.toLowerCase().includes(lowered))
  }, [data, filter])

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="eyebrow">Compound Library</div>
          <h3>Receptor & pharmacology coverage</h3>
        </div>
        <input
          className="input compact"
          placeholder="Filter by name or receptor"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>
      {isLoading && <div>Loading compounds...</div>}
      {isError && <div className="error-text">Unable to load library</div>}
      {!isLoading && !isError && (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Receptor</th>
                <th>Ki (nM)</th>
                <th>Bias</th>
                <th>t½ (h)</th>
                <th>Activities</th>
                <th>Safety</th>
              </tr>
            </thead>
            <tbody>
              {compounds.map((c) => (
                <tr key={c.name}>
                  <td>{c.name}</td>
                  <td>{c.receptor_type}</td>
                  <td>{c.ki_orthosteric}</td>
                  <td>{c.bias === Infinity ? '∞' : c.bias.toFixed(2)}</td>
                  <td>{c.t_half}</td>
                  <td>{c.activities?.join(', ') || '—'}</td>
                  <td>{c.safety?.toFixed?.(1) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
