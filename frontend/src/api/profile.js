import { jsonRequest, request } from './client'

export const updateProfile = (displayName) => jsonRequest('/profile', 'PATCH', { display_name: displayName })
export const deleteAvatar = () => request('/profile/avatar', { method: 'DELETE' })
export function uploadAvatar(file) {
  const body = new FormData()
  body.append('file', file)
  return request('/profile/avatar', { method: 'POST', body })
}
