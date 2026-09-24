import { jsonRequest, request } from './client'

export const createTask = (draft_text, topic = null) => jsonRequest('/tasks', 'POST', { draft_text, topic })
export const answerTask = (id, answers) => jsonRequest(`/tasks/${id}/answers`, 'PATCH', { answers })
export const updateTask = (id, fields) => jsonRequest(`/tasks/${id}`, 'PATCH', fields)
export const confirmTask = (id) => jsonRequest(`/tasks/${id}/confirm`, 'POST', {})
export const getTaskRating = (id) => request(`/tasks/${id}/rating`)
export function listTasks({ topic, readiness_level, sort } = {}) {
  const query = new URLSearchParams()
  if (topic) query.set('topic', topic)
  if (readiness_level) query.set('readiness_level', readiness_level)
  if (sort) query.set('sort', sort)
  return request(`/tasks${query.toString() ? `?${query}` : ''}`)
}
