import { create } from 'zustand'

const defaults = {
  backend: 'local',
  resume: true,
  batch_size: 256,
  pollIntervalMs: 8000,
  animations: true,
}

const dataKeys = Object.keys(defaults)

function pickData(source) {
  return dataKeys.reduce((acc, key) => {
    if (key in source) acc[key] = source[key]
    return acc
  }, {})
}

const useUiSettings = create((set, get) => ({
  ...defaults,
  hydrate() {
    const raw = localStorage.getItem('ui_settings')
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        set({ ...defaults, ...pickData(parsed) })
      } catch (err) {
        console.error('Failed to parse UI settings', err)
      }
    }
  },
  update(partial) {
    const next = { ...pickData(get()), ...pickData(partial) }
    localStorage.setItem('ui_settings', JSON.stringify(next))
    set(partial)
  },
}))

export default useUiSettings
