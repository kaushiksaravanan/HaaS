import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader, AlertCircle, ShieldAlert, Globe, ExternalLink, Search, Sparkles, ArrowRight, CheckCircle2, Lock, RefreshCw, MousePointer2, FileText, Link2, Trash2 } from 'lucide-react'
import { agentAPI } from '../services/api'
import ReactMarkdown from 'react-markdown'
import PlaywrightBrowser from '../components/PlaywrightBrowser'

const WELCOME_MESSAGE = {
  id: '1',
  role: 'assistant',
  content: `Hi, I'm your **HANA Ops agent**. Here's what I can do:

🖥️ **Run Commands** — \`run uptime\`, \`execute df -h\`, \`sapcontrol -nr 02 -function GetProcessList\`
🩺 **Health & Status** — \`check health\`, \`show status\`
🔍 **Diagnostics** — \`run diagnostics\`
💾 **Backups** — \`check backup status\`
⚡ **SQL Optimization** — Paste a query for analysis
🌐 **Web Search** — Toggle Browser mode to search SAP docs

What would you like to check?`,
  timestamp: new Date().toISOString(),
}

function loadChatHistory() {
  try {
    const saved = localStorage.getItem('agent_chat_history')
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch { /* ignore */ }
  return [WELCOME_MESSAGE]
}

export default function AgentChat() {
  const [messages, setMessages] = useState(loadChatHistory)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [conversationId] = useState(() => `conv_${Date.now()}`)
  const [adminMode, setAdminMode] = useState(() => {
    try {
      return localStorage.getItem('agent_admin_mode') === 'true'
    } catch {
      return false
    }
  })
  const [useBrowser, setUseBrowser] = useState(() => {
    try {
      return localStorage.getItem('agent_use_browser') === 'true'
    } catch {
      return false
    }
  })
  const [autonomousBrowser, setAutonomousBrowser] = useState(() => {
    try {
      return localStorage.getItem('agent_autonomous_browser') === 'true'
    } catch {
      return false
    }
  })
  const [browserSession, setBrowserSession] = useState(null) // Tracks active browser session
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Persist chat history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('agent_chat_history', JSON.stringify(messages))
    } catch { /* ignore */ }
  }, [messages])

  const clearChat = () => {
    setMessages([WELCOME_MESSAGE])
    try { localStorage.removeItem('agent_chat_history') } catch { /* ignore */ }
  }

  useEffect(() => {
    try {
      localStorage.setItem('agent_admin_mode', adminMode ? 'true' : 'false')
    } catch {
      // ignore storage issues in restricted browsers
    }
  }, [adminMode])

  useEffect(() => {
    try {
      localStorage.setItem('agent_use_browser', useBrowser ? 'true' : 'false')
    } catch {
      // ignore storage issues in restricted browsers
    }
  }, [useBrowser])

  useEffect(() => {
    try {
      localStorage.setItem('agent_autonomous_browser', autonomousBrowser ? 'true' : 'false')
    } catch {
      // ignore storage issues in restricted browsers
    }
  }, [autonomousBrowser])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmedInput = input.trim()
    if (!trimmedInput || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setError(null)
    setBrowserSession(null)

    // Auto-detect knowledge queries that should use browser
    // Only trigger browser for explicit SAP note lookups or when user says "browse"
    const inputLower = trimmedInput.toLowerCase()
    const isSapNoteQuery = /\b(?:sap\s*)?note\s*\d{5,7}\b|\b\d{6,7}\b/.test(inputLower)
    const isExplicitBrowse = ['browse', 'look up', 'search the web'].some(p => inputLower.includes(p))
    const shouldUseBrowser = autonomousBrowser && (isSapNoteQuery || isExplicitBrowse)

    try {
      const response = await agentAPI.chat(trimmedInput, conversationId, {
        admin_mode: adminMode,
        use_browser: useBrowser || shouldUseBrowser,
        autonomous_browser: shouldUseBrowser,
      })

      const browserActive = response.data.browser_active === true

      if (browserActive) {
        // WebSocket will handle the response — show browser UI, don't add assistant message yet
        setBrowserSession({ query: trimmedInput, active: true })
      } else {
        // Normal response — add it directly
        const sources = response.data.sources || []
        const assistantMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response.data.response,
          sources,
          timestamp: new Date(),
        }
        setMessages(prev => [...prev, assistantMessage])
        setIsLoading(false)
      }
    } catch (err) {
      setError('Failed to get response from agent. Please try again.')
      console.error('Chat error:', err)
      setIsLoading(false)
    }
  }

  // Called when PlaywrightBrowser completes — add the synthesized response as a message
  const handleBrowserComplete = (result) => {
    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: result.response || 'Browsing complete.',
      sources: result.sources || [],
      browserSummary: {
        actionCount: result.actionCount || 0,
        sources: result.sources || [],
      },
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, assistantMessage])
    setBrowserSession(prev => prev ? { ...prev, active: false } : null)
    setIsLoading(false)
  }

  const handleBrowserError = (errorMsg) => {
    setError(`Browser error: ${errorMsg}`)
    setBrowserSession(null)
    setIsLoading(false)
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="h-20 bg-card border-b border-border flex items-center px-8">
        <div className="p-2 bg-accent rounded-lg mr-4">
          <Bot className="w-5 h-5 text-accent-foreground" />
        </div>
        <div>
          <h2 className="font-serif text-xl font-semibold text-foreground">Agent Chat</h2>
          <p className="font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            GenAIHub • SAP AI Core
          </p>
        </div>
        <div className="ml-auto flex items-center gap-6">
          <button
            type="button"
            onClick={() => setUseBrowser((prev) => !prev)}
            className={`flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-md border transition-all ${
              useBrowser
                ? 'bg-blue-50 text-blue-600 border-blue-500/40'
                : 'bg-muted text-muted-foreground border-border'
            }`}
            title="When enabled, search SAP docs and Google for answers"
          >
            <Search className="w-4 h-4" />
            {useBrowser ? 'Browser ON' : 'Browser OFF'}
          </button>
          <button
            type="button"
            onClick={() => setAutonomousBrowser((prev) => !prev)}
            className={`flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-md border transition-all ${
              autonomousBrowser
                ? 'bg-purple-50 text-purple-600 border-purple-500/40'
                : 'bg-muted text-muted-foreground border-border'
            }`}
            title="Autonomous browser agent (like Manus) - uses browser-use for complex web tasks"
          >
            <Sparkles className="w-4 h-4" />
            {autonomousBrowser ? 'Auto ON' : 'Auto OFF'}
          </button>
          <button
            type="button"
            onClick={() => setAdminMode((prev) => !prev)}
            className={`flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-md border transition-all ${
              adminMode
                ? 'bg-danger-50 text-danger-600 border-danger-500/40'
                : 'bg-muted text-muted-foreground border-border'
            }`}
            title="Admin mode allows unrestricted command execution via chat"
          >
            <ShieldAlert className="w-4 h-4" />
            {adminMode ? 'Admin Mode ON' : 'Admin Mode OFF'}
          </button>
          <button
            type="button"
            onClick={clearChat}
            className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-md border bg-muted text-muted-foreground border-border hover:bg-danger-50 hover:text-danger-600 hover:border-danger-500/40 transition-all"
            title="Clear chat history"
          >
            <Trash2 className="w-4 h-4" />
            Clear
          </button>
          <span className="font-mono text-xs text-muted-foreground tracking-wide">
            Session: {conversationId.slice(-8)}
          </span>
          <span className="flex items-center gap-2 text-xs font-medium text-success-600">
            <span className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></span>
            Connected
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isLoading && (
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-accent-foreground" />
              </div>
              <div className="flex-1">
                {browserSession?.active ? (
                  /* Full Playwright Browser with real screenshots and cursor tracking */
                  <PlaywrightBrowser
                    query={browserSession.query}
                    conversationId={conversationId}
                    isAutonomous={true}
                    onComplete={handleBrowserComplete}
                    onError={handleBrowserError}
                  />
                ) : (
                  /* Simple loading for non-browser mode */
                  <div className="bg-card rounded-lg p-5 border border-border shadow-soft">
                    <div className="flex items-center gap-3">
                      <Loader className="w-4 h-4 text-accent animate-spin" />
                      <span className="text-sm text-muted-foreground italic">Processing your request...</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-3 p-4 bg-danger-50 border border-danger-500/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-danger-500 flex-shrink-0" />
              <span className="text-sm text-danger-600">{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border bg-card p-6">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          {adminMode && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-danger-500/30 bg-danger-50 p-3 text-sm text-danger-700">
              <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>
                Admin mode is enabled. Your message will be translated into a shell command and executed with unrestricted prefix checks.
              </span>
            </div>
          )}
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmit(e)
                  }
                }}
                placeholder="Ask me anything about your HANA system..."
                className="w-full bg-muted border border-border rounded-lg px-4 py-3 text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent resize-none transition-all duration-200"
                rows="3"
                disabled={isLoading}
              />
              <div className="mt-2 font-mono text-[10px] text-muted-foreground tracking-wide">
                Press Enter to send • Shift+Enter for new line
              </div>
            </div>
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="bg-accent hover:bg-accent-secondary disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed text-accent-foreground rounded-lg px-6 py-3 flex items-center gap-2 font-medium transition-all duration-200 shadow-accent hover:shadow-hard min-h-[44px]"
            >
              <Send className="w-5 h-5" />
              <span>Send</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex items-start gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-foreground' : 'bg-accent'
      }`}>
        {isUser ? (
          <User className="w-5 h-5 text-background" />
        ) : (
          <Bot className="w-5 h-5 text-accent-foreground" />
        )}
      </div>

      <div className={`flex-1 max-w-3xl ${isUser ? 'flex flex-col items-end' : ''}`}>
        <div className={`rounded-lg p-5 ${
          isUser
            ? 'bg-foreground text-background'
            : 'bg-card text-foreground border border-border shadow-soft'
        }`}>
          {isUser ? (
            <div className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</div>
          ) : (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown
                components={{
                  code: ({ node, inline, className, children, ...props }) => {
                    if (inline) {
                      return (
                        <code
                          className="bg-muted px-1.5 py-0.5 rounded text-accent font-mono text-sm"
                          {...props}
                        >
                          {children}
                        </code>
                      )
                    }
                    return (
                      <pre className="bg-foreground rounded-lg p-4 overflow-x-auto my-3">
                        <code className="text-success-500 font-mono text-sm" {...props}>
                          {children}
                        </code>
                      </pre>
                    )
                  },
                  p: ({ children }) => {
                    const hasBlock = Array.isArray(children)
                      ? children.some(c => c?.type === 'pre' || c?.type === 'div')
                      : children?.type === 'pre' || children?.type === 'div'
                    if (hasBlock) return <div className="mb-3 last:mb-0 leading-relaxed">{children}</div>
                    return <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>
                  },
                  ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1.5">{children}</ul>,
                  li: ({ children }) => <li className="text-foreground">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Browser Session Summary */}
        {!isUser && message.browserSummary && (
          <div className="mt-3 w-full">
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-purple-50 border border-purple-100">
              <Globe className="w-3.5 h-3.5 text-purple-500" />
              <span className="text-xs font-medium text-purple-700">
                Browsed {message.browserSummary.actionCount} actions
              </span>
              {message.browserSummary.sources?.length > 0 && (
                <span className="text-xs text-purple-500">
                  • {message.browserSummary.sources.length} source{message.browserSummary.sources.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Browsed Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 w-full">
            <div className="flex items-center gap-2 mb-2">
              <Globe className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Pages Browsed
              </span>
            </div>
            <div className="space-y-1.5">
              {message.sources.map((source, idx) => (
                <a
                  key={idx}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-50 border border-blue-100 hover:bg-blue-100 transition-colors group"
                >
                  <div className="w-5 h-5 rounded bg-blue-100 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-200">
                    <Globe className="w-3 h-3 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-blue-800 truncate">
                      {source.title || source.url}
                    </div>
                    <div className="text-[10px] text-blue-500 font-mono truncate">
                      {source.url}
                    </div>
                  </div>
                  <ExternalLink className="w-3 h-3 text-blue-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                    source.status === 'ok'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}>
                    {source.status === 'ok' ? 'read' : source.status}
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}

        <div className="font-mono text-[10px] text-muted-foreground mt-2 px-1 tracking-wide">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
