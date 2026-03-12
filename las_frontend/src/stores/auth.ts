import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  role: string
  is_active: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const refreshTokenValue = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<User | null>(null)
  const refreshPromise = ref<Promise<string | null> | null>(null)
  const userPromise = ref<Promise<void> | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  const setToken = (value: string | null) => {
    token.value = value
    if (value) {
      localStorage.setItem('token', value)
      return
    }
    localStorage.removeItem('token')
  }

  const setRefreshToken = (value: string | null) => {
    refreshTokenValue.value = value
    if (value) {
      localStorage.setItem('refresh_token', value)
      return
    }
    localStorage.removeItem('refresh_token')
  }

  const clearAuth = () => {
    setToken(null)
    setRefreshToken(null)
    user.value = null
    userPromise.value = null
  }

  const getTokenExpiry = (jwt: string | null): number | null => {
    if (!jwt) return null

    try {
      const [, payload] = jwt.split('.')
      if (!payload) return null
      const parsed = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
      return typeof parsed.exp === 'number' ? parsed.exp * 1000 : null
    } catch {
      return null
    }
  }

  const isTokenExpiringSoon = () => {
    const expiry = getTokenExpiry(token.value)
    if (!expiry) return false
    return expiry - Date.now() <= 5 * 60 * 1000
  }

  const login = async (username: string, password: string) => {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    
    setToken(response.data.access_token)
    setRefreshToken(response.data.refresh_token)
    
    await fetchUser()
  }

  const register = async (email: string, username: string, password: string, fullName?: string) => {
    const response = await api.post('/auth/register', {
      email,
      username,
      password,
      full_name: fullName,
    })
    
    return response.data
  }

  const fetchUser = async () => {
    if (!token.value && !refreshTokenValue.value) return

    if (userPromise.value) {
      return userPromise.value
    }

    userPromise.value = (async () => {
      try {
        if (!token.value && refreshTokenValue.value) {
          const refreshed = await refreshToken()
          if (!refreshed) return
        }
        const response = await api.get('/auth/me')
        user.value = response.data
      } catch {
        const refreshed = await refreshToken()
        if (!refreshed) {
          clearAuth()
          return
        }
        const response = await api.get('/auth/me')
        user.value = response.data
      } finally {
        userPromise.value = null
      }
    })()

    return userPromise.value
  }

  const ensureUserLoaded = async () => {
    if (user.value || (!token.value && !refreshTokenValue.value)) return
    await fetchUser()
  }

  const refreshToken = async () => {
    if (!refreshTokenValue.value) return null
    if (refreshPromise.value) return refreshPromise.value

    refreshPromise.value = api.post(
      '/auth/refresh',
      {
        refresh_token: refreshTokenValue.value,
      },
      {
        _skipAuthRefresh: true,
      } as any
    )
      .then((response) => {
        const nextToken = response.data.access_token as string
        const nextRefreshToken = response.data.refresh_token as string
        setToken(nextToken)
        setRefreshToken(nextRefreshToken)
        return nextToken
      })
      .catch(() => {
        clearAuth()
        return null
      })
      .finally(() => {
        refreshPromise.value = null
      })

    return refreshPromise.value
  }

  const ensureFreshToken = async () => {
    if (!token.value) return null
    if (!isTokenExpiringSoon()) return token.value
    return refreshToken()
  }

  const logout = async () => {
    const currentToken = token.value
    const currentRefreshToken = refreshTokenValue.value
    clearAuth()

    if (!currentToken && !currentRefreshToken) return

    try {
      await api.post(
        '/auth/logout',
        {
          access_token: currentToken,
          refresh_token: currentRefreshToken,
        },
        {
          _skipAuthRefresh: true,
        } as any
      )
    } catch {
      // Ignore logout failures because local session is already cleared.
    }
  }

  if (token.value) {
    fetchUser()
  }

  return {
    token,
    refreshTokenValue,
    user,
    isAuthenticated,
    login,
    register,
    logout,
    fetchUser,
    ensureUserLoaded,
    refreshToken,
    ensureFreshToken,
    clearAuth,
  }
})
