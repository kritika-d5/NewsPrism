import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const searchArticles = async (query, dateFrom, dateTo, sources, limit = 50) => {
  const response = await api.post('/search', {
    query,
    date_from: dateFrom,
    date_to: dateTo,
    sources,
    limit,
  })
  return response.data
}

export const analyzeQuery = async (query, dateFrom, dateTo, sources) => {
  const response = await api.post('/search/analyze', {
    query,
    date_from: dateFrom,
    date_to: dateTo,
    sources,
  })
  return response.data
}

/**
 * Run the agentic pipeline and stream each agent's progress.
 * `onEvent` receives parsed SSE events: {type: 'agent'|'result'|'error'|'done', ...}.
 * Resolves with the final result payload (or throws on error).
 */
export const analyzeQueryStream = async (
  { query, dateFrom, dateTo, sources },
  onEvent,
) => {
  const response = await fetch(`${API_URL}/search/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      date_from: dateFrom,
      date_to: dateTo,
      sources,
    }),
  })

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `Request failed (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult = null
  let streamError = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      const dataLine = frame
        .split('\n')
        .find((line) => line.startsWith('data:'))
      if (!dataLine) continue

      let event
      try {
        event = JSON.parse(dataLine.slice(5).trim())
      } catch {
        continue
      }

      onEvent?.(event)

      if (event.type === 'result') finalResult = event.result
      if (event.type === 'error') streamError = event.error
    }
  }

  if (streamError) throw new Error(streamError)
  return finalResult
}

export const getCluster = async (clusterId) => {
  const response = await api.get(`/search/clusters/${clusterId}`)
  return response.data
}

export const getArticle = async (articleId) => {
  const response = await api.get(`/search/articles/${articleId}`)
  return response.data
}

export default api
