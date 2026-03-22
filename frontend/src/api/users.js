export const getMe = (API) =>
  API.get('/users/me')

export const updateMe = (API, data) =>
  API.patch('/users/me', data)

export const markSolved = (API, slug) =>
  API.post(`/users/me/solved/${slug}`)

export const markAttempted = (API, slug) =>
  API.post(`/users/me/attempted/${slug}`)