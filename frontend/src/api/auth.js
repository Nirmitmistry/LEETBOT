export const registerUser = (API, data) =>
  API.post('/auth/register', data)

export const loginUser = (API, data) =>
  API.post('/auth/login', data)