import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import useAuthStore, { api } from './useAuthStore'

const emptyCompound = {
  name: '',
  ki_orthosteric: 1.0,
  ki_allosteric1: 1e9,
  ki_allosteric2: 1e9,
  g_protein_bias: 1.0,
  beta_arrestin_bias: 1.0,
  t_half: 3.0,
  bioavailability: 0.3,
  intrinsic_activity: 1.0,
  tolerance_rate: 0.5,
  prevents_withdrawal: false,
  reverses_tolerance: false,
  receptor_type: 'MOR',
  pharmacological_activities: '',
  mechanism_notes: '',
}

export default function CompoundBuilder() {
  const token = useAuthStore((s) => s.accessToken)
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['compounds'],
    queryFn: async () => {
      const res = await api.get('/compounds/library')
      return res.data.compounds
    },
    enabled: !!token,
  })
  const [form, setForm] = useState(emptyCompound)
  const [status, setStatus] = useState(null)

  useEffect(() => {
    if (!data?.length) return
    const first = data[0]
    setForm((prev) => ({ ...prev, name: prev.name || first.name }))
  }, [data])

  const mutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/compounds/custom', payload)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['compounds'] })
    },
  })

  const handleSelect = (name) => {
    const picked = data?.find((c) => c.name === name)
    if (!picked) return
    setForm((prev) => ({
      ...prev,
      name: picked.name,
      ki_orthosteric: picked.ki_orthosteric,
      ki_allosteric1: picked.ki_allosteric1 ?? 1e9,
      ki_allosteric2: picked.ki_allosteric2 ?? 1e9,
      g_protein_bias: picked.bias === Infinity ? 1.0 : picked.bias,
      beta_arrestin_bias: picked.bias === Infinity ? 0.1 : 1 / Math.max(picked.bias, 0.01),
      t_half: picked.t_half,
      bioavailability: picked.bioavailability,
      pharmacological_activities: picked.activities?.join(', ') || '',
    }))
  }

  const activities = useMemo(
    () =>
      (form.pharmacological_activities || '')
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [form.pharmacological_activities]
  )

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus(null)
    const payload = { ...form, pharmacological_activities: activities }
    const res = await mutation.mutateAsync(payload)
    setStatus(res)
  }

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="eyebrow">Guided compound creator</div>
          <h3>Template, tweak, and audit custom ligands</h3>
        </div>
        <select className="input compact" value={form.name} onChange={(e) => handleSelect(e.target.value)}>
          {data?.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.receptor_type})
            </option>
          ))}
        </select>
      </div>
      <form className="grid two" onSubmit={handleSubmit}>
        <label className="stack">
          <span>Custom name</span>
          <input className="input" value={form.name} onChange={(e) => handleChange('name', e.target.value)} required />
        </label>
        <label className="stack">
          <span>Receptor type</span>
          <select className="input" value={form.receptor_type} onChange={(e) => handleChange('receptor_type', e.target.value)}>
            <option value="MOR">MOR</option>
            <option value="DOR">DOR</option>
            <option value="KOR">KOR</option>
          </select>
        </label>
        <label className="stack">
          <span>Ki (nM)</span>
          <input
            className="input"
            type="number"
            step="0.01"
            value={form.ki_orthosteric}
            onChange={(e) => handleChange('ki_orthosteric', Number(e.target.value))}
            required
          />
        </label>
        <label className="stack">
          <span>G-protein bias</span>
          <input
            className="input"
            type="number"
            step="0.1"
            value={form.g_protein_bias}
            onChange={(e) => handleChange('g_protein_bias', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>β-arrestin bias</span>
          <input
            className="input"
            type="number"
            step="0.05"
            value={form.beta_arrestin_bias}
            onChange={(e) => handleChange('beta_arrestin_bias', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Half-life (h)</span>
          <input
            className="input"
            type="number"
            step="0.1"
            value={form.t_half}
            onChange={(e) => handleChange('t_half', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Bioavailability</span>
          <input
            className="input"
            type="number"
            step="0.01"
            value={form.bioavailability}
            onChange={(e) => handleChange('bioavailability', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Intrinsic activity</span>
          <input
            className="input"
            type="number"
            step="0.05"
            value={form.intrinsic_activity}
            onChange={(e) => handleChange('intrinsic_activity', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Pharmacological activities</span>
          <input
            className="input"
            value={form.pharmacological_activities}
            placeholder="Comma-separated (e.g., MOR agonist, NRI)"
            onChange={(e) => handleChange('pharmacological_activities', e.target.value)}
          />
        </label>
        <label className="stack">
          <span>Mechanism notes</span>
          <input className="input" value={form.mechanism_notes} onChange={(e) => handleChange('mechanism_notes', e.target.value)} />
        </label>
        <label className="stack">
          <span>Withdrawal prevention</span>
          <input
            type="checkbox"
            checked={form.prevents_withdrawal}
            onChange={(e) => handleChange('prevents_withdrawal', e.target.checked)}
          />
        </label>
        <label className="stack">
          <span>Tolerance reversal</span>
          <input
            type="checkbox"
            checked={form.reverses_tolerance}
            onChange={(e) => handleChange('reverses_tolerance', e.target.checked)}
          />
        </label>
        <div className="grid full-span">
          <button className="button" type="submit" disabled={mutation.isLoading}>
            {mutation.isLoading ? 'Saving...' : 'Save + Audit'}
          </button>
          {status && (
            <div className="status-line">
              <span className={status.signature_valid ? 'badge' : 'error-text'}>{status.signature_status}</span>
              <span className="muted">Run ID: {status.run_id}</span>
            </div>
          )}
        </div>
      </form>
    </div>
  )
}
