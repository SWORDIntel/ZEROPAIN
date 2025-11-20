import { useMemo } from 'react'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Tooltip, ResponsiveContainer } from 'recharts'

const mockData = [
  { metric: 'hERG', score: 0.12 },
  { metric: 'Hepatotoxicity', score: 0.22 },
  { metric: 'CYP2D6', score: 0.18 },
  { metric: 'Bioavailability', score: 0.72 },
  { metric: 'Clearance', score: 0.54 },
]

export default function ADMETDashboard() {
  const normalized = useMemo(() => mockData.map((d) => ({ metric: d.metric, score: d.score * 100 })), [])

  return (
    <div className="card" style={{ height: 360 }}>
      <h3>ADMET Risk Radar</h3>
      <ResponsiveContainer width="100%" height="90%">
        <RadarChart data={normalized}>
          <PolarGrid stroke="rgba(0,217,255,0.3)" />
          <PolarAngleAxis dataKey="metric" stroke="#00d9ff" />
          <PolarRadiusAxis angle={45} domain={[0, 100]} stroke="#00d9ff" />
          <Radar
            name="Risk"
            dataKey="score"
            stroke="#00d9ff"
            fill="#00d9ff"
            fillOpacity={0.2}
          />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
