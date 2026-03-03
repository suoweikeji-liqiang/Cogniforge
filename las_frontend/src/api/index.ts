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
  return config
})

api.interceptors.request.use(async (config) => {
  const authStore = useAuthStore()
  if ((config as any)._skipAuthRefresh) {
    return config
  }

  const currentToken = await authStore.ensureFreshToken()
  if (currentToken) {
    config.headers.Authorization = `Bearer ${currentToken}`
  } else if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const authStore = useAuthStore()
    const originalRequest = error.config || {}
    const requestUrl = originalRequest.url || ''

    if (
      error.response?.status === 401 &&
      authStore.token &&
      !originalRequest._retry &&
      !originalRequest._skipAuthRefresh &&
      !requestUrl.includes('/auth/login') &&
      !requestUrl.includes('/auth/refresh')
    ) {
      originalRequest._retry = true
      const nextToken = await authStore.refreshToken()
      if (nextToken) {
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${nextToken}`
        return api(originalRequest)
      }
    }

    if (error.response?.status === 401) {
      authStore.clearAuth()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
