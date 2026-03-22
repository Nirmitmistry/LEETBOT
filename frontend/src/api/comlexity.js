export const analyzeComplexity = (API, code, language = 'python') =>
  API.post('/complexity', { code, language })