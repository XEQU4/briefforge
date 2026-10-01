import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import UserAvatar from './UserAvatar'

export default function AccountMenu({ user, loggingOut, onLogout }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const initialFocus = useRef('first')
  const menuId = useId()

  useEffect(() => {
    if (!open) return undefined
    const items = menuRef.current.querySelectorAll('[role="menuitem"]')
    items[initialFocus.current === 'last' ? items.length - 1 : 0]?.focus()
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function handleMenuKey(event) {
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const items = Array.from(menuRef.current.querySelectorAll('[role="menuitem"]'))
    const current = items.indexOf(document.activeElement)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
      : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
    items[next]?.focus()
  }

  return (
    <div className="account-menu" ref={rootRef} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false)
    }}>
      <button
        className="account-trigger"
        type="button"
        ref={triggerRef}
        aria-label={`Account menu for ${user.display_name?.trim() || user.email}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        disabled={loggingOut}
        onClick={() => { initialFocus.current = 'first'; setOpen((value) => !value) }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false)
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            initialFocus.current = event.key === 'ArrowUp' ? 'last' : 'first'
            if (open) {
              const items = menuRef.current.querySelectorAll('[role="menuitem"]')
              items[initialFocus.current === 'last' ? items.length - 1 : 0]?.focus()
            }
            setOpen(true)
          }
        }}
      >
        <UserAvatar user={user} />
        <span className="account-chevron" aria-hidden="true">▾</span>
      </button>
      {open && <div className="account-dropdown">
        <div className="account-identity"><strong>{user.display_name?.trim() || 'Your account'}</strong><span>{user.email}</span></div>
        <div id={menuId} role="menu" aria-label="Account" ref={menuRef} onKeyDown={handleMenuKey}>
          <Link className="account-menu-item" role="menuitem" to="/profile">Profile</Link>
          <Link className="account-menu-item" role="menuitem" to="/my-teams">My teams</Link>
          <Link className="account-menu-item" role="menuitem" to="/proposals/mine">My proposals</Link>
          <Link className="account-menu-item" role="menuitem" to="/business">Business workspace</Link>
          <div className="account-menu-divider" role="separator" />
          <button className="account-menu-item" role="menuitem" type="button" disabled={loggingOut} onClick={() => { setOpen(false); onLogout() }}>Log out</button>
        </div>
      </div>}
    </div>
  )
}
