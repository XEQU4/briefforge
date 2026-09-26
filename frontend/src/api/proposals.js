import { buildQueryString, jsonRequest, request } from './client'

export const createProposal = (taskId, proposal) => jsonRequest(`/tasks/${taskId}/proposals`, 'POST', proposal)
export const listProposals = (taskId, filters = {}) => request(`/tasks/${taskId}/proposals?${buildQueryString(filters)}`)
export const listMyProposals = (filters = {}) => request(`/proposals/mine?${buildQueryString(filters)}`)
export const updateProposal = (id, status) => jsonRequest(`/proposals/${id}`, 'PATCH', { status })
