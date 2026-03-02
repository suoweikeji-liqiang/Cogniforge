import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const getBaseURL = () => {
  // Native mobile: check localStorage override (set by Capacitor build)
  const nativeUrl = localStorage.getItem('api_server_url')
  if (nativeUrl) return nativeUrl
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
