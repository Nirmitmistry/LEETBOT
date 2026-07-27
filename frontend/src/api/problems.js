export const searchProblems = (API, query) =>
  API.get(`/problems/search`, { params: { q: query } })

export const getProblem = (API, slug) =>
  API.get(`/problems/${slug}`)

export const getAllProblems = (API, skip = 0, limit = 50) =>
  API.get(`/problems`, { params: { skip, limit } })