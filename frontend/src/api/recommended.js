export const getRecommendations = (API, slugs = [], preferences = {}) =>
  API.post('/recommend', { solved_slugs: slugs, preferences })