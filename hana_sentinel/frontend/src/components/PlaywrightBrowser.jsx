import { useState, useEffect, useRef } from 'react'
import { Globe, Lock, RefreshCw, MousePointer2, CheckCircle2, AlertCircle, Loader2, ExternalLink, Search, Type, ChevronRight } from 'lucide-react'

/**
 * PlaywrightBrowser - Browser automation view with real screenshots and cursor tracking.
 * Shows live screenshots of what the AI agent sees with animated cursor.
 */
export default function PlaywrightBrowser({
  query,
  conversationId,
  onComplete,
  onError,
  isAutonomous = true,
}) {
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState('connecting')
  const [currentUrl, setCurrentUrl] = useState('about:blank')
  const [pageTitle, setPageTitle] = useState('')
  const [progress, setProgress] = useState(0)
  const [screenshot, setScreenshot] = useState(null)
  const [cursorX, setCursorX] = useState(640)
  const [cursorY, setCursorY] = useState(360)
  const [pageText, setPageText] = useState('')
  const [elements, setElements] = useState([])
  const [targetElement, setTargetElement] = useState(null)
  const [currentAction, setCurrentAction] = useState('Initializing...')
  const [actions, setActions] = useState([])
  const [sources, setSources] = useState([])
  const [error, setError] = useState(null)

  const wsRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3

  // WebSocket connection
  useEffect(() => {
    const connect = () => {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/browser-stream`

      try {
        wsRef.current = new WebSocket(wsUrl)

        wsRef.current.onopen = () => {
          setConnected(true)
          setStatus('starting')
          setError(null)
          reconnectAttempts.current = 0

          wsRef.current.send(JSON.stringify({
            conversation_id: conversationId,
            query: query,
            use_playwright: isAutonomous,
          }))
        }

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            handleBrowserMessage(data)
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        wsRef.current.onclose = () => {
          setConnected(false)
          if (status !== 'complete' && status !== 'error' && reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current++
            setTimeout(connect, 1000 * reconnectAttempts.current)
          }
        }

        wsRef.current.onerror = (e) => {
          console.error('WebSocket error:', e)
          setError('Connection error')
        }
      } catch (e) {
        console.error('Failed to create WebSocket:', e)
        setError('Failed to connect to browser stream')
      }
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [conversationId, query, isAutonomous])

  const handleBrowserMessage = (data) => {
    switch (data.type) {
      case 'status':
        setStatus(data.status)
        setCurrentAction(data.message || data.description || '')
        if (data.progress !== undefined) setProgress(data.progress)
        break

      case 'action':
        setStatus('browsing')
        setCurrentUrl(data.url || currentUrl)
        setPageTitle(data.page_title || '')
        setCurrentAction(data.description || data.action || '')
        if (data.progress !== undefined) setProgress(data.progress)

        // Update screenshot
        if (data.screenshot) {
          setScreenshot(data.screenshot)
        }

        // Update cursor position with smooth animation
        if (data.cursor_x !== undefined && data.cursor_y !== undefined) {
          setCursorX(data.cursor_x)
          setCursorY(data.cursor_y)
        }

        // Update page text
        if (data.page_text) {
          setPageText(data.page_text)
        }

        // Update interactive elements
        if (data.elements) {
          setElements(data.elements)
        }

        // Update target element (the one being clicked)
        if (data.target_element) {
          setTargetElement(data.target_element)
        } else {
          setTargetElement(null)
        }

        // Add to actions list
        setActions(prev => [...prev.slice(-9), {
          type: data.action_type,
          description: data.description || data.action,
          url: data.url,
          target: data.target_element?.text || data.target,
          success: data.success !== false,
          timestamp: Date.now(),
        }])
        break

      case 'complete':
        setStatus('complete')
        setProgress(100)
        setCurrentAction('Complete!')
        if (data.sources) setSources(data.sources)
        if (onComplete) {
          onComplete({
            response: data.response,
            sources: data.sources,
            actionCount: data.action_count,
          })
        }
        break

      case 'error':
        setStatus('error')
        setError(data.message || 'An error occurred')
        if (onError) onError(data.message)
        break

      default:
        if (data.url) setCurrentUrl(data.url)
        if (data.action) setCurrentAction(data.action)
        if (data.progress !== undefined) setProgress(data.progress)
        if (data.status) setStatus(data.status)
    }
  }

  // Get element type icon
  const getElementIcon = (type) => {
    switch (type) {
      case 'button': return '🔘'
      case 'link': return '🔗'
      case 'input': return '📝'
      default: return '•'
    }
  }

  // Calculate cursor position as percentage for the overlay
  const cursorXPercent = (cursorX / 1280) * 100
  const cursorYPercent = (cursorY / 720) * 100

  return (
    <div className="w-full max-w-4xl rounded-xl overflow-hidden border shadow-2xl bg-slate-900 browser-glow-purple">
      {/* macOS Window Chrome */}
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 px-4 py-3 flex items-center gap-3 border-b border-slate-700">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400" />
          <div className="w-3 h-3 rounded-full bg-yellow-500 hover:bg-yellow-400" />
          <div className="w-3 h-3 rounded-full bg-green-500 hover:bg-green-400" />
        </div>

        <div className="flex-1 mx-2">
          <div className="bg-slate-950/80 rounded-lg px-3 py-2 flex items-center gap-2 border border-slate-700">
            {currentUrl.startsWith('https') ? (
              <Lock className="w-3.5 h-3.5 text-green-400 flex-shrink-0" />
            ) : (
              <Globe className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
            )}
            <span className="text-sm text-slate-300 font-mono truncate flex-1">
              {currentUrl}
            </span>
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${status === 'browsing' ? 'animate-spin' : ''}`} />
          </div>
        </div>

        <div className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${
          status === 'complete' ? 'bg-green-500/20 text-green-300 border border-green-500/30' :
          status === 'error' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
          'bg-purple-500/20 text-purple-300 border border-purple-500/30'
        }`}>
          {status === 'complete' ? 'DONE' :
           status === 'error' ? 'ERROR' : 'LIVE'}
        </div>
      </div>

      {/* Browser Content - Screenshot View */}
      <div className="relative" style={{ height: '400px' }}>
        {/* Screenshot Display */}
        <div className="absolute inset-0 bg-slate-950">
          {screenshot ? (
            <div className="relative w-full h-full">
              <img
                src={`data:image/jpeg;base64,${screenshot}`}
                alt="Browser screenshot"
                className="w-full h-full object-contain screenshot-fade"
              />
              {/* Animated Cursor Overlay */}
              <div
                className="absolute pointer-events-none transition-all duration-300 ease-out"
                style={{
                  left: `${cursorXPercent}%`,
                  top: `${cursorYPercent}%`,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <div className="relative">
                  {/* Cursor glow effect */}
                  <div className="absolute inset-0 w-8 h-8 bg-purple-500/30 rounded-full blur-md animate-pulse" style={{ transform: 'translate(-25%, -25%)' }} />
                  {/* Cursor icon */}
                  <MousePointer2 className="w-6 h-6 text-purple-400 drop-shadow-lg" style={{ filter: 'drop-shadow(0 0 4px rgba(168, 85, 247, 0.8))' }} />
                </div>
              </div>
              {/* Click indicator when clicking */}
              {targetElement && (
                <div
                  className="absolute pointer-events-none"
                  style={{
                    left: `${cursorXPercent}%`,
                    top: `${cursorYPercent}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                >
                  <div className="w-12 h-12 border-2 border-amber-400 rounded-full animate-ping" />
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                {status === 'starting' || status === 'connecting' ? (
                  <>
                    <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-3" />
                    <div className="text-slate-400">Starting browser...</div>
                  </>
                ) : (
                  <>
                    <Globe className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <div className="text-slate-500">Waiting for screenshot...</div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Current Action Overlay */}
        <div className="absolute top-3 left-3 right-3">
          <div className={`px-3 py-2 rounded-lg flex items-center gap-2 backdrop-blur-sm ${
            status === 'error' ? 'bg-red-900/70 border border-red-500/30' :
            status === 'complete' ? 'bg-green-900/70 border border-green-500/30' :
            'bg-slate-900/70 border border-purple-500/30'
          }`}>
            {status === 'browsing' || status === 'starting' ? (
              <Loader2 className="w-4 h-4 text-purple-400 animate-spin flex-shrink-0" />
            ) : status === 'complete' ? (
              <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
            ) : status === 'error' ? (
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            ) : (
              <Search className="w-4 h-4 text-slate-400 flex-shrink-0" />
            )}
            <span className="text-white text-xs">{currentAction}</span>
          </div>
        </div>

        {/* Target Element Badge */}
        {targetElement && (
          <div className="absolute bottom-3 left-3">
            <div className="px-3 py-2 bg-amber-900/80 border border-amber-500/40 rounded-lg backdrop-blur-sm animate-pulse">
              <div className="flex items-center gap-2 text-amber-300 text-xs">
                <MousePointer2 className="w-4 h-4" />
                <span className="font-bold">Clicking:</span>
                <span className="bg-amber-500/20 px-2 py-0.5 rounded">
                  {getElementIcon(targetElement.element_type)} {targetElement.text}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Interactive Elements Panel (collapsed by default, expandable) */}
        {elements.length > 0 && (
          <div className="absolute bottom-3 right-3">
            <details className="group">
              <summary className="px-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg backdrop-blur-sm cursor-pointer list-none flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300">
                <Type className="w-3 h-3" />
                <span>{elements.length} elements</span>
                <ChevronRight className="w-3 h-3 group-open:rotate-90 transition-transform" />
              </summary>
              <div className="absolute bottom-full right-0 mb-2 w-56 max-h-48 overflow-y-auto bg-slate-900/95 border border-slate-700 rounded-lg backdrop-blur-sm p-2">
                <div className="space-y-1">
                  {elements.map((el, idx) => (
                    <div
                      key={idx}
                      className={`px-2 py-1 rounded text-[10px] flex items-center gap-2 ${
                        targetElement?.text === el.text
                          ? 'bg-amber-500/30 text-amber-200 border border-amber-500/50'
                          : 'bg-slate-800/50 text-slate-400'
                      }`}
                    >
                      <span>{getElementIcon(el.element_type)}</span>
                      <span className="truncate flex-1">{el.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </details>
          </div>
        )}
      </div>

      {/* Progress & Actions Bar */}
      <div className="bg-slate-900 border-t border-slate-700">
        {/* Progress bar */}
        <div className="h-1 bg-slate-800">
          <div
            className={`h-full transition-all duration-300 ${
              status === 'error' ? 'bg-red-500' :
              status === 'complete' ? 'bg-green-500' :
              'bg-purple-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-400' : 'bg-red-400'
              } ${status === 'browsing' ? 'animate-pulse' : ''}`} />
              <span className="text-xs text-slate-400">
                {pageTitle || currentUrl}
              </span>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">
              {progress}% • {actions.length} actions
            </span>
          </div>

          {/* Action History */}
          {actions.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {actions.slice(-6).map((action, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] action-badge ${
                    action.success
                      ? 'bg-slate-800 text-slate-400'
                      : 'bg-red-900/30 text-red-400'
                  }`}
                  title={action.description}
                >
                  {action.success ? (
                    <CheckCircle2 className="w-2.5 h-2.5 text-green-500" />
                  ) : (
                    <AlertCircle className="w-2.5 h-2.5 text-red-500" />
                  )}
                  <span className="font-medium">{action.type}:</span>
                  <span className="truncate max-w-[80px]">{action.target || 'page'}</span>
                </div>
              ))}
            </div>
          )}

          {/* Sources */}
          {sources.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-800">
              <div className="text-[10px] text-slate-500 mb-1">Sources found:</div>
              <div className="flex flex-wrap gap-1.5">
                {sources.map((source, idx) => (
                  <a
                    key={idx}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-2 py-0.5 bg-slate-800 hover:bg-slate-700 rounded text-[10px] text-slate-300 transition-colors"
                  >
                    <CheckCircle2 className="w-2.5 h-2.5 text-green-500" />
                    {new URL(source.url).hostname}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-2 p-2 bg-red-900/30 rounded text-xs text-red-300">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
