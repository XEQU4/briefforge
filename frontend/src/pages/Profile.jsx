import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { deleteAvatar, updateProfile, uploadAvatar } from '../api/profile'
import UserAvatar from '../components/UserAvatar'
import uiError from '../utils/uiError'

const MAX_AVATAR_BYTES = 2 * 1024 * 1024
const AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/webp']

export default function Profile() {
  const { user, updateUser } = useAuth()
  return <ProfileEditor key={user.id} user={user} updateUser={updateUser} />
}

function ProfileEditor({ user, updateUser }) {
  const [displayName, setDisplayName] = useState(user.display_name || '')
  const [selected, setSelected] = useState(null)
  const [preview, setPreview] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const fileInput = useRef(null)
  const mounted = useRef(false)
  const pending = useRef(false)
  const createdAt = user.created_at ? new Date(user.created_at) : null
  const hasDate = createdAt && !Number.isNaN(createdAt.getTime())

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (!selected) { setPreview(''); return undefined }
    const url = URL.createObjectURL(selected)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [selected])

  function chooseAvatar(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError('')
    setSuccess('')
    setSelected(null)
    if (!AVATAR_TYPES.includes(file.type)) { setError('Unsupported image type. Choose JPEG, PNG, or WebP.'); return }
    if (file.size > MAX_AVATAR_BYTES) { setError('Image must be 2 MB or smaller.'); return }
    setSelected(file)
  }

  async function submit(action) {
    if (pending.current) return
    pending.current = true
    setBusy(action)
    setError('')
    setSuccess('')
    try {
      const updated = action === 'name' ? await updateProfile(displayName)
        : action === 'upload' ? await uploadAvatar(selected) : await deleteAvatar()
      if (!mounted.current) return
      updateUser(updated)
      if (action === 'name') setDisplayName(updated.display_name || '')
      else setSelected(null)
      setSuccess(action === 'name' ? 'Display name saved.' : action === 'upload' ? 'Avatar updated.' : 'Avatar removed.')
    } catch (reason) {
      if (!mounted.current) return
      const avatarErrors = {
        413: 'Image must be 2 MB or smaller.',
        415: 'Unsupported image type. Choose JPEG, PNG, or WebP.',
        422: 'Unable to use this image. Choose a valid JPEG, PNG, or WebP, up to 16 megapixels and 8192 pixels per side.',
      }
      setError(action === 'upload' && avatarErrors[reason.status] ? avatarErrors[reason.status]
        : uiError(reason, action === 'name' ? 'Unable to save your name. Please try again.' : 'Unable to update avatar. Please try again.'))
    } finally {
      pending.current = false
      if (mounted.current) setBusy('')
    }
  }

  return (
    <section className="page profile-page">
      <header className="page-header account-page-header">
        <span className="eyebrow">Your account</span>
        <h1>Profile</h1>
        <p>One account for your teams and business workspaces.</p>
      </header>
      <section className="feature-panel profile-details" aria-labelledby="account-details-heading" aria-busy={Boolean(busy)}>
        <div className="profile-avatar-area">
          {selected && preview
            ? <img className="profile-avatar" src={preview} alt="Selected avatar preview" onError={() => { setSelected(null); setError('Unable to preview this image. Choose another JPEG, PNG, or WebP.'); }} />
            : <UserAvatar user={user} className="profile-avatar" />}
          <div className="profile-avatar-controls">
            <div className="button-row">
              <button className="secondary" type="button" disabled={Boolean(busy)} onClick={() => fileInput.current?.click()}>Change avatar</button>
              {user.avatar_url && <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => submit('remove')}>{busy === 'remove' ? 'Removing…' : 'Remove avatar'}</button>}
            </div>
            <input ref={fileInput} type="file" accept={AVATAR_TYPES.join(',')} hidden aria-label="Choose avatar image" onChange={chooseAvatar} disabled={Boolean(busy)} />
            <p className="profile-note">JPEG, PNG, or WebP. Up to 2 MB.</p>
            {selected && <div className="profile-avatar-preview-actions">
              <p className="profile-note">Preview only. Upload to save your avatar.</p>
              <div className="button-row">
                <button type="button" disabled={Boolean(busy)} onClick={() => submit('upload')}>{busy === 'upload' ? 'Uploading…' : 'Upload avatar'}</button>
                <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => setSelected(null)}>Cancel</button>
              </div>
            </div>}
          </div>
        </div>
        <div aria-live="polite" aria-atomic="true">{success && <p className="feedback feedback-success">{success}</p>}</div>
        {error && <p className="feedback feedback-error" role="alert">{error}</p>}
        <h2 id="account-details-heading">Account details</h2>
        <form className="profile-form" onSubmit={(event) => { event.preventDefault(); submit('name') }}>
          <label>Display name <span className="optional-label">Optional</span>
            <input name="display_name" autoComplete="name" maxLength={200} value={displayName} disabled={Boolean(busy)} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <dl>
            <div><dt>Email <span className="optional-label">Read-only</span></dt><dd>{user.email}</dd></div>
            {hasDate && <div><dt>Account created</dt><dd><time dateTime={user.created_at}>{createdAt.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}</time></dd></div>}
          </dl>
          <button disabled={Boolean(busy)}>{busy === 'name' ? 'Saving…' : 'Save changes'}</button>
        </form>
      </section>
    </section>
  )
}
