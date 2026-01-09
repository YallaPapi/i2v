import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { api } from '@/api/client'

// Types
export interface User {
  id: number
  email: string
  role: string
  tier: string
  credits_balance: number
}

interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

// Token storage keys
const ACCESS_TOKEN_KEY = 'i2v_access_token'
const REFRESH_TOKEN_KEY = 'i2v_refresh_token'

// Get stored tokens
function getStoredTokens(): { accessToken: string | null; refreshToken: string | null } {
  return {
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY),
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  }
}

// Store tokens
function storeTokens(tokens: AuthTokens) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

// Clear tokens
function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

// Setup axios interceptor for auth
function setupAxiosInterceptor() {
  // Request interceptor - add auth header
  api.interceptors.request.use(
    (config) => {
      const { accessToken } = getStoredTokens()
      if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  // Response interceptor - handle 401 and refresh token
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config

      // If 401 and we haven't retried yet
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true

        const { refreshToken } = getStoredTokens()
        if (refreshToken) {
          try {
            // Try to refresh the token
            const { data } = await api.post<AuthTokens>('/auth/refresh', {
              refresh_token: refreshToken,
            })
            storeTokens(data)

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`
            return api(originalRequest)
          } catch {
            // Refresh failed - clear tokens and redirect to login
            clearTokens()
            window.location.href = '/login'
          }
        }
      }

      return Promise.reject(error)
    }
  )
}

// Initialize interceptor once
let interceptorSetup = false

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Setup axios interceptor once
  useEffect(() => {
    if (!interceptorSetup) {
      setupAxiosInterceptor()
      interceptorSetup = true
    }
  }, [])

  // Fetch current user
  const refreshUser = useCallback(async () => {
    const { accessToken } = getStoredTokens()
    if (!accessToken) {
      setUser(null)
      setIsLoading(false)
      return
    }

    try {
      const { data } = await api.get<User>('/auth/me')
      setUser(data)
    } catch {
      // Token invalid/expired - clear it
      clearTokens()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Check auth on mount
  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  // Login
  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<AuthTokens>('/auth/login', { email, password })
    storeTokens(data)
    await refreshUser()
  }, [refreshUser])

  // Signup
  const signup = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<AuthTokens>('/auth/signup', { email, password })
    storeTokens(data)
    await refreshUser()
  }, [refreshUser])

  // Logout
  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    // Optionally call backend logout endpoint
    api.post('/auth/logout').catch(() => {})
  }, [])

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    signup,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
