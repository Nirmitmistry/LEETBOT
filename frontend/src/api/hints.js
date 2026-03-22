export const getHint = (API, slug, sessionId) =>
  API.post(`/hints/${slug}`, { session_id: sessionId })