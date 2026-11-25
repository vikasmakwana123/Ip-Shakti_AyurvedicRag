import axios from 'axios'

const API_ROOT = (import.meta.env.BACKEND_URL || 'http://localhost:8080').replace(/\/+$/, '')

export async function authenticate(endpoint, payload) {
  const { data } = await axios.post(`${API_ROOT}${endpoint}`, payload)
  return data
}

export async function getConversations(token) {
  const { data } = await axios.get(`${API_ROOT}/api/conversations`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!Array.isArray(data)) {
    throw new Error('The server returned an invalid conversation list.')
  }
  return data
}

export function askQuestion(token, payload) {
  return axios.post(`${API_ROOT}/groq/api/ask`, payload, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data === 'string' && data.trim()) return data
  if (data && typeof data === 'object') {
    return data.detail || data.message || data.title || error.message
  }
  return error.message || 'The request could not be completed.'
}
