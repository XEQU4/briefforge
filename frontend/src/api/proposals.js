import { jsonRequest, request } from './client'

export const createProposal = (taskId, proposal) => jsonRequest(`/tasks/${taskId}/proposals`, 'POST', proposal)
export const listProposals = (taskId, page = 1, pageSize = 20) => request(`/tasks/${taskId}/proposals?page=${page}&page_size=${pageSize}`)
export const updateProposal = (id, status) => jsonRequest(`/proposals/${id}`, 'PATCH', { status })
