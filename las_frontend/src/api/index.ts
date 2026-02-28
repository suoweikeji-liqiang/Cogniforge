import axios from 'axios'
import { Capacitor } from '@capacitor/core'
import { useAuthStore } from '@/stores/auth'

const getBaseURL = () => {
  if (Capacitor.isNativePlatform()) {
    // On native mobile, use the configured server URL
    return localStorage.getItem('api_server_url') || 'http://10.0.2.2:8002/api'
  }
  return '/api'
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
