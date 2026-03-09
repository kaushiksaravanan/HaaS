import { Outlet, Link, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { LayoutDashboard, GitBranch, MessageSquare, AlertTriangle, Shield, Activity, Server, CheckSquare, RefreshCw } from 'lucide-react'
import { metricsAPI } from '../services/api'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Instance Monitoring', href: '/instance-monitoring', icon: Server },
  { name: 'Instance Approvals', href: '/instance-approvals', icon: CheckSquare },
  { name: 'Agent Flow', href: '/agent-flow', icon: GitBranch },
  { name: 'Agent Chat', href: '/agent-chat', icon: MessageSquare },
  { name: 'Incidents', href: '/incidents', icon: AlertTriangle },
  { name: 'Risk Budget', href: '/risk-budget', icon: Shield },
  { name: 'Monitoring', href: '/monitoring', icon: Activity },
]

export default function Layout() {
  const location = useLocation()
  const [systemStatus, setSystemStatus] = useState({
    apiConnected: false,
    dbConnected: false,
    checking: true,
    systemId: null,
    instanceName: null,
    lastUpdated: null,
  })

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await metricsAPI.getRealtime()
        const data = response.data || {}

        setSystemStatus({
          apiConnected: true,
          dbConnected: data.database_connected ?? false,
          checking: false,
          systemId: data.system_id || null,
          instanceName: data.system_id || data.instance_name || null,
          lastUpdated: data.timestamp || new Date().toISOString(),
        })
      } catch (error) {
        // API is down
        setSystemStatus({
          apiConnected: false,
          dbConnected: false,
          checking: false,
          systemId: null,
          instanceName: null,
          lastUpdated: null,
        })
      }
    }

    checkStatus()
    const interval = setInterval(checkStatus, 10000) // Check every 10 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-72 bg-card border-r border-border flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 h-20 px-6 border-b border-border">
          <div className="p-2 bg-accent rounded-lg shadow-accent">
            <svg className="w-6 h-6 text-accent-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <h1 className="font-serif text-xl font-semibold text-foreground tracking-tight">
              HANA Sentinel
            </h1>
            <p className="font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              AI Operations
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`
                  group flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200
                  ${isActive
                    ? 'bg-accent text-accent-foreground shadow-accent'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? '' : 'opacity-70 group-hover:opacity-100'}`} />
                <span className="tracking-wide">{item.name}</span>
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 bg-accent-foreground rounded-full"></div>
                )}
              </Link>
            )
          })}
        </nav>

        {/* System Status */}
        <div className="p-4 border-t border-border">
          <div className="bg-muted rounded-lg p-4 border border-border">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                System Status
              </span>
              <span className={`flex items-center gap-1.5 text-xs font-medium ${
                systemStatus.checking ? 'text-warning-600' :
                systemStatus.apiConnected && systemStatus.dbConnected ? 'text-success-600' :
                systemStatus.apiConnected ? 'text-warning-600' : 'text-danger-600'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  systemStatus.checking ? 'bg-warning-500 animate-pulse' :
                  systemStatus.apiConnected && systemStatus.dbConnected ? 'bg-success-500 animate-pulse' :
                  systemStatus.apiConnected ? 'bg-warning-500' : 'bg-danger-500'
                }`}></div>
                {systemStatus.checking ? 'Checking...' :
                 systemStatus.apiConnected && systemStatus.dbConnected ? 'Online' :
                 systemStatus.apiConnected ? 'Degraded' : 'Offline'}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Database</span>
                <span className={`font-medium ${systemStatus.dbConnected ? 'text-foreground' : 'text-danger-600'}`}>
                  {systemStatus.dbConnected ? (systemStatus.systemId || 'Connected') : 'Disconnected'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Instance</span>
                <span className={`font-medium ${systemStatus.apiConnected ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {systemStatus.instanceName || 'Unknown'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">API</span>
                <span className={`font-medium ${systemStatus.apiConnected ? 'text-success-600' : 'text-danger-600'}`}>
                  {systemStatus.apiConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              {systemStatus.lastUpdated && (
                <div className="pt-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  Live • {new Date(systemStatus.lastUpdated).toLocaleTimeString()}
                </div>
              )}
              <button
                onClick={async () => {
                  setSystemStatus(prev => ({ ...prev, checking: true }))
                  try {
                    await metricsAPI.forceReconnect()
                    // Poll for result every 2s, up to 60s
                    for (let i = 0; i < 30; i++) {
                      await new Promise(r => setTimeout(r, 2000))
                      const res = await metricsAPI.forceReconnectStatus()
                      const d = res.data || {}
                      if (d.status !== 'in_progress') {
                        setSystemStatus({
                          apiConnected: true,
                          dbConnected: d.database_connected ?? false,
                          checking: false,
                          systemId: d.details?.database || d.details?.system_id || null,
                          instanceName: d.details?.host || null,
                          lastUpdated: d.timestamp || new Date().toISOString(),
                        })
                        return
                      }
                    }
                    setSystemStatus(prev => ({ ...prev, checking: false }))
                  } catch {
                    setSystemStatus(prev => ({ ...prev, checking: false }))
                  }
                }}
                disabled={systemStatus.checking}
                className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md border border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${systemStatus.checking ? 'animate-spin' : ''}`} />
                Force Reconnect
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="ml-72">
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
