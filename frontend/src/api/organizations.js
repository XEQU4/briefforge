import { buildQueryString, jsonRequest, request } from './client'

export const listMyOrganizations = () => request('/organizations/mine')
export const createOrganization = (organization) => jsonRequest('/organizations', 'POST', organization)
export const listOrganizationTasks = (organizationId, filters = {}) => request(`/organizations/${organizationId}/tasks?${buildQueryString(filters)}`)
