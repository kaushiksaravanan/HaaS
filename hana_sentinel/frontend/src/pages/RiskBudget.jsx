import { useState, useEffect } from 'react'
import { Shield, TrendingDown, TrendingUp, Activity } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts'
import { riskBudgetAPI, metricsAPI } from '../services/api'

const transactionHistory = [
  { id: 1, action: 'read_monitoring', agent: 'Health Agent', cost: 5, time: '14:30', status: 'success' },
  { id: 2, action: 'sql_analyze', agent: 'SQL Tuning Agent', cost: 10, time: '14:15', status: 'success' },
  { id: 3, action: 'backup_trigger', agent: 'Backup Agent', cost: 15, time: '13:45', status: 'success' },
  { id: 4, action: 'security_scan', agent: 'Security Agent', cost: 8, time: '12:20', status: 'success' },
  { id: 5, action: 'config_modify', agent: 'Capacity Agent', cost: 20, time: '11:30', status: 'approved' },
]

const budgetByAgent = [
  { agent: 'Health', consumed: 15, color: '#B8860B' },
  { agent: 'SQL', consumed: 10, color: '#D4A84B' },
  { agent: 'Backup', consumed: 15, color: '#10B981' },
  { agent: 'Security', consumed: 8, color: '#6B6B6B' },
  { agent: 'Capacity', consumed: 20, color: '#1A1A1A' },
  { agent: 'Recovery', consumed: 5, color: '#E8E4DF' },
]

export default function RiskBudget() {
  const [budgetData, setBudgetData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchBudgetData = async () => {
      try {
        // Get the real system_id from the realtime metrics endpoint
        let systemId = 'default'
        try {
          const metricsRes = await metricsAPI.getRealtime()
          systemId = metricsRes.data?.system_id || 'default'
        } catch { /* fall through */ }

        const budgetRes = await riskBudgetAPI.get(systemId)
        const budget = budgetRes.data

        setBudgetData({
          systemId: budget.system_id || systemId,
          effectiveBudget: budget.effective_budget || 100,
          currentPoints: budget.current_points || 100,
          consumedToday: budget.consumed_today || 0,
          utilizationPct: budget.utilization_pct || 0,
          governanceMode: budget.governance_mode || 'HOOTL',
          trustMultiplier: budget.trust_multiplier || 1.0,
        })
      } catch (err) {
        console.error('Failed to fetch budget data:', err)
        setBudgetData({
          systemId: 'Unknown',
          effectiveBudget: 100,
          currentPoints: 100,
          consumedToday: 0,
          utilizationPct: 0,
          governanceMode: 'HOOTL',
          trustMultiplier: 1.0,
        })
      } finally {
        setIsLoading(false)
      }
    }

    fetchBudgetData()
    const interval = setInterval(fetchBudgetData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (isLoading || !budgetData) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="text-center py-16 text-muted-foreground">Loading risk budget data...</div>
      </div>
    )
  }

  const utilizationColor =
    budgetData.utilizationPct > 80 ? 'text-danger-500' :
    budgetData.utilizationPct > 60 ? 'text-warning-500' :
    'text-success-500'

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <div>
            <div className="flex items-center gap-4 mb-3">
              <span className="h-px flex-1 max-w-[60px] bg-border"></span>
              <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
                Risk Management
              </span>
            </div>
            <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
              Risk Budget
            </h1>
            <p className="text-muted-foreground mt-2">Policy-driven autonomous operations budget</p>
          </div>
          <div className="text-right">
            <div className="font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground mb-1">
              Governance Mode
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-success-50 text-success-600 rounded-lg border border-success-500/20">
              <div className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></div>
              <span className="font-semibold">{budgetData.governanceMode}</span>
            </div>
          </div>
        </div>

        {/* Budget Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
          <BudgetCard
            title="Effective Budget"
            value={budgetData.effectiveBudget}
            subtitle={`Trust Multiplier: ${budgetData.trustMultiplier}x`}
            icon={Shield}
            accent
          />
          <BudgetCard
            title="Current Points"
            value={budgetData.currentPoints}
            subtitle="Available for operations"
            icon={Activity}
          />
          <BudgetCard
            title="Consumed Today"
            value={budgetData.consumedToday}
            subtitle={`${budgetData.utilizationPct}% utilization`}
            icon={TrendingDown}
          />
          <BudgetCard
            title="Utilization"
            value={`${budgetData.utilizationPct}%`}
            subtitle={budgetData.utilizationPct < 60 ? 'Healthy' : 'Monitor'}
            icon={TrendingUp}
            valueColor={utilizationColor}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
          {/* Budget Distribution */}
          <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
            <h3 className="font-serif text-lg font-semibold text-foreground mb-6">Budget Distribution by Agent</h3>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={budgetByAgent}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ agent, consumed }) => `${agent}: ${consumed}`}
                  outerRadius={100}
                  fill="#B8860B"
                  dataKey="consumed"
                  stroke="#FAFAF8"
                  strokeWidth={2}
                >
                  {budgetByAgent.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #E8E4DF',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(26,26,26,0.06)'
                  }}
                  labelStyle={{ color: '#1A1A1A', fontWeight: 600 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Daily Consumption Trend */}
          <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
            <h3 className="font-serif text-lg font-semibold text-foreground mb-6">Daily Consumption Trend</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={budgetByAgent}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E8E4DF" />
                <XAxis dataKey="agent" stroke="#6B6B6B" fontSize={12} />
                <YAxis stroke="#6B6B6B" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #E8E4DF',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(26,26,26,0.06)'
                  }}
                  labelStyle={{ color: '#1A1A1A', fontWeight: 600 }}
                />
                <Bar dataKey="consumed" fill="#B8860B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Transaction History */}
        <div className="bg-card border border-border rounded-lg p-6 shadow-soft mb-10">
          <h3 className="font-serif text-lg font-semibold text-foreground mb-6">Recent Transactions</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Time</th>
                  <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Agent</th>
                  <th className="text-left font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Action</th>
                  <th className="text-right font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Cost</th>
                  <th className="text-center font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest pb-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {transactionHistory.map((tx) => (
                  <tr key={tx.id} className="hover:bg-muted/50 transition-colors">
                    <td className="py-4 text-sm text-muted-foreground">{tx.time}</td>
                    <td className="py-4 text-sm font-medium text-foreground">{tx.agent}</td>
                    <td className="py-4 text-sm text-muted-foreground font-mono">{tx.action}</td>
                    <td className="py-4 text-sm font-semibold text-foreground text-right">-{tx.cost}</td>
                    <td className="py-4 text-center">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                        tx.status === 'success'
                          ? 'bg-success-50 text-success-600 border border-success-500/20'
                          : 'bg-warning-50 text-warning-600 border border-warning-500/20'
                      }`}>
                        {tx.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Policy Information */}
        <div className="bg-card border border-border rounded-lg p-6 shadow-soft">
          <h3 className="font-serif text-lg font-semibold text-foreground mb-6">Policy Rules</h3>
          <div className="space-y-3">
            <PolicyRule
              rule="Low-risk actions (≤10 points) are automatically approved"
              status="active"
            />
            <PolicyRule
              rule="Medium-risk actions (11-20 points) require supervisor review"
              status="active"
            />
            <PolicyRule
              rule="High-risk actions (>20 points) require human approval"
              status="active"
            />
            <PolicyRule
              rule="Trust multiplier increases with successful operations"
              status="active"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function BudgetCard({ title, value, subtitle, icon: Icon, accent, valueColor }) {
  return (
    <div className={`bg-card border rounded-lg p-6 shadow-soft transition-all duration-200 hover:shadow-medium ${
      accent ? 'border-t-2 border-t-accent border-border' : 'border-border'
    }`}>
      <div className="flex items-center justify-between mb-4">
        <Icon className={`w-5 h-5 ${accent ? 'text-accent' : 'text-muted-foreground'}`} />
      </div>
      <div className={`font-serif text-3xl font-semibold ${valueColor || 'text-foreground'}`}>{value}</div>
      <div className="text-sm font-medium text-foreground mt-2">{title}</div>
      <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>
    </div>
  )
}

function PolicyRule({ rule, status }) {
  return (
    <div className="flex items-start gap-3 p-4 bg-muted/50 rounded-lg border border-border/50">
      <div className="flex-shrink-0 mt-1">
        <div className={`w-2 h-2 rounded-full ${
          status === 'active' ? 'bg-success-500' : 'bg-muted-foreground'
        }`}></div>
      </div>
      <div className="flex-1">
        <div className="text-foreground text-sm leading-relaxed">{rule}</div>
      </div>
    </div>
  )
}
