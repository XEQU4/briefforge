import { useLocation, useNavigate } from 'react-router'

export default function WorkspaceSwitcher() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const workspace = pathname === '/business' || pathname.startsWith('/business/') ? '/business'
    : ['/my-teams', '/proposals/mine'].includes(pathname) ? '/my-teams'
      : pathname === '/tasks' || pathname.startsWith('/tasks/') || pathname === '/teams' || pathname.startsWith('/teams/') ? '/tasks' : ''

  return (
    <label className="workspace-switcher">
      <span className="sr-only">Workspace</span>
      <select value={workspace} onChange={(event) => navigate(event.target.value)}>
        <option value="" disabled>Switch workspace...</option>
        <option value="/tasks">Explore</option>
        <option value="/my-teams">Team workspace</option>
        <option value="/business">Business workspace</option>
      </select>
    </label>
  )
}
