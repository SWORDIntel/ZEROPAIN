import { useQuery } from '@tanstack/react-query'
import useAuthStore, { api } from './useAuthStore'

export default function Dashboard() {
  const { accessToken } = useAuthStore()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await api.get('/health')
      return res.data
    },
    enabled: !!accessToken,
  })

  return (
    <div className="card">
      <h3>System Status</h3>
      {isLoading && <div>Loading...</div>}
      {isError && <div style={{ color: '#ffb3b3' }}>Health check failed</div>}
      {data && (
        <div className="status-grid">
          <div className="card">
            <strong>API</strong>
            <div>{data.status}</div>
          </div>
          <div className="card">
            <strong>Intel Device</strong>
            <div>{data.intel_device}</div>
          </div>
          <div className="card">
            <strong>Redis</strong>
            <div>{data.redis || 'connected'}</div>
          </div>
        </div>
      )}
    </div>
  )
}
