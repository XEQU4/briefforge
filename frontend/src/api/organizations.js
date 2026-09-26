import { jsonRequest, request } from './client'

export const listMyOrganizations = () => request('/organizations/mine')
export const createOrganization = (organization) => jsonRequest('/organizations', 'POST', organization)
