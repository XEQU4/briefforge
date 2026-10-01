import { jsonRequest, request } from './client'

export const readAdmin = (path) => request(`/admin/${path}`)
export const setUserActive = (id, isActive) => jsonRequest(`/admin/users/${id}`, 'PATCH', { is_active: isActive })
export const revokeUserSessions = (id) => request(`/admin/users/${id}/revoke-sessions`, { method: 'POST' })
