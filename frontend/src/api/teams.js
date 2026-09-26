import { jsonRequest, request } from './client'

function queryString(values) {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  return query.toString()
}

export const listTeams = (page = 1, pageSize = 20, q = '') => request(`/teams?${queryString({ page, page_size: pageSize, q })}`)
export const listMyTeams = (page = 1, pageSize = 100) => request(`/teams/mine?${queryString({ page, page_size: pageSize })}`)
export const getTeam = (id) => request(`/teams/${id}`)
export const createTeam = ({ name, interests = null, skills = null, technologies = null }) => jsonRequest('/teams', 'POST', { name, interests, skills, technologies })
