import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Server, Activity, Database, AlertCircle, CheckCircle, PlayCircle, Camera, HardDrive, Clock, RotateCcw, Cpu, Zap, Users, Shield, Wifi, WifiOff, BarChart3, FileText, Bot } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';
import { metricsAPI } from '../services/api';
import {
  runInstanceDiagnostic,
  getLatestDiagnostic,
  getInstanceDiagnostic,
  getDiagnosticHistory,
  createInstanceSnapshot,
  listInstanceSnapshots,
  getInstanceStatus
} from '../services/instanceApi';

const InstanceMonitoring = () => {
  const [diagnosticData, setDiagnosticData] = useState(null);
  const [instanceStatus, setInstanceStatus] = useState({ instance_name: 'vlgdbzo3' });
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [healingCount, setHealingCount] = useState(0);
  const [diagnosticHistory, setDiagnosticHistory] = useState([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [services, setServices] = useState([]);
  const [agents, setAgents] = useState([]);
  const [activities, setActivities] = useState([]);

  const { status: wsStatus, data: wsData } = useWebSocket('/ws/instance-status');

  useEffect(() => {
    loadData();
    loadLiveData();
  }, []);

  // Poll live metrics every 5 seconds
  useEffect(() => {
    const interval = setInterval(loadLiveData, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (wsData?.type === 'diagnostic_completed') {
      loadLatestDiagnostic();
    }
  }, [wsData]);

  const loadData = async () => {
    try {
      const [status, diagnostic, snapshotData, history] = await Promise.all([
        getInstanceStatus().catch(() => null),
        getLatestDiagnostic().catch(() => null),
        listInstanceSnapshots().catch(() => null),
        getDiagnosticHistory().catch(() => null)
      ]);
      if (status) setInstanceStatus(status);
      if (diagnostic) setDiagnosticData(diagnostic);
      if (snapshotData?.snapshots) setSnapshots(snapshotData.snapshots);
      if (history?.diagnostics) setDiagnosticHistory(history.diagnostics);
    } catch (err) {
      console.error('Failed to load data:', err);
    }
  };

  const loadLatestDiagnostic = async () => {
    try {
      const diagnostic = await getLatestDiagnostic();
      setDiagnosticData(diagnostic);
    } catch (err) {
      console.error('Failed to load diagnostic:', err);
    }
  };

  const loadLiveData = async () => {
    try {
      const [metricsRes, healthRes, servicesRes, agentsRes, activitiesRes] = await Promise.all([
        metricsAPI.getRealtime().catch(() => null),
        metricsAPI.getHealth().catch(() => null),
        metricsAPI.getServices().catch(() => null),
        metricsAPI.list ? metricsAPI.list().catch(() => null) : null,
        metricsAPI.getActivities(10).catch(() => null),
      ]);
      if (metricsRes?.data) setMetrics(metricsRes.data);
      if (healthRes?.data) setHealthData(healthRes.data);
      if (servicesRes?.data?.services) setServices(servicesRes.data.services);
      // agents come from agentAPI
      if (agentsRes?.data?.agents) setAgents(agentsRes.data.agents);
      if (activitiesRes?.data?.activities) setActivities(activitiesRes.data.activities);
    } catch (err) {
      console.error('Failed to load live data:', err);
    }
    // Also try agents separately via the right API
    try {
      const agentsRes = await fetch('/api/v1/agents').then(r => r.json()).catch(() => null);
      if (agentsRes?.agents) setAgents(agentsRes.agents);
    } catch (_) {}
  };

  const handleRunDiagnostic = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runInstanceDiagnostic();
      setDiagnosticData(result.result);
      setSelectedHistoryId(null);
      // Show auto-generated healing proposals count
      if (result.healing_proposals && result.healing_proposals.length > 0) {
        setHealingCount(result.healing_proposals.length);
      } else {
        setHealingCount(0);
      }
      // Refresh status counts and history
      try {
        const [status, history] = await Promise.all([
          getInstanceStatus(),
          getDiagnosticHistory().catch(() => null)
        ]);
        setInstanceStatus(status);
        if (history?.diagnostics) setDiagnosticHistory(history.diagnostics);
      } catch (_) { /* ignore refresh failure */ }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to run diagnostic');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSnapshot = async () => {
    setLoading(true);
    setError(null);
    try {
      await createInstanceSnapshot();
      await loadData();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create snapshot');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHistory = async (diagnosticId) => {
    if (selectedHistoryId === diagnosticId) {
      // Click again to go back to latest
      setSelectedHistoryId(null);
      try {
        const diagnostic = await getLatestDiagnostic();
        setDiagnosticData(diagnostic);
      } catch (_) {}
      return;
    }
    setHistoryLoading(true);
    try {
      const diagnostic = await getInstanceDiagnostic(diagnosticId);
      setDiagnosticData(diagnostic);
      setSelectedHistoryId(diagnosticId);
    } catch (err) {
      setError('Failed to load diagnostic: ' + (err.message || diagnosticId));
    } finally {
      setHistoryLoading(false);
    }
  };

  const StatusBadge = ({ status }) => {
    const styles = {
      ok: 'bg-success-50 text-success-600 border-success-500/20',
      success: 'bg-success-50 text-success-600 border-success-500/20',
      warning: 'bg-warning-50 text-warning-600 border-warning-500/20',
      critical: 'bg-danger-50 text-danger-600 border-danger-500/20',
      info: 'bg-info-50 text-info-600 border-info-500/20'
    };

    return (
      <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border ${styles[status] || styles.info}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
        {status?.toUpperCase()}
      </span>
    );
  };

  const CheckItem = ({ check }) => {
    const getIcon = () => {
      if (check.severity === 'ok' || check.severity === 'success') {
        return <CheckCircle className="w-5 h-5 text-success-500" />;
      } else if (check.severity === 'warning') {
        return <AlertCircle className="w-5 h-5 text-warning-500" />;
      } else {
        return <AlertCircle className="w-5 h-5 text-danger-500" />;
      }
    };

    return (
      <div className="flex items-start gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors duration-200 border border-transparent hover:border-border">
        <div className="flex-shrink-0 p-2 rounded-lg bg-card border border-border shadow-soft">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-4 mb-1">
            <p className="text-sm font-semibold text-foreground tracking-wide">
              {check.check?.replace(/_/g, ' ').toUpperCase()}
            </p>
            <StatusBadge status={check.severity} />
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {check.message || check.error || 'Check completed'}
          </p>

          {/* Process list table */}
          {check.check === 'process_status' && check.processes && check.processes.length > 0 && (
            <div className="mt-3 rounded-md border border-border overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/80 text-muted-foreground">
                    <th className="px-3 py-1.5 text-left font-medium">Status</th>
                    <th className="px-3 py-1.5 text-left font-medium">Process</th>
                    <th className="px-3 py-1.5 text-left font-medium">Description</th>
                    <th className="px-3 py-1.5 text-left font-medium">State</th>
                    {check.processes[0]?.pid && <th className="px-3 py-1.5 text-left font-medium">PID</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {check.processes.map((proc, idx) => (
                    <tr key={idx} className="hover:bg-muted/30">
                      <td className="px-3 py-1.5">
                        <span className={`inline-flex items-center gap-1.5 font-semibold ${
                          proc.status === 'GREEN' ? 'text-success-500' :
                          proc.status === 'YELLOW' ? 'text-warning-500' :
                          proc.status === 'GRAY' ? 'text-muted-foreground' : 'text-danger-500'
                        }`}>
                          <span className={`w-2 h-2 rounded-full ${
                            proc.status === 'GREEN' ? 'bg-success-500' :
                            proc.status === 'YELLOW' ? 'bg-warning-500' :
                            proc.status === 'GRAY' ? 'bg-muted-foreground' : 'bg-danger-500'
                          }`}></span>
                          {proc.status}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 font-mono text-foreground">{proc.name}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">{proc.description}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">{proc.text_status}</td>
                      {proc.pid && <td className="px-3 py-1.5 font-mono text-muted-foreground">{proc.pid}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-3 bg-accent rounded-lg shadow-accent">
              <Server className="w-7 h-7 text-accent-foreground" />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <span className="font-mono text-[10px] font-medium uppercase tracking-widest text-accent">
                  Instance Monitoring
                </span>
              </div>
              <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
                {instanceStatus?.instance_name || import.meta.env.VITE_HANA_INSTANCE_NAME || 'Unknown Instance'}
              </h1>
              <div className="text-muted-foreground mt-1 flex items-center gap-3">
                <span>SAP HANA Instance</span>
                <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                  <span className={`w-2 h-2 rounded-full ${
                    wsStatus === 'connected' ? 'bg-success-500 animate-pulse' :
                    wsStatus === 'error' ? 'bg-danger-500' : 'bg-warning-500'
                  }`}></span>
                  {wsStatus === 'connected' ? 'Live' : wsStatus === 'error' ? 'Disconnected' : 'Connecting'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-4">
            <button
              onClick={handleRunDiagnostic}
              disabled={loading}
              className="px-6 py-3 bg-accent hover:bg-accent-secondary text-accent-foreground rounded-lg font-medium shadow-accent hover:shadow-hard disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 min-h-[44px]"
            >
              <PlayCircle className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Running...' : 'Run Diagnostics'}
            </button>

            <button
              onClick={handleCreateSnapshot}
              disabled={loading}
              className="px-6 py-3 bg-card border border-border hover:border-accent text-foreground hover:text-accent rounded-lg font-medium shadow-soft hover:shadow-medium disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 min-h-[44px]"
            >
              <Camera className="w-5 h-5" />
              Create Snapshot
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-8 p-4 bg-danger-50 border border-danger-500/20 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-danger-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-danger-600 font-medium">{error}</p>
          </div>
        )}

        {/* Auto-generated healing proposals notification */}
        {healingCount > 0 && (
          <div className="mb-8 p-4 bg-accent/5 border border-accent/20 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Activity className="w-4 h-4 text-accent" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {healingCount} healing proposal{healingCount > 1 ? 's' : ''} auto-generated
                </p>
                <p className="text-xs text-muted-foreground">
                  Diagnostics detected issues and created healing proposals with AI analysis
                </p>
              </div>
            </div>
            <Link
              to="/instance-approvals"
              className="px-4 py-2 bg-accent hover:bg-accent-secondary text-accent-foreground rounded-lg text-sm font-medium shadow-accent transition-all duration-200"
            >
              Review Approvals
            </Link>
          </div>
        )}

        {/* Stats Grid */}
        {instanceStatus && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
            <StatCard
              icon={Database}
              label="Instance"
              value={instanceStatus.instance_name || import.meta.env.VITE_HANA_INSTANCE_NAME || 'Unknown'}
              accent
            />
            <StatCard
              icon={Activity}
              label="Diagnostics"
              value={instanceStatus.diagnostics_count || 0}
            />
            <StatCard
              icon={AlertCircle}
              label="Pending"
              value={instanceStatus.pending_approvals || 0}
            />
            <StatCard
              icon={Camera}
              label="Snapshots"
              value={instanceStatus.snapshots_count || 0}
            />
          </div>
        )}

        {/* ─── Live System Metrics ─── */}
        {metrics && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-accent/10">
                  <BarChart3 className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <h2 className="font-serif text-xl font-semibold text-foreground">Live System Metrics</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">Auto-refreshing every 5s &middot; SID: {metrics.system_id || '—'}</p>
                </div>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                metrics.database_connected
                  ? 'bg-success-50 text-success-600 border-success-500/20'
                  : 'bg-danger-50 text-danger-600 border-danger-500/20'
              }`}>
                {metrics.database_connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {metrics.database_connected ? 'DB Connected' : 'DB Disconnected'}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <MetricMini label="CPU" value={metrics.cpu_usage} unit="%" warn={70} crit={85} icon={Cpu} />
              <MetricMini label="Memory" value={metrics.memory_usage} unit="%" warn={80} crit={92} icon={Database} />
              <MetricMini label="Disk" value={metrics.disk_usage} unit="%" warn={75} crit={90} icon={HardDrive} />
              <MetricMini label="Connections" value={metrics.active_connections} icon={Users} />
              <MetricMini label="TPS" value={metrics.transactions_per_sec} icon={Zap} />
              <MetricMini label="Cache Hit" value={metrics.cache_hit_ratio} unit="%" icon={BarChart3} />
            </div>
            {/* Secondary row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-border">
              <div className="text-center">
                <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Active Txns</p>
                <p className="font-serif text-lg font-semibold text-foreground">{metrics.active_transactions ?? '—'}</p>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Threads</p>
                <p className="font-serif text-lg font-semibold text-foreground">{metrics.active_threads ?? '—'}</p>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Blocking</p>
                <p className={`font-serif text-lg font-semibold ${(metrics.blocking_sessions || 0) > 0 ? 'text-danger-500' : 'text-foreground'}`}>{metrics.blocking_sessions ?? '—'}</p>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-1">Resp Time</p>
                <p className="font-serif text-lg font-semibold text-foreground">{metrics.response_time_ms != null ? `${metrics.response_time_ms}ms` : '—'}</p>
              </div>
            </div>
          </div>
        )}

        {/* ─── System Health ─── */}
        {healthData && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="p-2 rounded-lg bg-accent/10">
                <Shield className="w-5 h-5 text-accent" />
              </div>
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">System Health</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{healthData.timestamp ? new Date(healthData.timestamp).toLocaleString() : ''}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <HealthTile label="Overall" status={healthData.status === 'healthy' ? 'ok' : 'critical'} detail={healthData.status} />
              <HealthTile
                label="Database"
                status={healthData.database_connected ? 'ok' : 'critical'}
                detail={healthData.hana_connection?.status || '—'}
                sub={healthData.hana_connection?.host || ''}
              />
              <HealthTile
                label="Sapcontrol"
                status={healthData.sapcontrol?.status === 'ok' || healthData.sapcontrol?.status === 'success' ? 'ok' : healthData.sapcontrol?.status === 'warning' ? 'warning' : 'critical'}
                detail={healthData.sapcontrol?.status || '—'}
              />
              <HealthTile
                label="Agents"
                status="ok"
                detail={`${healthData.agents_registered || 0} registered`}
              />
            </div>
          </div>
        )}

        {/* ─── HANA Services ─── */}
        {services.length > 0 && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="p-2 rounded-lg bg-accent/10">
                <Server className="w-5 h-5 text-accent" />
              </div>
              <h2 className="font-serif text-xl font-semibold text-foreground">HANA Services</h2>
            </div>
            <div className="rounded-md border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/80 text-muted-foreground">
                    <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest">Service</th>
                    <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest">Status</th>
                    <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest">Port</th>
                    <th className="px-4 py-2 text-left font-mono text-[10px] uppercase tracking-widest">Memory</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {services.map((svc, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-2.5 font-mono text-foreground">{svc.name}</td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
                          svc.status === 'running' ? 'text-success-500' : 'text-danger-500'
                        }`}>
                          <span className={`w-2 h-2 rounded-full ${svc.status === 'running' ? 'bg-success-500' : 'bg-danger-500'}`}></span>
                          {svc.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-muted-foreground">{svc.port}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{svc.memory}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ─── Agent Fleet ─── */}
        {agents.length > 0 && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="p-2 rounded-lg bg-accent/10">
                <Bot className="w-5 h-5 text-accent" />
              </div>
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">Agent Fleet</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{agents.length} agents registered</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {agents.map((agent) => (
                <div key={agent.id} className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 border border-transparent hover:border-border transition-colors">
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${agent.status === 'available' ? 'bg-success-500' : 'bg-muted-foreground'}`}></span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{agent.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{agent.description}</p>
                  </div>
                  <span className={`px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded ${
                    agent.risk_tier === 'low' ? 'bg-success-50 text-success-600' :
                    agent.risk_tier === 'medium' ? 'bg-warning-50 text-warning-600' :
                    'bg-danger-50 text-danger-600'
                  }`}>{agent.risk_tier}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ─── Recent Activity ─── */}
        {activities.length > 0 && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="p-2 rounded-lg bg-accent/10">
                <FileText className="w-5 h-5 text-accent" />
              </div>
              <h2 className="font-serif text-xl font-semibold text-foreground">Recent Activity</h2>
            </div>
            <div className="space-y-2">
              {activities.map((act) => (
                <div key={act.id} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 border border-transparent hover:border-border transition-colors">
                  <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                    act.severity === 'warning' ? 'bg-warning-500' :
                    act.severity === 'error' || act.severity === 'critical' ? 'bg-danger-500' :
                    'bg-success-500'
                  }`}></span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground">{act.message}</p>
                    <div className="flex items-center gap-3 mt-0.5 text-[11px] text-muted-foreground">
                      <span>{act.timestamp ? new Date(act.timestamp).toLocaleString() : ''}</span>
                      {act.agent && <span className="font-mono">{act.agent}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Diagnostic History */}
        {diagnosticHistory.length > 1 && (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border mb-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-accent/10">
                <Clock className="w-5 h-5 text-accent" />
              </div>
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">Diagnostic History</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {diagnosticHistory.length} run{diagnosticHistory.length !== 1 ? 's' : ''} recorded
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {diagnosticHistory.map((entry, idx) => {
                const isSelected = selectedHistoryId === entry.diagnostic_id;
                const isLatest = idx === 0 && !selectedHistoryId;
                const isCurrent = isSelected || isLatest;
                const statusColor = {
                  ok: 'bg-success-500', warning: 'bg-warning-500', critical: 'bg-danger-500', info: 'bg-info-500'
                }[entry.overall_status] || 'bg-muted-foreground';

                return (
                  <button
                    key={entry.diagnostic_id}
                    onClick={() => handleSelectHistory(entry.diagnostic_id)}
                    disabled={historyLoading}
                    className={`w-full flex items-center gap-4 p-3 rounded-lg text-left transition-all duration-200 border ${
                      isCurrent
                        ? 'bg-accent/10 border-accent shadow-accent'
                        : 'bg-muted/30 border-transparent hover:bg-muted/60 hover:border-border'
                    } disabled:opacity-50`}
                  >
                    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusColor}`}></span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">
                          {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Unknown'}
                        </span>
                        {idx === 0 && (
                          <span className="px-1.5 py-0.5 bg-accent/20 text-accent text-[10px] font-semibold rounded uppercase tracking-wider">Latest</span>
                        )}
                        {isCurrent && (
                          <span className="px-1.5 py-0.5 bg-accent text-accent-foreground text-[10px] font-semibold rounded uppercase tracking-wider">Viewing</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
                        <span>{entry.check_count} checks</span>
                        {entry.issue_count > 0 && (
                          <span className="text-warning-600 font-medium">{entry.issue_count} issue{entry.issue_count !== 1 ? 's' : ''}</span>
                        )}
                        {entry.severity_counts?.critical > 0 && (
                          <span className="text-danger-600 font-medium">{entry.severity_counts.critical} critical</span>
                        )}
                        {entry.severity_counts?.warning > 0 && (
                          <span className="text-warning-600">{entry.severity_counts.warning} warning</span>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={entry.overall_status} />
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Diagnostic Results */}
        {diagnosticData ? (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border">
            <div className="flex items-center justify-between mb-6 pb-6 border-b border-border">
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">
                  {selectedHistoryId ? 'Historical Diagnostic' : 'Diagnostic Results'}
                </h2>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                  {diagnosticData.timestamp ? new Date(diagnosticData.timestamp).toLocaleString() : 'Just now'}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {selectedHistoryId && (
                  <button
                    onClick={() => { setSelectedHistoryId(null); loadLatestDiagnostic(); }}
                    className="px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/10 rounded-lg transition-colors"
                  >
                    ← Back to Latest
                  </button>
                )}
                <StatusBadge status={diagnosticData.overall_status} />
              </div>
            </div>

            <div className="space-y-3">
              {diagnosticData.checks && Object.values(diagnosticData.checks).map((check, idx) => (
                <CheckItem key={idx} check={check} />
              ))}
            </div>

            {diagnosticData.issues_detected?.length > 0 && (
              <div className="mt-6 p-4 bg-warning-50 border border-warning-500/20 rounded-lg">
                <h3 className="text-sm font-semibold text-warning-600 mb-3 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  Issues Detected
                </h3>
                <ul className="space-y-2">
                  {diagnosticData.issues_detected.map((issue, idx) => (
                    <li key={idx} className="text-sm text-warning-600 flex items-start gap-2">
                      <span className="text-warning-500 mt-1">•</span>
                      <span>{issue}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-20 bg-card rounded-lg shadow-soft border border-border">
            <div className="w-16 h-16 bg-muted rounded-lg mx-auto mb-6 flex items-center justify-center">
              <Activity className="w-8 h-8 text-accent" />
            </div>
            <h3 className="font-serif text-xl font-semibold text-foreground mb-2">No Diagnostic Data</h3>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              Run a diagnostic check to see the health status of your HANA instance
            </p>
            <button
              onClick={handleRunDiagnostic}
              disabled={loading}
              className="px-6 py-3 bg-accent hover:bg-accent-secondary text-accent-foreground rounded-lg font-medium shadow-accent hover:shadow-hard disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 min-h-[44px]"
            >
              {loading ? 'Running...' : 'Run First Diagnostic'}
            </button>
          </div>
        )}

        {/* Snapshots for Recovery */}
        <div className="bg-card rounded-lg p-6 shadow-soft border border-border mt-8">
          <div className="flex items-center justify-between mb-6 pb-6 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent/10">
                <HardDrive className="w-5 h-5 text-accent" />
              </div>
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">Snapshots for Recovery</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {snapshots.length} snapshot{snapshots.length !== 1 ? 's' : ''} available
                </p>
              </div>
            </div>
            <button
              onClick={handleCreateSnapshot}
              disabled={loading}
              className="px-4 py-2 bg-card border border-border hover:border-accent text-foreground hover:text-accent rounded-lg text-sm font-medium shadow-soft hover:shadow-medium disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2"
            >
              <Camera className="w-4 h-4" />
              New Snapshot
            </button>
          </div>

          {snapshots.length > 0 ? (
            <div className="space-y-3">
              {snapshots.map((snap, idx) => (
                <div key={idx} className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors duration-200 border border-transparent hover:border-border">
                  <div className="flex-shrink-0 p-2 rounded-lg bg-card border border-border shadow-soft">
                    {snap.status === 'READY' ? (
                      <CheckCircle className="w-5 h-5 text-success-500" />
                    ) : snap.status === 'CREATING' || snap.status === 'UPLOADING' ? (
                      <RotateCcw className="w-5 h-5 text-warning-500 animate-spin" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-danger-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground tracking-wide truncate">
                      {snap.name}
                    </p>
                    <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {snap.creation_time ? new Date(snap.creation_time).toLocaleString() : 'Unknown'}
                      </span>
                      {snap.disk_size_gb && (
                        <span className="flex items-center gap-1">
                          <HardDrive className="w-3 h-3" />
                          {snap.disk_size_gb} GB
                        </span>
                      )}
                    </div>
                    {snap.description && (
                      <p className="text-xs text-muted-foreground mt-1 truncate">{snap.description}</p>
                    )}
                  </div>
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                    snap.status === 'READY'
                      ? 'bg-success-50 text-success-600 border-success-500/20'
                      : snap.status === 'CREATING' || snap.status === 'UPLOADING'
                      ? 'bg-warning-50 text-warning-600 border-warning-500/20'
                      : 'bg-danger-50 text-danger-600 border-danger-500/20'
                  }`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                    {snap.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10">
              <div className="w-12 h-12 bg-muted rounded-lg mx-auto mb-4 flex items-center justify-center">
                <Camera className="w-6 h-6 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground text-sm">No snapshots yet. Create one for disaster recovery.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className={`bg-card rounded-lg p-6 shadow-soft border transition-all duration-200 hover:shadow-medium ${
      accent ? 'border-t-2 border-t-accent border-border' : 'border-border'
    }`}>
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${accent ? 'bg-accent/10' : 'bg-muted'}`}>
          <Icon className={`w-5 h-5 ${accent ? 'text-accent' : 'text-muted-foreground'}`} />
        </div>
        <span className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">{label}</span>
      </div>
      <p className="font-serif text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function MetricMini({ label, value, unit = '', warn, crit, icon: Icon }) {
  const v = value != null ? Number(value) : null;
  const color = v != null && crit && v >= crit ? 'text-danger-500'
    : v != null && warn && v >= warn ? 'text-warning-500'
    : 'text-foreground';
  const barColor = v != null && crit && v >= crit ? 'bg-danger-500'
    : v != null && warn && v >= warn ? 'bg-warning-500'
    : 'bg-accent';
  return (
    <div className="bg-muted/50 rounded-lg p-3 border border-transparent hover:border-border transition-colors">
      <div className="flex items-center gap-1.5 mb-1">
        {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground" />}
        <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <p className={`font-serif text-xl font-semibold ${color}`}>
        {v != null ? (Number.isInteger(v) ? v : v.toFixed(1)) : '—'}{v != null ? unit : ''}
      </p>
      {v != null && (warn || crit) && (
        <div className="mt-1.5 h-1.5 bg-muted rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${barColor} transition-all duration-500`} style={{ width: `${Math.min(v, 100)}%` }} />
        </div>
      )}
    </div>
  );
}

function HealthTile({ label, status, detail, sub }) {
  const styles = {
    ok: 'border-success-500/30 bg-success-50/50',
    warning: 'border-warning-500/30 bg-warning-50/50',
    critical: 'border-danger-500/30 bg-danger-50/50',
  };
  const dotColor = {
    ok: 'bg-success-500',
    warning: 'bg-warning-500',
    critical: 'bg-danger-500',
  };
  return (
    <div className={`rounded-lg p-4 border ${styles[status] || styles.ok}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full ${dotColor[status] || dotColor.ok}`}></span>
        <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <p className="text-sm font-semibold text-foreground capitalize">{detail}</p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{sub}</p>}
    </div>
  );
}

export default InstanceMonitoring;
