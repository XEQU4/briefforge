import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { getCurrentUser, loginUser, logoutUser, registerUser } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const generation = useRef(0)

  const refreshUser = useCallback(async () => {
    const current = ++generation.current
    setStatus('loading')
    setError(null)
    try {
      const value = await getCurrentUser()
      if (current === generation.current) {
        setUser(value)
        setStatus('ready')
      }
      return value
    } catch (reason) {
      if (current === generation.current) {
        if (reason.status === 401) {
          setUser(null)
          setError(null)
          setStatus('ready')
        } else {
          setError(reason)
          setStatus('error')
        }
      }
      throw reason
    }
  }, [])

  useEffect(() => { refreshUser().catch(() => {}) }, [refreshUser])

  const authenticate = useCallback(async (action, payload) => {
    const current = ++generation.current
    setError(null)
    const value = await action(payload)
    if (current === generation.current) {
      setUser(value)
      setStatus('ready')
    }
    return value
  }, [])

  const register = useCallback((payload) => authenticate(registerUser, payload), [authenticate])
  const login = useCallback((payload) => authenticate(loginUser, payload), [authenticate])

  const logout = useCallback(async () => {
    ++generation.current
    let failure = null
    try { await logoutUser() } catch (reason) { failure = reason }
    setUser(null)
    setStatus('ready')
    setError(null)
    return { remoteLogoutFailed: Boolean(failure) }
  }, [])

  const clearError = useCallback(() => setError(null), [])
  const value = useMemo(() => ({
    user,
    loading: status === 'loading',
    authenticated: Boolean(user),
    error,
    clearError,
    refreshUser,
    register,
    login,
    logout,
  }), [user, status, error, clearError, refreshUser, register, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
