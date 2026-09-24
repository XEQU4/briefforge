import { useEffect, useId, useRef, useState } from 'react'

export default function Select({ label, value, options, onChange, placeholder = 'Select an option', disabled = false, ariaLabel }) {
  const [open, setOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const [placement, setPlacement] = useState('bottom')
  const [menuMaxHeight, setMenuMaxHeight] = useState(280)
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const id = useId()
  const labelId = `${id}-label`
  const valueId = `${id}-value`
  const listboxId = `${id}-listbox`
  const selectedIndex = options.findIndex((option) => option.value === value)
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null

  function updatePlacement() {
    const rect = rootRef.current?.getBoundingClientRect()
    if (!rect) return
    const spaceBelow = window.innerHeight - rect.bottom
    const opensAbove = spaceBelow < 260 && rect.top > spaceBelow
    const availableSpace = opensAbove ? rect.top : spaceBelow
    setPlacement(opensAbove ? 'top' : 'bottom')
    setMenuMaxHeight(Math.max(96, Math.min(280, availableSpace - 16)))
  }

  function openMenu() {
    if (disabled || options.length === 0) return
    updatePlacement()
    setHighlightedIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setOpen(true)
  }

  function closeMenu({ restoreFocus = false } = {}) {
    setOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }

  function selectOption(index) {
    const option = options[index]
    if (!option) return
    onChange(option.value)
    closeMenu({ restoreFocus: true })
  }

  function moveHighlight(direction) {
    setHighlightedIndex((current) => (current + direction + options.length) % options.length)
  }

  function handleKeyDown(event) {
    if (disabled) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) openMenu()
      else moveHighlight(event.key === 'ArrowDown' ? 1 : -1)
      return
    }
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault()
      if (open) selectOption(highlightedIndex)
      else openMenu()
      return
    }
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      closeMenu({ restoreFocus: true })
      return
    }
    if (event.key === 'Home' && open) { event.preventDefault(); setHighlightedIndex(0) }
    if (event.key === 'End' && open) { event.preventDefault(); setHighlightedIndex(options.length - 1) }
    if (event.key === 'Tab') closeMenu()
  }

  useEffect(() => {
    if (!open) return undefined
    const handlePointerDown = (event) => { if (!rootRef.current?.contains(event.target)) closeMenu() }
    const handleFocusIn = (event) => { if (!rootRef.current?.contains(event.target)) closeMenu() }
    const handleViewportChange = () => updatePlacement()
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('focusin', handleFocusIn)
    window.addEventListener('resize', handleViewportChange)
    window.addEventListener('scroll', handleViewportChange, true)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('focusin', handleFocusIn)
      window.removeEventListener('resize', handleViewportChange)
      window.removeEventListener('scroll', handleViewportChange, true)
    }
  }, [open])

  useEffect(() => {
    if (open && selectedIndex >= 0) setHighlightedIndex(selectedIndex)
  }, [open, selectedIndex])

  return (
    <div className="custom-select" ref={rootRef}>
      {label && <span className="custom-select-label" id={labelId}>{label}</span>}
      <button
        type="button"
        role="combobox"
        className="custom-select-trigger"
        ref={triggerRef}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-labelledby={!ariaLabel ? (label ? `${labelId} ${valueId}` : valueId) : undefined}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-activedescendant={open ? `${listboxId}-option-${highlightedIndex}` : undefined}
        data-open={open}
        onClick={() => open ? closeMenu() : openMenu()}
        onKeyDown={handleKeyDown}
      >
        <span id={valueId} className={selectedOption ? '' : 'is-placeholder'}>{selectedOption?.label || placeholder}</span>
        <span className="custom-select-chevron" aria-hidden="true" />
      </button>
      {open && (
        <ul className={`custom-select-menu opens-${placement}`} id={listboxId} role="listbox" aria-label={!label ? ariaLabel : undefined} aria-labelledby={label ? labelId : undefined} style={{ maxHeight: `${menuMaxHeight}px` }}>
          {options.map((option, index) => {
            const selected = option.value === value
            return (
              <li
                className="custom-select-option"
                id={`${listboxId}-option-${index}`}
                key={option.value}
                role="option"
                aria-selected={selected}
                data-highlighted={highlightedIndex === index}
                onMouseEnter={() => setHighlightedIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(index)}
              >
                <span>{option.label}</span><span className="custom-select-check" aria-hidden="true">{selected ? '✓' : ''}</span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
