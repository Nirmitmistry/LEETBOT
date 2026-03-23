export const createSession = (API, slug) =>
  API.post('/sessions', { slug })

export const getMySessions = (API) =>
  API.get('/sessions/me')

export const getSession = (API, sessionId) =>
  API.get(`/sessions/${sessionId}`)

export const deleteSession = (API, sessionId) =>
  API.delete(`/sessions/${sessionId}`)