import { jsonRequest, request } from './client'

export const getCurrentUser = () => request('/auth/me')
export const registerUser = (payload) => jsonRequest('/auth/register', 'POST', payload)
export const loginUser = (payload) => jsonRequest('/auth/login', 'POST', payload)
export const logoutUser = () => request('/auth/logout', { method: 'POST' })
