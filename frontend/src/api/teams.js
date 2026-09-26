import { buildQueryString, jsonRequest, request } from './client'

export const listTeams = (page = 1, pageSize = 20, q = '') => request(`/teams?${buildQueryString({ page, page_size: pageSize, q })}`)
export const listMyTeams = (page = 1, pageSize = 100) => request(`/teams/mine?${buildQueryString({ page, page_size: pageSize })}`)
export const getTeam = (id) => request(`/teams/${id}`)
export const createTeam = ({ name, interests = null, skills = null, technologies = null }) => jsonRequest('/teams', 'POST', { name, interests, skills, technologies })
