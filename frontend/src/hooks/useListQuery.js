import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router'

// Define the schema outside the component so it stays stable between renders.
export default function useListQuery(schema) {
  const [params, setParams] = useSearchParams()
  const values = {}
  const normalized = new URLSearchParams(params)
  for (const [key, rule] of Object.entries(schema)) {
    let value = params.get(key) || rule.default || ''
    if (rule.options && !rule.options.includes(value)) value = rule.default || ''
    if (rule.maxLength) value = value.slice(0, rule.maxLength)
    values[key] = value
    if (!value || value === rule.default) normalized.delete(key)
    else normalized.set(key, value)
  }
  const requestedPage = Number(params.get('page') || 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  if (page === 1) normalized.delete('page')
  else normalized.set('page', String(page))
  const normalizedSearch = normalized.toString()

  useEffect(() => {
    if (params.toString() !== normalizedSearch) setParams(normalizedSearch, { replace: true })
  }, [params, normalizedSearch, setParams])

  const update = useCallback((changes, { replace = false } = {}) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('page')
      for (const [key, value] of Object.entries(changes)) {
        if (!value || value === schema[key]?.default || (key === 'page' && value === 1)) next.delete(key)
        else next.set(key, String(value))
      }
      return next
    }, { replace })
  }, [schema, setParams])

  const fitPage = useCallback((pages) => {
    const lastPage = Math.max(pages, 1)
    if (page <= lastPage) return true
    update({ page: lastPage }, { replace: true })
    return false
  }, [page, update])

  return { ...values, page, update, fitPage }
}
