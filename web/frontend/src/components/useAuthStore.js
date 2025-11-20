import { create } from 'zustand'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

const useAuthStore = create((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  loading: false,
  error: null,
  setAuthHeader(token) {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`
    } else {
      delete api.defaults.headers.common.Authorization
    }
  },
  async login(username, password) {
    set({ loading: true, error: null })
    try {
      const res = await api.post('/auth/login', { username, password })
      const { access_token, refresh_token, user } = res.data
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      api.defaults.headers.common.Authorization = `Bearer ${access_token}`
      set({ accessToken: access_token, refreshToken: refresh_token, user, loading: false })
      return true
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Login failed', loading: false })
      return false
    }
  },
  async refresh() {
    const refreshToken = get().refreshToken || localStorage.getItem('refresh_token')
    if (!refreshToken) return false
    try {
      const res = await api.post('/auth/refresh', { refresh_token: refreshToken })
      const { access_token, user } = res.data
      localStorage.setItem('access_token', access_token)
      api.defaults.headers.common.Authorization = `Bearer ${access_token}`
      set({ accessToken: access_token, user })
      return true
    } catch (err) {
      set({ error: 'Session expired', accessToken: null, refreshToken: null, user: null })
      return false
    }
  },
  async logout() {
    const refreshToken = get().refreshToken || localStorage.getItem('refresh_token')
    try {
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken })
      }
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      api.defaults.headers.common.Authorization = undefined
      set({ accessToken: null, refreshToken: null, user: null })
    }
  },
  async hydrateUser() {
    const access = localStorage.getItem('access_token')
    const refresh = localStorage.getItem('refresh_token')
    if (access) {
      api.defaults.headers.common.Authorization = `Bearer ${access}`
      set({ accessToken: access, refreshToken: refresh })
      try {
        const me = await api.get('/auth/me')
        set({ user: me.data })
      } catch (err) {
        if (await get().refresh()) {
          const me = await api.get('/auth/me')
          set({ user: me.data })
        }
      }
    }
  },
  loadFromStorage() {
    const access = localStorage.getItem('access_token')
    const refresh = localStorage.getItem('refresh_token')
    if (access) {
      api.defaults.headers.common.Authorization = `Bearer ${access}`
      set({ accessToken: access })
    }
    if (refresh) set({ refreshToken: refresh })
  },
}))

export { api }
export default useAuthStore
