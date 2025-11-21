export default function Loading({ label = 'Loading' }) {
  return (
    <div className="card">
      <div className="badge">{label}</div>
    </div>
  )
}
