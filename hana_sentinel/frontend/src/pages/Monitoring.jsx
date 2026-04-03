import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, Database, HardDrive, Cpu, Clock, AlertTriangle, Zap, TrendingUp, TrendingDown } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { toast, Toaster } from 'react-hot-toast'
import { metricsAPI } from '../services/api'

export default function Monitoring() {
  const [refreshInterval, setRefreshInterval] = useState(5)
  const [metrics, setMetrics] = useState(null)
  const [prevMetrics, setPrevMetrics] = useState(null)
  const [performanceData, setPerformanceData] = useState([])
  const [systemServices, setSystemServices] = useState([])
  const [topQueries, setTopQueries] = useState([])

  // Fetch services and queries from backend
  useEffect(() => {
    const fetchStaticData = async () => {
      try {
        const [servicesRes, queriesRes] = await Promise.all([
          metricsAPI.getServices(),
          metricsAPI.getTopQueries(),
        ])
        if (servicesRes.data?.services) setSystemServices(servicesRes.data.services)
        if (queriesRes.data?.queries) setTopQueries(queriesRes.data.queries)
      } catch (err) {
        console.error('Failed to fetch services/queries:', err)
      }
    }
    fetchStaticData()
    const interval = setInterval(fetchStaticData, refreshInterval * 1000)
    return () => clearInterval(interval)
  }, [refreshInterval])

  // Real-time metric updates from backend API
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await metricsAPI.getRealtime()
        const data = response.data
        
        setPrevMetrics(metrics)
        
        const newMetrics = {
          cpuUsage: data.cpu_usage,
          memoryUsage: data.memory_usage,
          diskUsage: data.disk_usage,
          activeConnections: data.active_connections,
          transactionsPerSec: data.transactions_per_sec,
          responseTime: data.response_time_ms,
        }
        
        // Alert on high values
        if (metrics) {
          if (newMetrics.cpuUsage > 80 && metrics.cpuUsage <= 80) {
            toast.error('⚠️ CPU usage exceeded 80%!', { duration: 5000 })
          }
          if (newMetrics.memoryUsage > 90 && metrics.memoryUsage <= 90) {
            toast.error('⚠️ Memory usage critical!', { duration: 5000 })
          }
        }
        
        setMetrics(newMetrics)

        // Update performance chart
        const now = new Date()
        const timeStr = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')}`
        setPerformanceData(prev => {
          const newData = [...prev, { 
            time: timeStr, 
            cpu: Math.round(data.cpu_usage), 
            memory: Math.round(data.memory_usage), 
            connections: data.active_connections 
          }]
          return newData.slice(-10)
        })
      } catch (err) {
        console.error('Failed to fetch metrics:', err)
      }
    }
    
    fetchMetrics()
    const interval = setInterval(fetchMetrics, refreshInterval * 1000)
    return () => clearInterval(interval)
  }, [refreshInterval])

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10 space-y-8">
      <Toaster position="top-right" />
      
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <div className="flex items-center gap-4 mb-3">
            <span className="h-px flex-1 max-w-[60px] bg-border"></span>
            <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
              Real-Time Monitoring
            </span>
          </div>
          <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
            Live Metrics
          </h1>
          <p className="text-muted-foreground mt-2">System performance and resource tracking</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="bg-card border border-border text-foreground text-sm rounded-lg px-4 py-2.5 shadow-soft focus:outline-none focus:border-accent"
          >
            <option value={2}>Refresh: 2s</option>
            <option value={5}>Refresh: 5s</option>
            <option value={10}>Refresh: 10s</option>
          </select>
          <div className="flex items-center gap-2 px-4 py-2 bg-success-50 text-success-600 rounded-lg border border-success-500/20">
            <motion.span 
              className="w-2 h-2 bg-success-500 rounded-full"
              animate={{ scale: [1, 1.5, 1] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
            <span className="text-sm font-semibold">LIVE</span>
          </div>
        </div>
      </motion.div>

      {/* Real-time Metrics */}
      {metrics ? (
        <motion.div 
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <LiveMetricCard
          title="CPU Usage"
          value={Math.round(metrics.cpuUsage)}
          prevValue={prevMetrics ? Math.round(prevMetrics.cpuUsage) : undefined}
          icon={Cpu}
          color="text-blue-500"
          threshold={70}
          unit="%"
        />
        <LiveMetricCard
          title="Memory Usage"
          value={Math.round(metrics.memoryUsage)}
          prevValue={prevMetrics ? Math.round(prevMetrics.memoryUsage) : undefined}
          icon={Database}
          color="text-purple-500"
          threshold={85}
          unit="%"
        />
        <LiveMetricCard
          title="Disk Usage"
          value={Math.round(metrics.diskUsage)}
          prevValue={prevMetrics ? Math.round(prevMetrics.diskUsage) : undefined}
          icon={HardDrive}
          color="text-green-500"
          threshold={80}
          unit="%"
        />
        <LiveMetricCard
          title="Active Connections"
          value={metrics.activeConnections}
          prevValue={prevMetrics ? prevMetrics.activeConnections : undefined}
          icon={Activity}
          color="text-orange-500"
        />
        <LiveMetricCard
          title="Transactions/sec"
          value={metrics.transactionsPerSec}
          prevValue={prevMetrics ? prevMetrics.transactionsPerSec : undefined}
          icon={Zap}
          color="text-cyan-500"
        />
        <LiveMetricCard
          title="Response Time"
          value={metrics.responseTime}
          prevValue={prevMetrics ? prevMetrics.responseTime : undefined}
          icon={Clock}
          color="text-pink-500"
          unit="ms"
          threshold={200}
        />
      </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-6 shadow-soft animate-pulse">
              <div className="h-4 bg-muted rounded w-1/2 mb-4" />
              <div className="h-8 bg-muted rounded w-1/3 mb-2" />
              <div className="h-3 bg-muted rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {/* Performance Chart */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-card border border-border rounded-lg p-6 shadow-soft"
      >
        <h3 className="font-serif text-lg font-semibold text-foreground mb-4">Performance Trends (Live)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={performanceData}>
            <defs>
              <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
              </linearGradient>
              <linearGradient id="memoryGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.1}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E8E4DF" opacity={0.4} />
            <XAxis dataKey="time" stroke="#6B6B6B" style={{ fontSize: '12px' }} />
            <YAxis stroke="#6B6B6B" style={{ fontSize: '12px' }} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E8E4DF', borderRadius: '8px', boxShadow: '0 4px 12px rgba(26,26,26,0.06)' }}
              labelStyle={{ color: '#1A1A1A', fontWeight: 600 }}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="cpu" 
              stroke="#3b82f6" 
              strokeWidth={3}
              name="CPU %" 
              dot={{ fill: '#3b82f6', r: 4 }}
              activeDot={{ r: 6 }}
            />
            <Line 
              type="monotone" 
              dataKey="memory" 
              stroke="#8b5cf6" 
              strokeWidth={3}
              name="Memory %" 
              dot={{ fill: '#8b5cf6', r: 4 }}
              activeDot={{ r: 6 }}
            />
            <Line 
              type="monotone" 
              dataKey="connections" 
              stroke="#10b981" 
              strokeWidth={3}
              name="Connections" 
              dot={{ fill: '#10b981', r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </motion.div>

      {/* System Services */}
      <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
        <h3 className="font-serif text-lg font-semibold text-foreground mb-6">System Services</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Service</th>
                <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Status</th>
                <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Port</th>
                <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Memory</th>
                <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">CPU %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {systemServices.length > 0 ? systemServices.map((service, idx) => (
                <tr key={idx} className="hover:bg-muted/50 transition-colors">
                  <td className="py-3 text-sm text-foreground font-mono">{service.name}</td>
                  <td className="py-3">
                    <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium bg-success-50 text-success-600 border border-success-500/20">
                      {service.status}
                    </span>
                  </td>
                  <td className="py-3 text-sm text-muted-foreground">{service.port}</td>
                  <td className="py-3 text-sm text-muted-foreground">{service.memory}</td>
                  <td className="py-3 text-sm font-medium text-foreground">{service.cpu}%</td>
                </tr>
              )) : (
                <tr><td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">No service data available</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top Queries */}
      <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
        <h3 className="font-serif text-lg font-semibold text-foreground mb-6">Top Resource-Consuming Queries</h3>
        <div className="space-y-3">
          {topQueries.length > 0 ? topQueries.map((query) => (
            <QueryRow key={query.id} query={query} />
          )) : (
            <div className="py-8 text-center text-sm text-muted-foreground">No query data available</div>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}

function LiveMetricCard({ title, value, prevValue, icon: Icon, color, status, threshold, unit = '' }) {
  const change = prevValue !== undefined ? value - prevValue : 0
  const isWarning = threshold && value > threshold
  const displayColor = isWarning ? 'text-danger-500' : color
  
  return (
    <motion.div
      animate={{
        scale: change !== 0 ? [1, 1.02, 1] : 1,
        borderColor: isWarning ? ['#ef4444', '#f97316', '#ef4444'] : '#E8E4DF'
      }}
      transition={{ duration: 0.5 }}
      className="bg-card border-2 border-border rounded-lg p-6 shadow-soft relative overflow-hidden"
    >
      {change !== 0 && (
        <motion.div
          initial={{ scale: 0, opacity: 0.3 }}
          animate={{ scale: 3, opacity: 0 }}
          transition={{ duration: 1 }}
          className="absolute inset-0 bg-accent/10"
        />
      )}

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-3">
          <motion.div
            animate={{ rotate: change !== 0 ? [0, 10, -10, 0] : 0 }}
            transition={{ duration: 0.5 }}
          >
            <Icon className={`w-5 h-5 ${displayColor}`} />
          </motion.div>
          
          {change !== 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center space-x-1"
            >
              {change > 0 ? (
                <TrendingUp className="w-4 h-4 text-danger-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-success-500" />
              )}
              <span className={`text-xs ${change > 0 ? 'text-danger-500' : 'text-success-500'}`}>
                {change > 0 ? '+' : ''}{Math.abs(change).toFixed(1)}{unit}
              </span>
            </motion.div>
          )}

          <motion.span 
            animate={{ scale: [1, 1.2, 1], opacity: [1, 0.5, 1] }}
            transition={{ repeat: Infinity, duration: 2 }}
            className={`w-2 h-2 rounded-full ${
              isWarning ? 'bg-danger-500' : 'bg-success-500'
            }`}
          />
        </div>

        <motion.div
          key={value}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`font-serif text-3xl font-semibold ${displayColor}`}
        >
          {value}{unit}
        </motion.div>
        
        <div className="text-sm text-muted-foreground mt-2">{title}</div>

        {threshold && (
          <div className="mt-3">
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((value / threshold) * 100, 100)}%` }}
                transition={{ type: "spring", stiffness: 50 }}
                className={`h-full ${
                  isWarning 
                    ? 'bg-gradient-to-r from-danger-500 to-warning-500' 
                    : 'bg-gradient-to-r from-accent to-accent-secondary'
                }`}
              />
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function MetricCard({ title, value, icon: Icon, color, status }) {
  return (
    <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
      <div className="flex items-center justify-between mb-3">
        <Icon className={`w-5 h-5 ${color}`} />
        <span className={`w-2 h-2 rounded-full ${
          status === 'healthy' ? 'bg-success-500' :
          status === 'warning' ? 'bg-warning-500' :
          'bg-danger-500'
        }`}></span>
      </div>
      <div className="font-serif text-2xl font-semibold text-foreground">{value}</div>
      <div className="text-sm text-muted-foreground mt-1">{title}</div>
    </div>
  )
}

function QueryRow({ query }) {
  const durationColor = query.duration > 10 ? 'text-danger-500' : query.duration > 5 ? 'text-warning-500' : 'text-foreground'
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors duration-200 border border-transparent hover:border-border">
      <div className="flex-shrink-0 p-2 rounded-lg bg-card border border-border shadow-soft">
        <Database className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-mono text-foreground truncate" title={query.query}>
          {query.query}
        </p>
        <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
          <span className={`font-medium ${durationColor}`}>{query.duration}s</span>
          {query.memory_mb != null && <span>{query.memory_mb} MB</span>}
        </div>
      </div>
    </div>
  )
}


