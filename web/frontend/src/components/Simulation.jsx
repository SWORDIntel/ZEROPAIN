import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import useAuthStore, { api } from './useAuthStore'
import useUiSettings from './useUiSettings'

const defaults = {
  patient_count: 5000,
  age_mean: 45,
  age_std: 12,
  sex_ratio_female: 0.52,
  medication_prevalence: 0.2,
  baseline_tolerance: 0.1,
  receptor_target: 'MOR',
}

export default function Simulation() {
  const token = useAuthStore((s) => s.accessToken)
  const ui = useUiSettings()
  const [form, setForm] = useState({ ...defaults, backend: ui.backend, resume: ui.resume, batch_size: ui.batch_size })
  useQuery({
    queryKey: ['defaults'],
    queryFn: async () => {
      const res = await api.get('/settings/defaults')
      setForm((prev) => ({ ...prev, ...res.data }))
      return res.data
    },
    enabled: !!token,
  })
  const mutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/simulate', payload)
      return res.data
    },
  })

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    await mutation.mutateAsync(form)
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="eyebrow">Patient simulation</div>
          <h3>Population + medication controls for CPU simulation</h3>
        </div>
        <span className="muted">Backend: {form.backend}</span>
      </div>
      <form className="grid two" onSubmit={handleSubmit}>
        <label className="stack">
          <span>Patients</span>
          <input
            className="input"
            type="number"
            value={form.patient_count}
            onChange={(e) => handleChange('patient_count', Number(e.target.value))}
            min={1}
            max={500000}
          />
        </label>
        <label className="stack">
          <span>Backend</span>
          <select className="input" value={form.backend} onChange={(e) => handleChange('backend', e.target.value)}>
            <option value="local">Local</option>
            <option value="ray">Ray</option>
            <option value="dask">Dask</option>
          </select>
        </label>
        <label className="stack">
          <span>Resume checkpoints</span>
          <input type="checkbox" checked={form.resume} onChange={(e) => handleChange('resume', e.target.checked)} />
        </label>
        <label className="stack">
          <span>Batch size</span>
          <input
            className="input"
            type="number"
            value={form.batch_size}
            onChange={(e) => handleChange('batch_size', Number(e.target.value))}
            min={1}
            max={10000}
          />
        </label>
        <label className="stack">
          <span>Mean age</span>
          <input className="input" type="number" value={form.age_mean} onChange={(e) => handleChange('age_mean', Number(e.target.value))} />
        </label>
        <label className="stack">
          <span>Age std dev</span>
          <input className="input" type="number" value={form.age_std} onChange={(e) => handleChange('age_std', Number(e.target.value))} />
        </label>
        <label className="stack">
          <span>Female ratio</span>
          <input
            className="input"
            type="number"
            step="0.01"
            value={form.sex_ratio_female}
            onChange={(e) => handleChange('sex_ratio_female', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Medication prevalence</span>
          <input
            className="input"
            type="number"
            step="0.01"
            value={form.medication_prevalence}
            onChange={(e) => handleChange('medication_prevalence', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Baseline tolerance</span>
          <input
            className="input"
            type="number"
            step="0.01"
            value={form.baseline_tolerance}
            onChange={(e) => handleChange('baseline_tolerance', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Receptor target</span>
          <select className="input" value={form.receptor_target} onChange={(e) => handleChange('receptor_target', e.target.value)}>
            <option value="MOR">MOR</option>
            <option value="DOR">DOR</option>
            <option value="KOR">KOR</option>
          </select>
        </label>
        <div className="grid full-span">
          <button className="button" type="submit" disabled={mutation.isLoading}>
            {mutation.isLoading ? 'Running...' : 'Run simulation'}
          </button>
          {mutation.data && (
            <div className="status-line">
              <span className={mutation.data.signature_valid ? 'badge' : 'error-text'}>{mutation.data.signature_status}</span>
              <span className="muted">Run ID: {mutation.data.run_id}</span>
              {mutation.data.job_record_id && <span className="muted">Job: {mutation.data.job_record_id}</span>}
            </div>
          )}
        </div>
      </form>
      {mutation.data && (
        <div className="stack result-stack">
          <div className="grid three nested">
            <div className="stat">
              <div className="eyebrow">Analgesia</div>
              <div className="stat-value">{mutation.data.metrics.analgesia_score}</div>
            </div>
            <div className="stat">
              <div className="eyebrow">Side-effect risk</div>
              <div className="stat-value">{mutation.data.metrics.side_effect_risk}</div>
            </div>
            <div className="stat">
              <div className="eyebrow">Receptor occupancy</div>
              <div className="stat-value">{mutation.data.metrics.receptor_occupancy}</div>
            </div>
            <div className="stat">
              <div className="eyebrow">Medication exposure</div>
              <div className="stat-value">{mutation.data.metrics.medication_exposure}</div>
            </div>
            <div className="stat">
              <div className="eyebrow">Throughput/batch</div>
              <div className="stat-value">{mutation.data.metrics.throughput_per_batch}</div>
            </div>
          </div>
          {mutation.data.provenance && (
            <div className="provenance-panel">
              <div className="status-line">
                <span className={mutation.data.provenance.decision_grade === 'true' ? 'badge' : 'badge warning'}>
                  {mutation.data.provenance.decision_grade === 'true' ? 'decision grade' : 'research only'}
                </span>
                <span className="muted">Model: {mutation.data.provenance.model}</span>
                <span className="muted">Mode: {mutation.data.provenance.mode}</span>
                <span className="muted">Training: {mutation.data.provenance.training_profile}</span>
              </div>
              <div className="provenance-grid">
                <span>Engine: {mutation.data.provenance.engine}</span>
                <span>Input hash: {mutation.data.provenance.input_hash.slice(0, 18)}</span>
                <span>Model hash: {mutation.data.provenance.model_hash.slice(0, 18)}</span>
                <span>{mutation.data.provenance.warning}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
