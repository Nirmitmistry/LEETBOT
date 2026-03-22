export const sendChatMessage = (API, messages, problemContext = {}) =>
  API.post('/chat', {
    messages,
    problem_slug: problemContext.slug || null,
    problem_title: problemContext.title || null,
    problem_description: problemContext.description || null,
  })