import { useState } from 'react'

function initialsFor(user) {
  const name = user.display_name?.trim()
  const parts = name ? name.split(/\s+/) : user.email.split('@')[0].split(/[._-]+/).filter(Boolean)
  const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' })
  const characters = (value) => Array.from(segmenter.segment(value), ({ segment }) => segment)
  const initials = parts.length > 1
    ? parts.slice(0, 2).map((part) => characters(part)[0]).join('')
    : characters(parts[0] || '').slice(0, 2).join('')
  return initials.toLocaleUpperCase() || 'BF'
}

export default function UserAvatar({ user, className = '' }) {
  const [failedUrl, setFailedUrl] = useState(null)
  return (
    <span className={`account-initials ${className}`} aria-hidden="true">
      {user.avatar_url && failedUrl !== user.avatar_url
        ? <img src={user.avatar_url} alt="" onError={() => setFailedUrl(user.avatar_url)} />
        : initialsFor(user)}
    </span>
  )
}
