import { useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import OrganizationPicker from '../components/OrganizationPicker'

export default function BusinessWorkspace() {
  const { user } = useAuth()
  const [organizationId, setOrganizationId] = useState(null)
  return (
    <section className="page workspace-page">
      <header className="page-header split-header">
        <div><span className="eyebrow">Business workspace</span><h1>Shape a challenge around your organization.</h1><p>Choose an organization to create a task. Your membership is checked by the server for every business action.</p></div>
        <div className="glass-panel account-summary"><span>Signed in as</span><strong>{user.display_name || user.email}</strong></div>
      </header>
      <div className="workspace-grid">
        <section className="feature-panel">
          <div className="panel-heading"><span className="eyebrow">Organizations</span><h2>Your workspaces</h2></div>
          <OrganizationPicker onSelectionChange={setOrganizationId} />
          {organizationId && <div className="form-footer"><span className="form-hint">Selected organization is sent with the task request.</span><Link className="small-primary-link" to="/business/tasks/new" state={{ organizationId }}>Create a task</Link></div>}
        </section>
        <aside className="side-note glass-panel"><span className="eyebrow">Your workflow</span><h2>From need to published challenge.</h2><ul className="feature-list"><li><strong>Describe</strong><span>Start from the business need.</span></li><li><strong>Clarify</strong><span>Answer focused questions and shape the brief.</span></li><li><strong>Publish</strong><span>Manage visibility and review team proposals.</span></li></ul></aside>
      </div>
    </section>
  )
}
