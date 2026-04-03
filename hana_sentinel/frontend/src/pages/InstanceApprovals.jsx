import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { instanceAPI } from '../services/api';
import HealingApprovalDialog from '../components/HealingApprovalDialog';

const InstanceApprovals = () => {
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all' | 'healing' | 'restricted_command'
  const [statusFilter, setStatusFilter] = useState('pending_approval'); // 'pending_approval' | 'executed' | 'rejected' | 'all'

  const { status: wsStatus, data: wsData } = useWebSocket('/ws/instance-status');

  // Load initial data
  useEffect(() => {
    loadApprovals();
    const interval = setInterval(loadApprovals, 10000);
    return () => clearInterval(interval);
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
      const res = await instanceAPI.getPendingApprovals();
      setPendingApprovals(res.data?.pending_approvals || []);
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

  const getCommandRiskInfo = (approval) => {
    const score = approval.risk_score || 9;
    if (score >= 12) return { risk: 'HIGH', color: 'red', riskScore: score };
    if (score >= 8) return { risk: 'MEDIUM-HIGH', color: 'orange', riskScore: score };
    if (score >= 5) return { risk: 'MEDIUM', color: 'yellow', riskScore: score };
    return { risk: 'LOW', color: 'green', riskScore: score };
  };

  const healingCount = pendingApprovals.filter(a => a.proposal_type !== 'restricted_command').length;
  const commandCount = pendingApprovals.filter(a => a.proposal_type === 'restricted_command').length;
  const pendingCount = pendingApprovals.filter(a => a.status === 'pending_approval').length;
  const executedCount = pendingApprovals.filter(a => a.status === 'executed' || a.status === 'approved').length;
  const rejectedCount = pendingApprovals.filter(a => a.status === 'rejected').length;

  const filteredApprovals = pendingApprovals
    .filter(a => {
      if (filter === 'restricted_command') return a.proposal_type === 'restricted_command';
      if (filter === 'healing') return a.proposal_type !== 'restricted_command';
      return true;
    })
    .filter(a => {
      if (statusFilter === 'pending_approval') return a.status === 'pending_approval';
      if (statusFilter === 'executed') return a.status === 'executed' || a.status === 'approved';
      if (statusFilter === 'rejected') return a.status === 'rejected';
      return true;
    });

  const formatDateTime = (isoStr) => {
    if (!isoStr) return 'Unknown';
    const d = new Date(isoStr + 'Z'); // UTC
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-3">
            <span className="h-px flex-1 max-w-[60px] bg-border"></span>
            <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
              Instance Approvals
            </span>
          </div>
          <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
            Healing &amp; Command Approvals
          </h1>
          <p className="text-muted-foreground mt-2">
            Review and approve healing scripts and restricted command executions for the active instance
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

        {/* Filter Tabs */}
        {pendingApprovals.length > 0 && (
          <div className="mb-6 flex items-center gap-2">
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-accent text-accent-foreground shadow-accent'
                  : 'bg-card text-muted-foreground border border-border hover:bg-muted'
              }`}
            >
              All ({pendingApprovals.length})
            </button>
            <button
              onClick={() => setFilter('restricted_command')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === 'restricted_command'
                  ? 'bg-danger-500 text-white shadow-accent'
                  : 'bg-card text-muted-foreground border border-border hover:bg-muted'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Restricted Commands ({commandCount})
              </span>
            </button>
            <button
              onClick={() => setFilter('healing')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === 'healing'
                  ? 'bg-accent text-accent-foreground shadow-accent'
                  : 'bg-card text-muted-foreground border border-border hover:bg-muted'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
                Healing Scripts ({healingCount})
              </span>
            </button>
          </div>
        )}

        {/* Status Filter */}
        {pendingApprovals.length > 0 && (
          <div className="mb-6 flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-mono uppercase tracking-widest mr-2">Status:</span>
            {[
              { key: 'pending_approval', label: 'Pending', count: pendingCount, color: 'warning' },
              { key: 'executed', label: 'Executed', count: executedCount, color: 'success' },
              { key: 'rejected', label: 'Rejected', count: rejectedCount, color: 'danger' },
              { key: 'all', label: 'All', count: pendingApprovals.length, color: 'accent' },
            ].map(({ key, label, count, color }) => (
              <button
                key={key}
                onClick={() => setStatusFilter(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  statusFilter === key
                    ? `bg-${color === 'accent' ? 'accent' : color + '-500'} text-white shadow-sm`
                    : 'bg-card text-muted-foreground border border-border hover:bg-muted'
                }`}
              >
                {label} ({count})
              </button>
            ))}
          </div>
        )}

        {/* Pending Approvals */}
        {filteredApprovals.length === 0 ? (
          <div className="text-center py-20 bg-card rounded-lg shadow-soft border border-border">
            <div className="w-16 h-16 bg-muted rounded-lg mx-auto mb-6 flex items-center justify-center">
              <svg className="w-8 h-8 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="font-serif text-xl font-semibold text-foreground mb-2">No Pending Approvals</h3>
            <p className="text-muted-foreground max-w-md mx-auto">
              {statusFilter === 'executed'
                ? 'No executed commands or healing scripts found.'
                : statusFilter === 'rejected'
                ? 'No rejected commands or healing scripts found.'
                : filter === 'restricted_command'
                ? 'No restricted commands awaiting approval.'
                : filter === 'healing'
                ? 'All healing scripts are either approved or no issues detected.'
                : 'All approvals are resolved. Restricted commands and healing scripts will appear here when blocked.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {filteredApprovals.map((approval) => {
              const isCommand = approval.proposal_type === 'restricted_command';
              const scriptInfo = isCommand ? null : getScriptInfo(approval.script_name);
              const cmdRisk = isCommand ? getCommandRiskInfo(approval) : null;
              const llm = approval.llm_analysis;
              const bv = approval.browser_verification;

              return (
                <div
                  key={approval.certificate_id}
                  className={`bg-card rounded-lg shadow-soft border p-6 hover:shadow-medium transition-all duration-200 ${
                    isCommand ? 'border-danger-500/30' : 'border-border'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {/* Type Badge */}
                        {isCommand ? (
                          <span className="px-2 py-1 rounded text-[10px] font-semibold bg-danger-50 text-danger-600 border border-danger-500/20 uppercase tracking-wider flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                            Restricted Command
                          </span>
                        ) : (
                          <span className="px-2 py-1 rounded text-[10px] font-semibold bg-accent/10 text-accent border border-accent/20 uppercase tracking-wider">
                            Healing Script
                          </span>
                        )}

                        <h3 className="font-serif text-xl font-semibold text-foreground">
                          {isCommand ? 'Command Approval Required' : scriptInfo.name}
                        </h3>

                        {/* Risk Badge */}
                        {(() => {
                          const riskInfo = isCommand ? cmdRisk : scriptInfo;
                          const color = riskInfo.color;
                          return (
                            <span className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                              color === 'red' ? 'bg-danger-50 text-danger-600 border-danger-500/20' :
                              color === 'orange' ? 'bg-warning-50 text-warning-600 border-warning-500/20' :
                              color === 'yellow' ? 'bg-warning-50/50 text-warning-600 border-warning-500/20' :
                              color === 'green' ? 'bg-success-50 text-success-600 border-success-500/20' :
                              'bg-muted text-muted-foreground border-border'
                            }`}>
                              {riskInfo.risk} RISK ({riskInfo.riskScore} pts)
                            </span>
                          );
                        })()}

                        {approval.auto_generated && (
                          <span className="px-2 py-1 rounded text-[10px] font-semibold bg-accent/10 text-accent border border-accent/20 uppercase tracking-wider">
                            Auto-generated
                          </span>
                        )}
                      </div>

                      {/* Command Display (restricted commands only) */}
                      {isCommand && approval.command && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">Blocked Command</div>
                          <div className="font-mono text-sm text-danger-600 bg-danger-50/50 p-3 rounded-lg border border-danger-500/20 break-all">
                            $ {approval.command}
                          </div>
                        </div>
                      )}

                      {/* Description */}
                      {!isCommand && <p className="text-muted-foreground mb-3">{scriptInfo.description}</p>}

                      {/* AI-generated purpose (restricted commands) */}
                      {isCommand && llm && llm.purpose && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">What This Command Does</div>
                          <div className="text-sm text-foreground bg-muted/50 p-3 rounded-lg border border-border">
                            {llm.purpose}
                          </div>
                        </div>
                      )}

                      {/* Issue Description (healing) */}
                      {!isCommand && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">Issue Detected</div>
                          <div className="text-sm text-foreground bg-muted/50 p-3 rounded-lg border border-border">
                            {approval.issue_description || 'Issue description not available'}
                          </div>
                        </div>
                      )}

                      {/* LLM Analysis */}
                      {llm && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">AI Analysis</div>
                          <div className="bg-accent/5 border border-accent/20 rounded-lg p-4 space-y-2 text-sm">
                            {llm.root_cause && (
                              <div><span className="font-semibold text-foreground">Root Cause:</span> <span className="text-muted-foreground">{llm.root_cause}</span></div>
                            )}
                            {llm.risk_assessment && (
                              <div><span className="font-semibold text-foreground">Risk:</span> <span className="text-muted-foreground">{llm.risk_assessment}</span></div>
                            )}
                            {llm.impact && (
                              <div><span className="font-semibold text-foreground">Impact:</span> <span className="text-muted-foreground">{llm.impact}</span></div>
                            )}
                            {llm.estimated_downtime && (
                              <div><span className="font-semibold text-foreground">Downtime:</span> <span className="text-muted-foreground">{llm.estimated_downtime}</span></div>
                            )}
                            {llm.expected_outcome && (
                              <div><span className="font-semibold text-foreground">Expected Outcome:</span> <span className="text-muted-foreground">{llm.expected_outcome}</span></div>
                            )}
                            {llm.safe_alternative && (
                              <div><span className="font-semibold text-foreground">Safer Alternative:</span> <span className="text-muted-foreground font-mono text-xs">{llm.safe_alternative}</span></div>
                            )}
                            {llm.preconditions && (Array.isArray(llm.preconditions) ? llm.preconditions.length > 0 : llm.preconditions) && (
                              <div>
                                <span className="font-semibold text-foreground">Preconditions:</span>
                                {Array.isArray(llm.preconditions) ? (
                                  <ul className="list-disc list-inside text-muted-foreground mt-1 space-y-0.5">
                                    {llm.preconditions.map((step, i) => <li key={i}>{step}</li>)}
                                  </ul>
                                ) : (
                                  <p className="text-muted-foreground mt-1">{llm.preconditions}</p>
                                )}
                              </div>
                            )}
                            {llm.healing_steps && Array.isArray(llm.healing_steps) && llm.healing_steps.length > 0 && (
                              <div>
                                <span className="font-semibold text-foreground">Steps:</span>
                                <ol className="list-decimal list-inside text-muted-foreground mt-1 space-y-0.5">
                                  {llm.healing_steps.map((step, i) => <li key={i}>{step}</li>)}
                                </ol>
                              </div>
                            )}
                            {llm.sap_recommendation && (
                              <div><span className="font-semibold text-foreground">SAP Recommendation:</span> <span className="text-muted-foreground">{llm.sap_recommendation}</span></div>
                            )}
                            {llm.raw_analysis && !llm.root_cause && !llm.purpose && (
                              <div className="text-muted-foreground whitespace-pre-wrap">{llm.raw_analysis}</div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Browser Verification */}
                      {bv && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">SAP Documentation Verification</div>
                          <div className={`rounded-lg p-3 text-sm border ${
                            bv.verified
                              ? 'bg-success-50 border-success-500/20 text-success-700'
                              : 'bg-warning-50/50 border-warning-500/20 text-warning-700'
                          }`}>
                            <div className="flex items-center gap-2 mb-1">
                              {bv.verified ? (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                              ) : (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                              )}
                              <span className="font-semibold">
                                {bv.verified ? 'Verified against SAP documentation' : 'Verification pending'}
                              </span>
                            </div>
                            {bv.source_url && (
                              <div className="text-xs opacity-75">
                                Source:{' '}
                                <a href={bv.source_url} target="_blank" rel="noopener noreferrer" className="underline hover:no-underline">
                                  {bv.source_url}
                                </a>
                              </div>
                            )}
                            {bv.sap_guidance && typeof bv.sap_guidance === 'string' && (
                              <div className="mt-2 text-xs opacity-90 line-clamp-3">{bv.sap_guidance.slice(0, 300)}</div>
                            )}
                            {bv.error && !bv.verified && (
                              <div className="text-xs opacity-75 mt-1">{bv.error}</div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* SAP Notes */}
                      {approval.sap_notes && Array.isArray(approval.sap_notes) && approval.sap_notes.length > 0 && (
                        <div className="mb-3 flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">SAP Notes:</span>
                          {approval.sap_notes.map((note) => (
                            <a
                              key={note}
                              href={`https://me.sap.com/notes/${note}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-2 py-0.5 rounded text-xs font-mono bg-muted text-accent hover:bg-accent/10 border border-border transition-colors"
                            >
                              {note}
                            </a>
                          ))}
                        </div>
                      )}

                      {/* User Request (what was typed in chat) */}
                      {isCommand && approval.user_request && approval.user_request !== approval.command && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">User Request</div>
                          <div className="text-sm text-foreground bg-muted/30 p-3 rounded-lg border border-border italic">
                            &ldquo;{approval.user_request}&rdquo;
                          </div>
                        </div>
                      )}

                      {/* Execution Output (for executed commands) */}
                      {isCommand && approval.execution_output && (approval.status === 'executed' || approval.status === 'approved') && (
                        <div className="mb-3">
                          <div className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest mb-1">Execution Output</div>
                          <pre className="text-xs text-success-700 bg-success-50/50 p-3 rounded-lg border border-success-500/20 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono">
                            {approval.execution_output}
                          </pre>
                        </div>
                      )}

                      <div className="flex items-center gap-4 text-xs text-muted-foreground font-mono flex-wrap">
                        {/* Status Badge */}
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                          approval.status === 'pending_approval' ? 'bg-warning-50 text-warning-600 border border-warning-500/20' :
                          approval.status === 'executed' || approval.status === 'approved' ? 'bg-success-50 text-success-600 border border-success-500/20' :
                          approval.status === 'rejected' ? 'bg-danger-50 text-danger-600 border border-danger-500/20' :
                          'bg-muted text-muted-foreground border border-border'
                        }`}>
                          {approval.status === 'pending_approval' ? 'Pending' : approval.status}
                        </span>
                        <div>Cert: {approval.certificate_id.slice(0, 8)}</div>
                        <div>Requested: {formatDateTime(approval.created_at)}</div>
                        {approval.executed_at && <div>Executed: {formatDateTime(approval.executed_at)}</div>}
                        {approval.approved_by && <div>By: {approval.approved_by}</div>}
                        {approval.source && <div>Source: {approval.source}</div>}
                      </div>
                    </div>

                    <div className="ml-6 flex flex-col gap-2">
                      {approval.status === 'pending_approval' ? (
                        <button
                          onClick={() => handleViewDetails(approval)}
                          className="px-5 py-2.5 bg-accent hover:bg-accent-secondary text-accent-foreground rounded-lg font-medium shadow-accent hover:shadow-hard transition-all duration-200"
                        >
                          Review &amp; Approve
                        </button>
                      ) : approval.status === 'executed' || approval.status === 'approved' ? (
                        <button
                          onClick={() => handleViewDetails(approval)}
                          className="px-5 py-2.5 bg-success-500/10 hover:bg-success-500/20 text-success-700 rounded-lg font-medium border border-success-500/20 transition-all duration-200"
                        >
                          View Result
                        </button>
                      ) : (
                        <button
                          onClick={() => handleViewDetails(approval)}
                          className="px-5 py-2.5 bg-muted hover:bg-muted/80 text-muted-foreground rounded-lg font-medium border border-border transition-all duration-200"
                        >
                          View Details
                        </button>
                      )}
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
