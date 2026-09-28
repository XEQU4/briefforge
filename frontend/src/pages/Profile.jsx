import { useAuth } from '../auth/AuthContext'

export default function Profile() {
  const { user } = useAuth()
  const createdAt = user.created_at ? new Date(user.created_at) : null
  const hasDate = createdAt && !Number.isNaN(createdAt.getTime())

  return (
    <section className="page profile-page">
      <header className="page-header account-page-header">
        <span className="eyebrow">Your account</span>
        <h1>Profile</h1>
        <p>One account for your teams and business workspaces.</p>
      </header>
      <section className="feature-panel profile-details" aria-labelledby="account-details-heading">
        <h2 id="account-details-heading">Account details</h2>
        <dl>
          <div><dt>Display name</dt><dd>{user.display_name?.trim() || 'Not provided'}</dd></div>
          <div><dt>Email</dt><dd>{user.email}</dd></div>
          {hasDate && <div><dt>Account created</dt><dd><time dateTime={user.created_at}>{createdAt.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</time></dd></div>}
        </dl>
        <p className="profile-note">Profile editing is not available yet.</p>
      </section>
    </section>
  )
}
