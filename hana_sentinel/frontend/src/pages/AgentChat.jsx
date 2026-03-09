import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader, AlertCircle, ShieldAlert, Globe, ExternalLink, Search, Sparkles, ArrowRight, CheckCircle2, Lock, RefreshCw, MousePointer2, FileText, Link2 } from 'lucide-react'
import { agentAPI } from '../services/api'
import ReactMarkdown from 'react-markdown'
import PlaywrightBrowser from '../components/PlaywrightBrowser'

// Simple Browser Window UI (fallback when not using Playwright)
function BrowserWindow({ isAutonomous, query }) {
  const [step, setStep] = useState(0)
  const [cursorPos, setCursorPos] = useState({ x: 50, y: 40 })

  const steps = isAutonomous
    ? [
        { url: 'about:blank', action: 'Launching Chromium...', icon: '🚀' },
        { url: 'https://www.google.com', action: 'Opening Google...', icon: '🌐' },
        { url: `https://www.google.com/search?q=${encodeURIComponent(query)}`, action: 'Searching...', icon: '🔍' },
        { url: 'https://help.sap.com/docs', action: 'Reading SAP Help...', icon: '📖' },
        { url: 'https://me.sap.com/notes', action: 'Checking SAP Notes...', icon: '📋' },
        { url: 'https://community.sap.com', action: 'Browsing community...', icon: '👥' },
        { url: 'https://help.sap.com/docs', action: 'Extracting content...', icon: '📄' },
        { url: 'complete', action: 'Synthesizing answer...', icon: '🧠' },
      ]
    : [
        { url: 'searxng://search', action: 'Querying SearXNG...', icon: '🔍' },
        { url: 'duckduckgo://search', action: 'Trying DuckDuckGo...', icon: '🦆' },
        { url: 'https://help.sap.com/docs', action: 'Fetching SAP docs...', icon: '📖' },
        { url: 'parsing://content', action: 'Parsing content...', icon: '📄' },
        { url: 'complete', action: 'Generating answer...', icon: '🧠' },
      ]

  const currentStep = steps[Math.min(step, steps.length - 1)]
  const progress = Math.min(((step + 1) / steps.length) * 100, 100)

  useEffect(() => {
    const interval = setInterval(() => {
      setStep(s => (s < steps.length - 1 ? s + 1 : s))
    }, 1200)
    return () => clearInterval(interval)
  }, [steps.length])

  // Animate cursor position for autonomous mode
  useEffect(() => {
    if (!isAutonomous) return
    const interval = setInterval(() => {
      setCursorPos({
        x: 20 + Math.random() * 60,
        y: 20 + Math.random() * 60,
      })
    }, 800)
    return () => clearInterval(interval)
  }, [isAutonomous])

  return (
    <div className={`w-full max-w-2xl rounded-xl overflow-hidden border shadow-2xl ${
      isAutonomous ? 'border-purple-500/40 browser-glow-purple' : 'border-blue-500/40 browser-glow'
    }`}>
      {/* macOS-style Window Chrome */}
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 px-4 py-2.5 flex items-center gap-3 border-b border-slate-700">
        {/* Traffic lights */}
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500/90 shadow-inner" />
          <div className="w-3 h-3 rounded-full bg-yellow-500/90 shadow-inner" />
          <div className="w-3 h-3 rounded-full bg-green-500/90 shadow-inner" />
        </div>

        {/* URL bar */}
        <div className="flex-1 mx-2">
          <div className="bg-slate-950/80 rounded-lg px-3 py-1.5 flex items-center gap-2 border border-slate-700">
            {currentStep.url.startsWith('https') ? (
              <Lock className="w-3 h-3 text-green-400 flex-shrink-0" />
            ) : (
              <Globe className="w-3 h-3 text-slate-500 flex-shrink-0" />
            )}
            <span className="text-xs text-slate-300 font-mono truncate flex-1">
              {currentStep.url}
            </span>
            <RefreshCw className={`w-3 h-3 text-slate-500 ${progress < 100 ? 'animate-spin' : ''}`} />
          </div>
        </div>

        {/* Mode badge */}
        <div className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
          isAutonomous
            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
        }`}>
          {isAutonomous ? 'AI BROWSER' : 'WEB SEARCH'}
        </div>
      </div>

      {/* Browser Viewport */}
      <div className="relative bg-white" style={{ height: '280px' }}>
        {/* Simulated page content */}
        <div className="absolute inset-0 p-4 overflow-hidden">
          {/* Fake search results / page skeleton */}
          <div className="space-y-3 animate-pulse">
            <div className="h-6 bg-slate-100 rounded w-3/4" />
            <div className="h-4 bg-slate-50 rounded w-full" />
            <div className="h-4 bg-slate-50 rounded w-5/6" />
            <div className="h-4 bg-slate-50 rounded w-4/6" />
            <div className="mt-4 h-5 bg-blue-50 rounded w-2/3" />
            <div className="h-4 bg-slate-50 rounded w-full" />
            <div className="h-4 bg-slate-50 rounded w-3/4" />
            <div className="mt-4 h-5 bg-blue-50 rounded w-1/2" />
            <div className="h-4 bg-slate-50 rounded w-5/6" />
          </div>

          {/* Highlight box showing where AI is "looking" */}
          {isAutonomous && step < steps.length - 1 && (
            <div
              className="absolute border-2 border-purple-400 rounded bg-purple-100/30 transition-all duration-500"
              style={{
                left: `${10 + (step % 3) * 20}%`,
                top: `${20 + (step % 4) * 15}%`,
                width: '120px',
                height: '40px',
              }}
            />
          )}
        </div>

        {/* AI Cursor for autonomous mode */}
        {isAutonomous && step < steps.length - 1 && (
          <div
            className="absolute transition-all duration-700 ease-out z-10"
            style={{ left: `${cursorPos.x}%`, top: `${cursorPos.y}%` }}
          >
            <MousePointer2 className="w-5 h-5 text-purple-600 drop-shadow-lg" style={{ transform: 'rotate(-15deg)' }} />
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-purple-500 rounded-full animate-ping" />
          </div>
        )}

        {/* Center action indicator */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className={`px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 ${
            isAutonomous ? 'bg-purple-600/90 text-white' : 'bg-blue-600/90 text-white'
          }`}>
            <span className="text-lg">{currentStep.icon}</span>
            <span className="text-sm font-medium">{currentStep.action}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-200">
          <div
            className={`h-full transition-all duration-500 ${
              isAutonomous ? 'bg-purple-500' : 'bg-blue-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Status bar */}
      <div className="bg-slate-900 px-4 py-2.5 border-t border-slate-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${
              progress < 100 ? 'bg-green-400 animate-pulse' : 'bg-blue-400'
            }`} />
            <span className="text-xs text-slate-400">{currentStep.action}</span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            {Math.round(progress)}% • Step {step + 1}/{steps.length}
          </span>
        </div>

        {/* Sources found */}
        {step > 2 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {['help.sap.com', 'me.sap.com', 'community.sap.com'].slice(0, step - 2).map((domain, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1 px-1.5 py-0.5 bg-slate-800 rounded text-[10px] text-slate-400"
              >
                <CheckCircle2 className="w-2.5 h-2.5 text-green-500" />
                {domain}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function AgentChat() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      role: 'assistant',
      content: `Welcome to HANA Sentinel. I can assist you with:

• **Run commands** — "run uptime", "execute df -h", "run sapcontrol -nr 00 -function GetProcessList"
• **System health** — "check health", "show status"
• **Diagnostics** — "run diagnostics"
• **Backups** — "check backup status"
• **SQL optimization** — Share a query for analysis
• **Web search** — Enable Browser mode to search SAP docs & Google

How may I assist you today?`,
      timestamp: new Date(),
    }
  ])
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
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

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
    if (!input.trim() || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    setError(null)

    // Auto-detect knowledge queries that should use browser
    const inputLower = input.toLowerCase()
    const isSapNoteQuery = /\b(?:sap\s*)?note\s*\d{5,7}\b|\b\d{6,7}\b/.test(inputLower)
    const isKnowledgeQuery = [
      'what is', 'how to', 'explain', 'search', 'look up', 'find',
      'sap note', 'documentation', 'browse'
    ].some(p => inputLower.includes(p))
    const shouldUseBrowser = autonomousBrowser || isSapNoteQuery || isKnowledgeQuery

    // Temporarily enable autonomous browser for this request if it's a knowledge query
    if (shouldUseBrowser && !autonomousBrowser) {
      setAutonomousBrowser(true)
    }

    try {
      const response = await agentAPI.chat(input, conversationId, {
        admin_mode: adminMode,
        use_browser: useBrowser || shouldUseBrowser,
        autonomous_browser: shouldUseBrowser,
      })

      const sources = response.data.sources || []

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response,
        sources,
        timestamp: new Date(),
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setError('Failed to get response from agent. Please try again.')
      console.error('Chat error:', err)
    } finally {
      setIsLoading(false)
    }
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
                {autonomousBrowser ? (
                  /* Full Playwright Browser with real screenshots and cursor tracking */
                  <PlaywrightBrowser
                    query={messages[messages.length - 1]?.content || 'searching...'}
                    conversationId={conversationId}
                    isAutonomous={true}
                    onComplete={(result) => {
                      // The API call will handle the response
                      console.log('Playwright browser completed:', result.actionCount, 'actions')
                    }}
                    onError={(error) => {
                      console.error('Playwright error:', error)
                    }}
                  />
                ) : (useBrowser) ? (
                  /* Simple Browser Window UI for web search mode */
                  <BrowserWindow
                    isAutonomous={false}
                    query={messages[messages.length - 1]?.content || 'searching...'}
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
                  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
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
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
