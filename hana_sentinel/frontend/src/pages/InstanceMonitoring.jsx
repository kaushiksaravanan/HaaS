import React, { useState, useEffect } from 'react';
import { Server, Activity, Database, AlertCircle, CheckCircle, PlayCircle, Camera } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';
import {
  runInstanceDiagnostic,
  getLatestDiagnostic,
  createInstanceSnapshot,
  getInstanceStatus
} from '../services/instanceApi';

const InstanceMonitoring = () => {
  const [diagnosticData, setDiagnosticData] = useState(null);
  const [instanceStatus, setInstanceStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const { status: wsStatus, data: wsData } = useWebSocket('/ws/instance-status');

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (wsData?.type === 'diagnostic_completed') {
      loadLatestDiagnostic();
    }
  }, [wsData]);

  const loadData = async () => {
    try {
      const [status, diagnostic] = await Promise.all([
        getInstanceStatus().catch(() => null),
        getLatestDiagnostic().catch(() => null)
      ]);
      if (status) setInstanceStatus(status);
      if (diagnostic) setDiagnosticData(diagnostic);
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

  const handleRunDiagnostic = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runInstanceDiagnostic();
      setDiagnosticData(result.result);
      // Refresh status counts (but don't overwrite diagnosticData)
      try {
        const status = await getInstanceStatus();
        setInstanceStatus(status);
      } catch (_) { /* ignore status refresh failure */ }
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
        <div className="w-1.5 h-1.5 rounded-full bg-current"></div>
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
              <p className="text-muted-foreground mt-1 flex items-center gap-3">
                <span>SAP HANA Instance</span>
                <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                  <div className={`w-2 h-2 rounded-full ${
                    wsStatus === 'connected' ? 'bg-success-500 animate-pulse' :
                    wsStatus === 'error' ? 'bg-danger-500' : 'bg-warning-500'
                  }`}></div>
                  {wsStatus === 'connected' ? 'Live' : wsStatus === 'error' ? 'Disconnected' : 'Connecting'}
                </span>
              </p>
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

        {/* Diagnostic Results */}
        {diagnosticData ? (
          <div className="bg-card rounded-lg p-6 shadow-soft border border-border">
            <div className="flex items-center justify-between mb-6 pb-6 border-b border-border">
              <div>
                <h2 className="font-serif text-xl font-semibold text-foreground">Diagnostic Results</h2>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                  {diagnosticData.timestamp ? new Date(diagnosticData.timestamp).toLocaleString() : 'Just now'}
                </p>
              </div>
              <StatusBadge status={diagnosticData.overall_status} />
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

export default InstanceMonitoring;
