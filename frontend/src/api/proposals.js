import { jsonRequest, request } from './client'

export const createProposal = (taskId, proposal) => jsonRequest(`/tasks/${taskId}/proposals`, 'POST', proposal)
export const listProposals = (taskId) => request(`/tasks/${taskId}/proposals`)
export const updateProposal = (id, status) => jsonRequest(`/proposals/${id}`, 'PATCH', { status })
