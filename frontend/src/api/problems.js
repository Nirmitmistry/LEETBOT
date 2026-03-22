export const searchProblems = (API, query) =>
  API.get(`/problems/search`, { params: { q: query } })

export const getProblem = (API, slug) =>
  API.get(`/problems/${slug}`)

export const getAllProblems = (API) =>
  API.get(`/problems`)