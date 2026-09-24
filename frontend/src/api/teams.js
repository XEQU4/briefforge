import { jsonRequest, request } from './client'

export const listTeams = () => request('/teams')
export const createTeam = ({ name, interests = null, skills = null, technologies = null }) => jsonRequest('/teams', 'POST', { name, interests, skills, technologies })
