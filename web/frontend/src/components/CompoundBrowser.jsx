const compounds = [
  { name: 'Morphine', ki: '1.2 nM', type: 'Mu agonist' },
  { name: 'Oxycodone', ki: '2.8 nM', type: 'Mu agonist' },
  { name: 'Fentanyl', ki: '0.7 nM', type: 'Potent mu agonist' },
  { name: 'Buprenorphine', ki: '0.2 nM', type: 'Partial agonist' },
  { name: 'PZM21', ki: '18 nM', type: 'Biased agonist' },
]

export default function CompoundBrowser() {
  return (
    <div className="card">
      <h3>Compound Library</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Ki</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {compounds.map((c) => (
            <tr key={c.name}>
              <td>{c.name}</td>
              <td>{c.ki}</td>
              <td>{c.type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
