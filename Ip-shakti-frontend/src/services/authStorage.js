const TOKEN_KEY = 'ip-shakti-access-token'
const NAME_KEY = 'ip-shakti-user-name'
const EMAIL_KEY = 'ip-shakti-user-email'

export function getStoredAuth() {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return null

  return {
    token,
    name: localStorage.getItem(NAME_KEY) || '',
    email: localStorage.getItem(EMAIL_KEY) || '',
  }
}

export function storeAuth(response) {
  const auth = {
    token: response.accessToken,
    name: response.name || '',
    email: response.email || '',
  }
  localStorage.setItem(TOKEN_KEY, auth.token)
  localStorage.setItem(NAME_KEY, auth.name)
  localStorage.setItem(EMAIL_KEY, auth.email)
  return auth
}

export function clearStoredAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
  localStorage.removeItem(EMAIL_KEY)
}
