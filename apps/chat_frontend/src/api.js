const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8001'

export function getUserId() {
  return localStorage.getItem('cc3_user_id') || ''
}

export function setUserId(userId) {
  localStorage.setItem('cc3_user_id', userId)
}

function headers(userId) {
  return {
    'Content-Type': 'application/json',
    'X-User-Id': userId,
  }
}

export async function listConversations(userId) {
  const res = await fetch(`${API_BASE}/v1/conversations`, {
    headers: headers(userId),
  })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function createConversation(userId, title) {
  const res = await fetch(`${API_BASE}/v1/conversations`, {
    method: 'POST',
    headers: headers(userId),
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function listMessages(userId, conversationId) {
  const res = await fetch(`${API_BASE}/v1/conversations/${conversationId}/messages`, {
    headers: headers(userId),
  })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

export async function postMessage(userId, conversationId, content) {
  const res = await fetch(`${API_BASE}/v1/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: headers(userId),
    body: JSON.stringify({ content }),
  })
  if (!res.ok) throw new Error(await res.text())
  return await res.json()
}

export function runEventsUrl(userId, conversationId, runId) {
  // EventSource can't set custom headers, so pass user_id in query.
  const u = new URL(`${API_BASE}/v1/conversations/${conversationId}/runs/${runId}/events.sse`)
  u.searchParams.set('user_id', userId)
  return u.toString()
}
