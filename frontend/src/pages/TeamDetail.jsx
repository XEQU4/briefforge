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
    setError(null)
    getTeam(teamId).then((value) => { if (active) setTeam(value) }).catch((reason) => { if (active) setError(reason) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [teamId])

  if (loading) return <section className="page product-page"><LoadingState title="Loading team" /></section>
  if (error?.status === 404) return <section className="page product-page"><EmptyState eyebrow="" title="Team not found" description="This team may have been removed or the link may be incorrect." action={<Link to="/teams">Back to teams</Link>} /></section>
  if (error) return <section className="page product-page"><div className="feedback feedback-error" role="alert">Unable to load this team. Please try again.</div><Link to="/teams">Back to teams</Link></section>
  return (
    <section className="page product-page team-detail-page">
      <Link className="back-link" to="/teams">← Back to teams</Link>
      <header className="product-page-header"><div><span className="eyebrow">Public team profile</span><h1>{team.name}</h1>{team.interests && <p>{team.interests}</p>}</div></header>
      <dl className="team-detail-info">{[['skills', 'Skills'], ['technologies', 'Technologies']].map(([key, label]) => <div className={team[key] ? '' : 'is-empty'} key={key}><dt>{label}</dt><dd>{team[key] || 'Not provided'}</dd></div>)}</dl>
      <Link className="small-primary-link" to="/tasks">Explore challenges</Link>
    </section>
  )
}
