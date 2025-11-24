import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import useUiSettings from './useUiSettings'
import { api } from './useAuthStore'

export default function Settings() {
  const ui = useUiSettings()
  const [form, setForm] = useState(ui)

  useEffect(() => {
    ui.hydrate()
    setForm(ui)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    document.body.classList.toggle('reduced-motion', !ui.animations)
  }, [ui.animations])

  const mutation = useMutation({
    mutationFn: async (payload) => {
      const res = await api.post('/settings/presets', payload)
      return res.data
    },
    onSuccess: (data) => {
      ui.update(form)
      setStatus({ ok: true, message: data.signature_status, run: data.run_id })
    },
  })

  const [status, setStatus] = useState(null)

  const handleChange = (key, value) => {
    const next = { ...form, [key]: value }
    setForm(next)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setStatus(null)
    await mutation.mutateAsync(form)
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="eyebrow">Settings</div>
          <h3>TEMPEST Class C theming + distributed controls</h3>
        </div>
        <span className="muted">Animations {form.animations ? 'on' : 'off'}</span>
      </div>
      <form className="grid two" onSubmit={handleSubmit}>
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
          />
        </label>
        <label className="stack">
          <span>Polling interval (ms)</span>
          <input
            className="input"
            type="number"
            value={form.pollIntervalMs}
            onChange={(e) => handleChange('pollIntervalMs', Number(e.target.value))}
          />
        </label>
        <label className="stack">
          <span>Animations</span>
          <input type="checkbox" checked={form.animations} onChange={(e) => handleChange('animations', e.target.checked)} />
        </label>
        <div className="grid full-span">
          <button className="button" type="submit" disabled={mutation.isLoading}>
            {mutation.isLoading ? 'Saving...' : 'Save'}
          </button>
          {status && (
            <div className="status-line">
              <span className={status.ok ? 'badge' : 'error-text'}>{status.message}</span>
              <span className="muted">Run ID: {status.run}</span>
            </div>
          )}
        </div>
      </form>
    </div>
  )
}
