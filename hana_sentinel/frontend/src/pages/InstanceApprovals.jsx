import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { getInstanceStatus } from '../services/instanceApi';
import HealingApprovalDialog from '../components/HealingApprovalDialog';

const InstanceApprovals = () => {
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [loading, setLoading] = useState(false);

  const { status: wsStatus, data: wsData } = useWebSocket('/ws/instance-status');

  // Load initial data
  useEffect(() => {
    loadApprovals();
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (wsData) {
      console.log('WebSocket message:', wsData);

      if (wsData.type === 'approval_required') {
        // New approval request
        loadApprovals();
      } else if (wsData.type === 'healing_approved' || wsData.type === 'healing_rejected') {
        // Approval status changed
        loadApprovals();
      }
    }
  }, [wsData]);

  const loadApprovals = async () => {
    try {
      // In a real implementation, this would fetch pending approvals
      // For now, we'll show a placeholder
      // const status = await getInstanceStatus();
      // setPendingApprovals(status.pending_approvals);
    } catch (err) {
      console.error('Failed to load approvals:', err);
    }
  };

  const handleViewDetails = (approval) => {
    setSelectedApproval(approval);
  };

  const handleCloseDialog = () => {
    setSelectedApproval(null);
    loadApprovals();
  };

  const getScriptInfo = (scriptName) => {
    const scripts = {
      'auto_db_userstoremanagement': {
        name: 'Userstore Management',
        risk: 'MEDIUM',
        riskScore: 6,
        color: 'yellow',
        description: 'Fix HANA userstore connectivity issues'
      },
      'auto_db_metadata': {
        name: 'Database Metadata',
        risk: 'MEDIUM-HIGH',
        riskScore: 8,
        color: 'orange',
        description: 'Fix backup paths, trace permissions, DB parameters'
      },
      'auto_db_dbintegrations': {
        name: 'DB Integrations',
        risk: 'HIGH',
        riskScore: 12,
        color: 'red',
        description: 'Fix OS-level settings (swappiness, THP, ASLR)'
      },
      'auto_db_eligibility': {
        name: 'DB Eligibility',
        risk: 'MEDIUM',
        riskScore: 6,
        color: 'yellow',
        description: 'Validate and fix database eligibility criteria'
      }
    };

    return scripts[scriptName] || {
      name: scriptName,
      risk: 'UNKNOWN',
      riskScore: 0,
      color: 'gray',
      description: 'Unknown healing script'
    };
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-3">
            <span className="h-px flex-1 max-w-[60px] bg-border"></span>
            <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
              Instance Healing
            </span>
          </div>
          <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
            Healing Approvals
          </h1>
          <p className="text-muted-foreground mt-2">
            Review and approve healing script executions for the active instance
          </p>
        </div>

        {/* WebSocket Status */}
        <div className="mb-6 flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            wsStatus === 'connected' ? 'bg-success-500 animate-pulse' :
            wsStatus === 'error' ? 'bg-danger-500' : 'bg-warning-500'
          }`} />
          <span className="text-sm text-muted-foreground">
            {wsStatus === 'connected' ? 'Real-time updates enabled' :
             wsStatus === 'error' ? 'Connection Error' : 'Connecting...'}
          </span>
        </div>

        {/* Pending Approvals */}
        {pendingApprovals.length === 0 ? (
          <div className="text-center py-20 bg-card rounded-lg shadow-soft border border-border">
            <div className="w-16 h-16 bg-muted rounded-lg mx-auto mb-6 flex items-center justify-center">
              <svg className="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="font-serif text-xl font-semibold text-foreground mb-2">No Pending Approvals</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              All healing scripts are either approved or no issues detected.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {pendingApprovals.map((approval) => {
              const scriptInfo = getScriptInfo(approval.script_name);

              return (
                <div
                  key={approval.certificate_id}
                  className="bg-card rounded-lg shadow-soft border border-border p-6 hover:shadow-medium transition-all duration-200"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-serif text-xl font-semibold text-foreground">
                          {scriptInfo.name}
                        </h3>
                        <span className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                          scriptInfo.color === 'red' ? 'bg-danger-50 text-danger-600 border-danger-500/20' :
                          scriptInfo.color === 'orange' ? 'bg-warning-50 text-warning-600 border-warning-500/20' :
                          scriptInfo.color === 'yellow' ? 'bg-warning-50/50 text-warning-600 border-warning-500/20' :
                          'bg-muted text-muted-foreground border-border'
                        }`}>
                          {scriptInfo.risk} RISK ({scriptInfo.riskScore} points)
                        </span>
                      </div>

                      <p className="text-muted-foreground mb-3">{scriptInfo.description}</p>

                      <div className="mb-3">
                        <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">Issue Detected</div>
                        <div className="text-sm text-foreground bg-muted/50 p-3 rounded-lg border border-border">
                          {approval.issue_description || 'Issue description not available'}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground font-mono">
                        <div>Cert: {approval.certificate_id.slice(0, 8)}</div>
                        <div>Requested: {new Date(approval.created_at).toLocaleString()}</div>
                      </div>
                    </div>

                    <div className="ml-6">
                      <button
                        onClick={() => handleViewDetails(approval)}
                        className="px-5 py-2.5 bg-accent hover:bg-accent-secondary text-accent-foreground rounded-lg font-medium shadow-accent hover:shadow-hard transition-all duration-200"
                      >
                        Review & Approve
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

      {/* Approval Dialog */}
      {selectedApproval && (
        <HealingApprovalDialog
          approval={selectedApproval}
          onClose={handleCloseDialog}
        />
      )}
      </div>
    </div>
  );
};

export default InstanceApprovals;
