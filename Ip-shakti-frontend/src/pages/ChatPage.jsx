import { useCallback, useEffect, useRef, useState } from 'react'
import AuthPage from '../components/AuthPage.jsx'
import ChatComposer from '../components/ChatComposer.jsx'
import ChatHeader from '../components/ChatHeader.jsx'
import ChatMessages from '../components/ChatMessages.jsx'
import ConversationSidebar from '../components/ConversationSidebar.jsx'
import { askQuestion, getConversations, getErrorMessage } from '../services/api.js'
import { clearStoredAuth, getStoredAuth, storeAuth } from '../services/authStorage.js'

export default function ChatPage() {
  const [auth, setAuth] = useState(getStoredAuth)
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const handleLogout = useCallback(() => {
    clearStoredAuth()
    setAuth(null)
    setConversations([])
    setCurrentConversationId(null)
    setMessages([])
    setQuery('')
    setError('')
    setHistoryError('')
  }, [])

  const fetchConversations = useCallback(() => getConversations(auth.token), [auth])

  const loadConversations = useCallback(async () => {
    if (!auth?.token) return

    setHistoryLoading(true)
    setHistoryError('')
    try {
      setConversations(await fetchConversations())
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        handleLogout()
      } else {
        setHistoryError(getErrorMessage(requestError))
      }
    } finally {
      setHistoryLoading(false)
    }
  }, [auth, fetchConversations, handleLogout])

  useEffect(() => {
    if (!auth?.token) return undefined
    let active = true

    fetchConversations()
      .then((data) => {
        if (active) setConversations(data)
      })
      .catch((requestError) => {
        if (!active) return
        if (requestError.response?.status === 401) {
          handleLogout()
        } else {
          setHistoryError(getErrorMessage(requestError))
        }
      })

    return () => {
      active = false
    }
  }, [auth, fetchConversations, handleLogout])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  function handleAuthenticated(response) {
    setAuth(storeAuth(response))
  }

  function startNewChat() {
    setCurrentConversationId(null)
    setMessages([])
    setQuery('')
    setError('')
    setSidebarOpen(false)
    textareaRef.current?.focus()
  }

  function openConversation(conversation) {
    setCurrentConversationId(conversation.id)
    setMessages(
      (conversation.messages || []).map((message) => ({
        role: message.role,
        content: message.content,
      })),
    )
    setQuery('')
    setError('')
    setSidebarOpen(false)
  }

  async function sendMessage(message = query) {
    const trimmedMessage = message.trim()
    if (!trimmedMessage || isLoading || !auth?.token) return

    setMessages((currentMessages) => [
      ...currentMessages,
      { role: 'user', content: trimmedMessage },
    ])
    setQuery('')
    setError('')
    setIsLoading(true)

    try {
      const payload = { query: trimmedMessage }
      if (currentConversationId) payload.conversationId = currentConversationId

      const response = await askQuestion(auth.token, payload)
      const answer =
        typeof response.data === 'string'
          ? response.data
          : response.data?.answer ?? response.data?.response ?? ''

      if (!answer) {
        throw new Error('The server returned an empty response.')
      }

      const returnedConversationId = response.headers['x-conversation-id']
      if (returnedConversationId) {
        setCurrentConversationId(returnedConversationId)
      }
      setMessages((currentMessages) => [
        ...currentMessages,
        { role: 'assistant', content: answer },
      ])
      void loadConversations()
    } catch (requestError) {
      if (requestError.response?.status === 401) {
        handleLogout()
      } else {
        setError(getErrorMessage(requestError))
      }
    } finally {
      setIsLoading(false)
      textareaRef.current?.focus()
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    sendMessage()
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  if (!auth) {
    return <AuthPage onAuthenticated={handleAuthenticated} />
  }

  return (
    <main className="h-dvh overflow-hidden bg-[#f7f8fa] text-slate-900">
      <div className="mx-auto flex h-full max-w-[1440px]">
        <ConversationSidebar
          auth={auth}
          conversations={conversations}
          currentConversationId={currentConversationId}
          historyLoading={historyLoading}
          historyError={historyError}
          sidebarOpen={sidebarOpen}
          isLoading={isLoading}
          onStartNewChat={startNewChat}
          onLoadConversations={() => void loadConversations()}
          onOpenConversation={openConversation}
          onLogout={handleLogout}
          onClose={() => setSidebarOpen(false)}
        />

        <section className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
          <ChatHeader
            onToggleSidebar={() => setSidebarOpen(true)}
            onStartNewChat={startNewChat}
          />
          <ChatMessages
            messages={messages}
            isLoading={isLoading}
            error={error}
            messagesEndRef={messagesEndRef}
            onSendSuggestion={sendMessage}
          />
          <ChatComposer
            query={query}
            textareaRef={textareaRef}
            isLoading={isLoading}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            onSubmit={handleSubmit}
          />
        </section>
      </div>
    </main>
  )
}
