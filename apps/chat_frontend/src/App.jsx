import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  createConversation,
  getUserId,
  listConversations,
  listMessages,
  postMessage,
  runEventsUrl,
  setUserId,
} from './api.js'

function extractDelta(obj) {
  if (!obj || typeof obj !== 'object') return null
  const d = obj.delta
  if (typeof d === 'string' && d) return d
  if (d && typeof d === 'object' && typeof d.text === 'string' && d.text) return d.text
  return null
}

function extractResultText(obj) {
  if (!obj || typeof obj !== 'object') return null
  if (typeof obj.result_text === 'string' && obj.result_text) return obj.result_text
  if (typeof obj.resultText === 'string' && obj.resultText) return obj.resultText
  if (obj.result && typeof obj.result === 'object' && typeof obj.result.text === 'string') return obj.result.text
  return null
}

export default function App() {
  const [userId, setUserIdState] = useState(getUserId())
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streamText, setStreamText] = useState('')
  const [statusText, setStatusText] = useState('')
  const esRef = useRef(null)

  const canUse = userId.trim().length > 0

  async function refreshConversations() {
    if (!canUse) return
    const list = await listConversations(userId)
    setConversations(list)
    if (!activeConversationId && list.length) {
      setActiveConversationId(list[0].conversation_id)
    }
  }

  async function refreshMessages(conversationId) {
    if (!canUse || !conversationId) return
    const list = await listMessages(userId, conversationId)
    setMessages(list)
  }

  useEffect(() => {
    setUserId(userId)
  }, [userId])

  useEffect(() => {
    refreshConversations().catch((e) => setStatusText(String(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canUse])

  useEffect(() => {
    if (activeConversationId) {
      refreshMessages(activeConversationId).catch((e) => setStatusText(String(e)))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId])

  async function onNewConversation() {
    if (!canUse) return
    setStatusText('Creating conversation...')
    const meta = await createConversation(userId, 'New conversation')
    await refreshConversations()
    setActiveConversationId(meta.conversation_id)
    setStatusText('')
  }

  function stopStream() {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }

  async function onSend() {
    if (!canUse || !activeConversationId) return
    const content = input.trim()
    if (!content) return

    stopStream()
    setStreamText('')
    setStatusText('Sending...')

    setInput('')

    const { run_id } = await postMessage(userId, activeConversationId, content)

    const url = runEventsUrl(userId, activeConversationId, run_id)
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (evt) => {
      try {
        const obj = JSON.parse(evt.data)
        const delta = extractDelta(obj)
        const resText = extractResultText(obj)
        if (delta) setStreamText((t) => t + delta)
        if (resText) setStreamText(resText)
      } catch {
        // Fallback: show raw
        setStreamText((t) => t + evt.data)
      }
    }

    es.addEventListener('status', (evt) => {
      setStatusText('Done')
      stopStream()
      refreshMessages(activeConversationId).catch((e) => setStatusText(String(e)))
    })

    es.onerror = () => {
      setStatusText('Stream error (check API)')
      // keep connection; EventSource may retry
    }

    setStatusText('Running...')
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">cc3 chat</div>

        <label className="field">
          <div className="label">User ID</div>
          <input
            value={userId}
            onChange={(e) => setUserIdState(e.target.value)}
            placeholder="alice"
          />
        </label>

        <button className="button" onClick={onNewConversation} disabled={!canUse}>
          New conversation
        </button>

        <div className="sectionTitle">Conversations</div>
        <div className="convList">
          {conversations.map((c) => (
            <button
              key={c.conversation_id}
              className={
                'convItem ' +
                (c.conversation_id === activeConversationId ? 'active' : '')
              }
              onClick={() => {
                stopStream()
                setStreamText('')
                setActiveConversationId(c.conversation_id)
              }}
            >
              <div className="convTitle">{c.title || c.conversation_id}</div>
              <div className="convId">{c.conversation_id}</div>
            </button>
          ))}
        </div>

        <div className="status">{statusText}</div>
      </aside>

      <main className="main">
        <div className="messages">
          {messages.map((m) => (
            <div key={m.message_id} className={'msg ' + m.role}>
              <div className="role">{m.role}</div>
              <div className="content">{m.content}</div>
            </div>
          ))}

          {streamText ? (
            <div className="msg assistant streaming">
              <div className="role">assistant (stream)</div>
              <div className="content">{streamText}</div>
            </div>
          ) : null}
        </div>

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            rows={3}
            disabled={!canUse || !activeConversationId}
          />
          <button className="button" onClick={onSend} disabled={!canUse || !activeConversationId}>
            Send
          </button>
        </div>
      </main>
    </div>
  )
}
