import { useState, useEffect } from 'react'
import { Activity, AlertTriangle, CheckCircle, TrendingUp, Shield, Database, Clock, Server, Cpu, HardDrive } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { metricsAPI } from '../services/api'

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      const [metricsRes, historyRes] = await Promise.all([
        metricsAPI.getRealtime().catch(() => ({ data: {} })),
        metricsAPI.getHistory(12).catch(() => ({ data: { metrics: [] } }))
      ])

      setMetrics(metricsRes.data || {})
      setHistory(historyRes.data.metrics || [])
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-border border-t-accent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  const cpuUsage = metrics?.cpu_usage
  const memoryUsage = metrics?.memory_usage
  const diskUsage = metrics?.disk_usage
  const activeConnections = metrics?.active_connections
  const transactionsPerSec = metrics?.transactions_per_sec
  const activeTransactions = metrics?.active_transactions
  const isDbConnected = metrics?.database_connected

  const getHealthStatus = () => {
    if (!isDbConnected) return { label: 'Disconnected', color: 'danger' }
    if (cpuUsage == null || memoryUsage == null) return { label: 'No Data', color: 'warning' }
    if (cpuUsage > 90 || memoryUsage > 95) return { label: 'Critical', color: 'danger' }
    if (cpuUsage > 80 || memoryUsage > 85) return { label: 'Warning', color: 'warning' }
    return { label: 'Healthy', color: 'success' }
  }

  const healthStatus = getHealthStatus()

  const chartData = history.length > 0 ? history.map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    cpu: h.cpu_usage || 0,
    memory: h.memory_usage || 0
  })) : []

  const recentActivities = [
    ...(cpuUsage != null ? [{ title: `CPU Usage: ${cpuUsage.toFixed(1)}%`, severity: cpuUsage > 80 ? 'warning' : 'success', timestamp: 'Just now' }] : []),
    ...(memoryUsage != null ? [{ title: `Memory Usage: ${memoryUsage.toFixed(1)}%`, severity: memoryUsage > 85 ? 'warning' : 'success', timestamp: 'Just now' }] : []),
    ...(activeConnections != null ? [{ title: `Active Connections: ${activeConnections}`, severity: 'success', timestamp: '1 min ago' }] : []),
    ...(!isDbConnected ? [{ title: 'Database disconnected', severity: 'critical', timestamp: 'Just now' }] : []),
  ]

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-3">
            <span className="h-px flex-1 max-w-[60px] bg-border"></span>
            <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
              Operations Dashboard
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
                HANA Ops agent
              </h1>
              <div className="text-muted-foreground mt-2 flex items-center gap-3">
                <span>AI-Powered Operations Platform</span>
                <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-lg text-xs font-semibold ${
                  healthStatus.color === 'success' ? 'bg-success-50 text-success-600 border border-success-500/20' :
                  healthStatus.color === 'warning' ? 'bg-warning-50 text-warning-600 border border-warning-500/20' :
                  'bg-danger-50 text-danger-600 border border-danger-500/20'
                }`}>
                  <span className={`w-2 h-2 rounded-full animate-pulse ${
                    healthStatus.color === 'success' ? 'bg-success-500' :
                    healthStatus.color === 'warning' ? 'bg-warning-500' : 'bg-danger-500'
                  }`}></span>
                  {healthStatus.label}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <MetricCard
            icon={Cpu}
            title="CPU Usage"
            value={cpuUsage != null ? cpuUsage.toFixed(1) : '—'}
            unit={cpuUsage != null ? '%' : ''}
            subtitle={activeConnections != null ? `${activeConnections} active connections` : 'No data'}
            accent
          />
          <MetricCard
            icon={Database}
            title="Memory Usage"
            value={memoryUsage != null ? memoryUsage.toFixed(1) : '—'}
            unit={memoryUsage != null ? '%' : ''}
            subtitle={activeTransactions != null ? `${activeTransactions} active transactions` : (transactionsPerSec != null ? `${transactionsPerSec} TPS` : 'No data')}
          />
          <MetricCard
            icon={HardDrive}
            title="Disk Usage"
            value={diskUsage != null ? diskUsage.toFixed(1) : '—'}
            unit={diskUsage != null ? '%' : ''}
            subtitle={diskUsage != null ? `${(diskUsage * 8.5).toFixed(0)}GB used` : 'No data'}
          />
          <MetricCard
            icon={Activity}
            title="Transactions/sec"
            value={transactionsPerSec != null ? transactionsPerSec : '—'}
            unit={transactionsPerSec != null ? 'TPS' : ''}
            subtitle={activeTransactions != null ? `${activeTransactions} active` : 'No data'}
          />
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
          {/* Chart */}
          <div className="lg:col-span-2 bg-card rounded-lg p-6 shadow-soft border border-border">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-border">
              <div>
                <h2 className="font-serif text-lg font-semibold text-foreground">System Performance</h2>
                <p className="text-sm text-muted-foreground mt-1">Real-time monitoring</p>
              </div>
              <div className="flex gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-accent"></div>
                  <span className="text-muted-foreground">CPU</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-success-500"></div>
                  <span className="text-muted-foreground">Memory</span>
                </div>
              </div>
            </div>
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#B8860B" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#B8860B" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="memoryGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E8E4DF" opacity={0.4} />
                  <XAxis dataKey="time" stroke="#6B6B6B" style={{ fontSize: '12px' }} />
                  <YAxis stroke="#6B6B6B" style={{ fontSize: '12px' }} domain={[0, 100]} unit="%" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#FFFFFF',
                      border: '1px solid #E8E4DF',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(26,26,26,0.06)'
                    }}
                    formatter={(value) => [`${value}%`]}
                  />
                  <Area type="monotone" dataKey="cpu" stroke="#B8860B" strokeWidth={2} fill="url(#cpuGradient)" />
                  <Area type="monotone" dataKey="memory" stroke="#10B981" strokeWidth={2} fill="url(#memoryGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[280px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Activity className="w-10 h-10 mx-auto mb-3 text-border" />
                  <p className="text-sm">{isDbConnected ? 'No historical data available' : 'Database not connected'}</p>
                </div>
              </div>
            )}
          </div>

          {/* Activity Feed */}
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-border">
              <h2 className="font-serif text-lg font-semibold text-foreground">Activity</h2>
              <button className="text-sm font-medium text-accent hover:text-accent-secondary transition-colors">
                View all
              </button>
            </div>
            <ActivityFeed items={recentActivities} />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <QuickActionCard
            href="/instance-monitoring"
            icon={Server}
            title="Instance Monitoring"
            subtitle={metrics?.system_id ? `Check ${metrics.system_id} health` : 'Check instance health'}
            accent
          />
          <QuickActionCard
            href="/instance-approvals"
            icon={Shield}
            title="Pending Approvals"
            subtitle="Review healing actions"
          />
          
        </div>
      </div>
    </div>
  )
}

function MetricCard({ icon: Icon, title, value, unit, subtitle, accent }) {
  return (
    <div className={`bg-card rounded-lg p-6 shadow-soft border transition-all duration-200 hover:shadow-medium ${
      accent ? 'border-t-2 border-t-accent border-border' : 'border-border'
    }`}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${accent ? 'bg-accent/10' : 'bg-muted'}`}>
          <Icon className={`w-5 h-5 ${accent ? 'text-accent' : 'text-muted-foreground'}`} />
        </div>
        <span className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">{title}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="font-serif text-3xl font-semibold text-foreground">{value}</span>
        {unit && <span className="text-lg text-muted-foreground">{unit}</span>}
      </div>
      {subtitle && <p className="text-sm text-muted-foreground mt-2">{subtitle}</p>}
    </div>
  )
}

function ActivityFeed({ items }) {
  return (
    <div className="space-y-3">
      {items.length > 0 ? items.map((item, idx) => (
        <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
          <div className={`flex-shrink-0 p-1.5 rounded-lg ${
            item.severity === 'critical' ? 'bg-danger-50 text-danger-500' :
            item.severity === 'warning' ? 'bg-warning-50 text-warning-500' :
            'bg-success-50 text-success-500'
          }`}>
            {item.severity === 'critical' ? <AlertTriangle className="w-4 h-4" /> :
             item.severity === 'warning' ? <Activity className="w-4 h-4" /> :
             <CheckCircle className="w-4 h-4" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">{item.title}</p>
            <div className="flex items-center gap-1.5 mt-1 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              <span>{item.timestamp}</span>
            </div>
          </div>
        </div>
      )) : (
        <div className="text-center py-8">
          <Activity className="w-10 h-10 text-border mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No recent activity</p>
        </div>
      )}
    </div>
  )
}

function QuickActionCard({ href, icon: Icon, title, subtitle, accent }) {
  return (
    <a
      href={href}
      className={`group block bg-card rounded-lg p-6 shadow-soft border border-border hover:shadow-medium hover:border-accent transition-all duration-200 ${
        accent ? 'border-t-2 border-t-accent' : ''
      }`}
    >
      <div className={`p-3 rounded-lg inline-block mb-4 ${accent ? 'bg-accent text-accent-foreground' : 'bg-muted'}`}>
        <Icon className={`w-6 h-6 ${accent ? '' : 'text-foreground'}`} />
      </div>
      <h3 className="font-serif text-lg font-semibold text-foreground mb-1 group-hover:text-accent transition-colors">{title}</h3>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </a>
  )
}
