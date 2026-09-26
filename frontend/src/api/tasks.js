import { buildQueryString, jsonRequest, request } from './client'

export const createTask = (draft_text, topic = null, organization_id) => jsonRequest('/tasks', 'POST', { draft_text, topic, organization_id })
export const getTask = (id) => request(`/tasks/${id}`)
export const getTaskQuestions = (id) => request(`/tasks/${id}/questions`)
export const answerTask = (id, answers) => jsonRequest(`/tasks/${id}/answers`, 'PATCH', { answers })
export const updateTask = (id, fields) => jsonRequest(`/tasks/${id}`, 'PATCH', fields)
export const confirmTask = (id) => jsonRequest(`/tasks/${id}/confirm`, 'POST', {})
export const getTaskRating = (id) => request(`/tasks/${id}/rating`)
export const publishTask = (id) => jsonRequest(`/tasks/${id}/publish`, 'POST', {})
export const unpublishTask = (id) => jsonRequest(`/tasks/${id}/unpublish`, 'POST', {})
export const archiveTask = (id) => jsonRequest(`/tasks/${id}/archive`, 'POST', {})
export const listTasks = (filters = {}) => request(`/tasks?${buildQueryString(filters)}`)
