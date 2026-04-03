import { useState, useEffect, useRef, useCallback } from 'react'
import { Globe, Lock, RefreshCw, MousePointer2, CheckCircle2, AlertCircle, Loader2, ExternalLink, Search, Type, ChevronRight, Brain, ChevronDown, ChevronUp } from 'lucide-react'

/**
 * PlaywrightBrowser - Manus-style browser automation view with real screenshots,
 * animated cursor, click ripple effects, blue edge glow, and action overlay bar.
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
  const [clickRipples, setClickRipples] = useState([])
  const [cursorTrail, setCursorTrail] = useState([])
  const [isClicking, setIsClicking] = useState(false)
  const [thoughts, setThoughts] = useState([])
  const [scratchpadOpen, setScratchpadOpen] = useState(true)

  const wsRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5
  const screenshotRef = useRef(null)
  const scratchpadEndRef = useRef(null)
  const statusRef = useRef(status)
  statusRef.current = status

  // WebSocket connection
  useEffect(() => {
    let cancelled = false
    const connect = () => {
      if (cancelled) return
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/browser-stream`

      try {
        wsRef.current = new WebSocket(wsUrl)

        wsRef.current.onopen = () => {
          setConnected(true)
          setStatus('starting')
          setError(null)
          reconnectAttempts.current = 0

          if (!query || !String(query).trim()) {
            const msg = 'Browser query is empty; cannot start browsing session.'
            setStatus('error')
            setError(msg)
            if (onError) onError(msg)
            wsRef.current.close()
            return
          }

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
          const isTerminal = statusRef.current === 'complete' || statusRef.current === 'error'
          if (!isTerminal && !cancelled && reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current++
            setStatus('connecting')
            setTimeout(connect, 1000 * reconnectAttempts.current)
            return
          }

          if (!isTerminal && !cancelled) {
            const msg = 'Browser stream closed before completion. Please retry.'
            setStatus('error')
            setError(msg)
            if (onError) onError(msg)
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
      cancelled = true
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [conversationId, query, isAutonomous])

  // Auto-scroll scratchpad to bottom on new thoughts
  useEffect(() => {
    if (scratchpadOpen && scratchpadEndRef.current) {
      scratchpadEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [thoughts, scratchpadOpen])

  // Spawn a click ripple at cursor position
  const spawnClickRipple = useCallback((x, y) => {
    const id = Date.now() + Math.random()
    setClickRipples(prev => [...prev, { id, x, y }])
    setIsClicking(true)
    setTimeout(() => setIsClicking(false), 150)
    // Auto-remove after animation
    setTimeout(() => {
      setClickRipples(prev => prev.filter(r => r.id !== id))
    }, 1500)
  }, [])

  // Track cursor trail (last 3 positions)
  const updateCursorTrail = useCallback((x, y) => {
    setCursorTrail(prev => [...prev.slice(-2), { x, y, id: Date.now() }])
  }, [])

  const handleBrowserMessage = (data) => {
    switch (data.type) {
      case 'status':
        setStatus(data.status)
        setCurrentAction(data.message || data.description || '')
        if (data.progress !== undefined) setProgress(data.progress)
        break

      case 'thought':
        // Agent scratchpad — step-by-step thoughts from browser-use
        setThoughts(prev => [...prev, {
          step: data.step,
          url: data.url || '',
          title: data.title || '',
          thinking: data.thinking || '',
          evaluation: data.evaluation || '',
          memory: data.memory || '',
          nextGoal: data.next_goal || '',
          actions: data.actions || [],
          timestamp: Date.now(),
        }])
        // Update page info from step data
        if (data.url) setCurrentUrl(data.url)
        if (data.title) setPageTitle(data.title)
        if (data.screenshot) setScreenshot(data.screenshot)
        if (data.next_goal) setCurrentAction(data.next_goal)
        // Collect visited pages as sources
        if (data.url && data.url !== 'about:blank') {
          setSources(prev => {
            if (prev.some(s => s.url === data.url)) return prev
            return [...prev, { url: data.url, title: data.title || data.url, status: 'ok', source: 'browser_use' }]
          })
        }
        // Update progress proportionally (max_steps=8, cap at 75%)
        setProgress(prev => Math.min(75, Math.max(prev, Math.round((data.step / 8) * 75))))
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
          updateCursorTrail(data.cursor_x, data.cursor_y)
          setCursorX(data.cursor_x)
          setCursorY(data.cursor_y)

          // Spawn click ripple for click actions
          if (data.action_type === 'click') {
            spawnClickRipple(data.cursor_x, data.cursor_y)
          }
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
        // Merge server sources with locally-tracked sources (from thoughts)
        setSources(prev => {
          const serverSources = data.sources || []
          const merged = [...prev]
          for (const s of serverSources) {
            if (!merged.some(m => m.url === s.url)) merged.push(s)
          }
          // Call onComplete with the merged sources
          if (onComplete) {
            onComplete({
              response: data.response,
              sources: merged,
              actionCount: data.action_count || merged.length,
              isPartial: data.is_partial || false,
            })
          }
          return merged
        })
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

  const isBrowsing = status === 'browsing' || status === 'starting' || status === 'synthesizing'

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
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isBrowsing ? 'animate-spin' : ''}`} />
          </div>
        </div>

        <div className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${
          status === 'complete' ? 'bg-green-500/20 text-green-300 border border-green-500/30' :
          status === 'error' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
          status === 'synthesizing' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
          'bg-purple-500/20 text-purple-300 border border-purple-500/30'
        }`}>
          {status === 'complete' ? 'DONE' :
           status === 'error' ? 'ERROR' :
           status === 'synthesizing' ? 'THINKING' : 'LIVE'}
        </div>
      </div>

      {/* Browser Content - Screenshot View */}
      <div className="relative" style={{ height: '400px' }}>
        {/* Screenshot Display with Blue Edge Glow */}
        <div
          ref={screenshotRef}
          className={`absolute inset-0 bg-slate-950 transition-shadow duration-500 ${
            isBrowsing ? 'browser-edge-glow' : ''
          }`}
        >
          {screenshot ? (
            <div className="relative w-full h-full">
              <img
                src={`data:image/jpeg;base64,${screenshot}`}
                alt="Browser screenshot"
                className="w-full h-full object-contain screenshot-fade"
              />

              {/* Cursor Trail Dots */}
              {cursorTrail.map((trail, i) => (
                <div
                  key={trail.id}
                  className="absolute pointer-events-none cursor-trail-dot"
                  style={{
                    left: `${(trail.x / 1280) * 100}%`,
                    top: `${(trail.y / 720) * 100}%`,
                    transform: 'translate(-50%, -50%)',
                    opacity: 0.3 + (i * 0.15),
                  }}
                >
                  <div className="w-2 h-2 bg-blue-400 rounded-full" />
                </div>
              ))}

              {/* Animated Cursor Overlay — Manus-style smooth easing */}
              <div
                className="absolute pointer-events-none cursor-smooth"
                style={{
                  left: `${cursorXPercent}%`,
                  top: `${cursorYPercent}%`,
                  transform: `translate(-50%, -50%) ${isClicking ? 'scale(0.85)' : 'scale(1)'}`,
                }}
              >
                <div className="relative">
                  {/* Cursor glow effect */}
                  <div className="absolute inset-0 w-8 h-8 bg-blue-500/30 rounded-full blur-md animate-pulse" style={{ transform: 'translate(-25%, -25%)' }} />
                  {/* Cursor icon */}
                  <MousePointer2 className="w-6 h-6 text-white drop-shadow-lg" style={{ filter: 'drop-shadow(0 0 6px rgba(0, 129, 242, 0.8))' }} />
                </div>
              </div>

              {/* Click Ripple Effects — Manus-style blue expanding circles */}
              {clickRipples.map(ripple => (
                <div
                  key={ripple.id}
                  className="absolute pointer-events-none click-ripple"
                  style={{
                    left: `${(ripple.x / 1280) * 100}%`,
                    top: `${(ripple.y / 720) * 100}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                {status === 'starting' || status === 'connecting' ? (
                  <>
                    <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-3" />
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

        {/* Interactive Elements Panel (collapsed by default, expandable) */}
        {elements.length > 0 && (
          <div className="absolute bottom-14 right-3 z-10">
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
                          ? 'bg-blue-500/30 text-blue-200 border border-blue-500/50'
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

        {/* Action Overlay Bar — Manus-style floating status at bottom */}
        <div className="absolute bottom-0 left-0 right-0 z-10">
          <div className={`px-4 py-2.5 flex items-center gap-3 backdrop-blur-md transition-colors duration-300 ${
            status === 'error' ? 'bg-red-900/80 border-t border-red-500/30' :
            status === 'complete' ? 'bg-green-900/80 border-t border-green-500/30' :
            status === 'synthesizing' ? 'bg-blue-900/80 border-t border-blue-500/30' :
            'bg-slate-900/80 border-t border-blue-500/20'
          }`}>
            {status === 'synthesizing' ? (
              <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            ) : isBrowsing ? (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
            ) : status === 'complete' ? (
              <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
            ) : status === 'error' ? (
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            ) : (
              <Search className="w-4 h-4 text-slate-400 flex-shrink-0" />
            )}
            <span className="text-white text-xs flex-1 truncate">{currentAction}</span>
            {targetElement && (
              <span className="text-blue-300 text-[10px] bg-blue-500/20 px-2 py-0.5 rounded">
                {getElementIcon(targetElement.element_type)} {targetElement.text}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Agent Scratchpad / Thoughts Panel */}
      {thoughts.length > 0 && (
        <div className="bg-slate-950 border-t border-slate-700">
          <button
            onClick={() => setScratchpadOpen(prev => !prev)}
            className="w-full px-4 py-2 flex items-center justify-between text-xs text-slate-300 hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Brain className="w-3.5 h-3.5 text-purple-400" />
              <span className="font-medium">Agent Scratchpad</span>
              <span className="text-slate-500">— {thoughts.length} step{thoughts.length !== 1 ? 's' : ''}</span>
            </div>
            {scratchpadOpen ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            )}
          </button>
          {scratchpadOpen && (
            <div className="max-h-52 overflow-y-auto px-4 pb-3 space-y-2 scrollbar-thin scrollbar-thumb-slate-700">
              {thoughts.map((t, idx) => (
                <div key={idx} className="rounded-lg bg-slate-900/80 border border-slate-800 p-3 text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-purple-400 font-semibold">Step {t.step}</span>
                    {t.url && (
                      <span className="text-slate-500 truncate max-w-[200px] font-mono">{t.url}</span>
                    )}
                  </div>
                  {t.evaluation && (
                    <div className="text-slate-400">
                      <span className="text-yellow-500/80 font-medium">Eval: </span>{t.evaluation}
                    </div>
                  )}
                  {t.thinking && (
                    <div className="text-slate-300">
                      <span className="text-blue-400/80 font-medium">Thinking: </span>{t.thinking}
                    </div>
                  )}
                  {t.memory && (
                    <div className="text-slate-400">
                      <span className="text-green-400/80 font-medium">Memory: </span>{t.memory}
                    </div>
                  )}
                  {t.nextGoal && (
                    <div className="text-slate-200">
                      <span className="text-purple-400/80 font-medium">Next: </span>{t.nextGoal}
                    </div>
                  )}
                  {t.actions.length > 0 && (
                    <div className="flex gap-1 flex-wrap pt-0.5">
                      {t.actions.map((a, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded text-[10px] font-mono">
                          {a}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div ref={scratchpadEndRef} />
            </div>
          )}
        </div>
      )}

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
