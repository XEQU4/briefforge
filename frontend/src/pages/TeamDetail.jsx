import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getTeam } from '../api/teams'
import { EmptyState, LoadingState } from '../components/StatePanel'

export default function TeamDetail() {
  const { teamId } = useParams()
  const [team, setTeam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    getTeam(teamId).then((value) => { if (active) setTeam(value) }).catch((reason) => { if (active) setError(reason) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [teamId])

  if (loading) return <section className="page"><LoadingState title="Loading team" /></section>
  if (error?.status === 404) return <section className="page"><EmptyState title="Team not found" description="This team may have been removed or the link may be incorrect." action={<Link to="/teams">Browse teams</Link>} /></section>
  if (error) return <section className="page"><div className="feedback feedback-error" role="alert">Unable to load this team: {error.message}</div></section>
  return <section className="page team-detail-page"><header className="page-header"><span className="eyebrow">Public team profile</span><h1>{team.name}</h1><p>{team.interests || 'This team has not added interests yet.'}</p></header><div className="detail-grid"><article><h3>Skills</h3><p>{team.skills || 'Not provided.'}</p></article><article><h3>Technologies</h3><p>{team.technologies || 'Not provided.'}</p></article></div><Link className="small-primary-link" to="/tasks">Explore challenges</Link></section>
}
