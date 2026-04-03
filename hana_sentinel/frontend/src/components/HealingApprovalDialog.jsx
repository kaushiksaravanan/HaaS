import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import {
  approveInstanceHealing,
  rejectInstanceHealing,
  executeInstanceHealing
} from '../services/instanceApi';

const HealingApprovalDialog = ({ approval, onClose }) => {
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [approved, setApproved] = useState(false);
  const [executed, setExecuted] = useState(false);
  const [executionResult, setExecutionResult] = useState(null);
  const [error, setError] = useState(null);
  const [notes, setNotes] = useState('');
  const [approvedBy, setApprovedBy] = useState('');

  const isCommand = approval.proposal_type === 'restricted_command';
  const { data: wsData } = useWebSocket('/ws/instance-status');

  // Handle WebSocket messages
  useEffect(() => {
    if (wsData && wsData.data?.certificate_id === approval.certificate_id) {
      console.log('WebSocket update for approval:', wsData);

      if (wsData.type === 'healing_executing') {
        setExecuting(true);
      } else if (wsData.type === 'healing_completed') {
        setExecuting(false);
        setExecuted(true);
        setExecutionResult(wsData.data);
      } else if (wsData.type === 'healing_failed') {
        setExecuting(false);
        setError(wsData.data.error);
      }
    }
  }, [wsData, approval.certificate_id]);

  const handleApprove = async () => {
    if (!approvedBy.trim()) {
      setError('Please enter your name');
      return;
    }

    setApproving(true);
    setError(null);

    try {
      await approveInstanceHealing(approval.certificate_id, approvedBy, notes);
      setApproved(true);

      // Automatically execute after approval
      handleExecute();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to approve');
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!approvedBy.trim()) {
      setError('Please enter your name');
      return;
    }

    if (!notes.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }

    setRejecting(true);
    setError(null);

    try {
      await rejectInstanceHealing(approval.certificate_id, approvedBy, notes);
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to reject');
      setRejecting(false);
    }
  };

  const handleExecute = async () => {
    setExecuting(true);
    setError(null);

    try {
      const result = await executeInstanceHealing(approval.certificate_id);
      setExecutionResult(result);
      setExecuted(true);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to execute');
      setExecuting(false);
    } finally {
      setApproving(false);
    }
  };

  const scriptDetails = {
    'auto_db_userstoremanagement': {
      name: 'Userstore Management',
      changes: [
        'Reconfigure userstore keys (BKPMON, SAPDBCTRL, SYSTEM, TRANSPORT)',
        'Delete existing misconfigured keys',
        'Create new keys with correct configuration',
        'Test connectivity for each key'
      ],
      rollback: [
        'Keys can be manually reconfigured if needed',
        'Previous configuration can be restored from backup',
        'Low risk of data loss'
      ]
    },
    'auto_db_metadata': {
      name: 'Database Metadata',
      changes: [
        'Configure backup paths (basepath_databackup, basepath_logbackup)',
        'Fix trace directory permissions',
        'Reset database parameters to standard values',
        'Update global.ini configuration'
      ],
      rollback: [
        'Configuration changes can be reverted via ALTER SYSTEM',
        'File permissions can be manually restored',
        'Medium risk - requires HANA restart if issues occur'
      ]
    },
    'auto_db_dbintegrations': {
      name: 'DB Integrations (HIGH RISK)',
      changes: [
        'Set swappiness to 10',
        'Disable Transparent Huge Pages (THP)',
        'Disable ASLR (Address Space Layout Randomization)',
        'Configure user shell settings',
        'Set file permissions on HANA directories'
      ],
      rollback: [
        'System parameters can be reverted with sysctl',
        'May require system reboot to fully revert',
        'HIGH RISK - Test in non-production first if possible'
      ]
    },
    'auto_db_eligibility': {
      name: 'DB Eligibility',
      changes: [
        'Validate backup configuration',
        'Create/fix archive directories',
        'Verify system database configuration',
        'Check backup catalog integrity'
      ],
      rollback: [
        'Directory creation can be reverted manually',
        'Low risk - mostly validation operations',
        'Safe to execute'
      ]
    }
  };

  const details = scriptDetails[approval.script_name] || scriptDetails['auto_db_userstoremanagement'];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 sticky top-0 bg-white">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">
              {isCommand ? 'Restricted Command Approval' : 'Healing Script Approval'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Error Display */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
              {error}
            </div>
          )}

          {/* Success Message for Rejection */}
          {rejecting && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
              {isCommand ? 'Restricted command rejected.' : 'Healing script rejected.'}
            </div>
          )}

          {/* Execution Status */}
          {executing && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                <span className="text-blue-800 font-medium">{isCommand ? 'Executing command...' : 'Executing healing script...'}</span>
              </div>
            </div>
          )}

          {/* Execution Result */}
          {executed && executionResult && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="text-green-800 font-medium mb-2">
                {isCommand ? '✓ Command executed successfully' : '✓ Healing script executed successfully'}
              </div>
              <div className="text-sm text-green-700">
                {isCommand
                  ? (executionResult.execution_result?.output
                    ? <pre className="whitespace-pre-wrap font-mono text-xs mt-1 max-h-40 overflow-y-auto bg-green-100/50 rounded p-2">{executionResult.execution_result.output}</pre>
                    : `Exit code: ${executionResult.execution_result?.exit_code ?? 'N/A'}`)
                  : `Verification: ${executionResult.verification?.overall_status || 'pending'}`
                }
              </div>
            </div>
          )}

          {/* Script Details (healing) or Command Details (restricted) */}
          {isCommand ? (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Restricted Command</h3>
              <div className="font-mono text-sm text-red-700 bg-red-50 p-3 rounded-lg border border-red-200 break-all mb-3">
                $ {approval.command}
              </div>
              {approval.user_request && approval.user_request !== approval.command && (
                <div className="mb-3">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Original Request:</span>
                  <p className="text-gray-700 text-sm italic mt-1">&ldquo;{approval.user_request}&rdquo;</p>
                </div>
              )}
              {approval.source && (
                <p className="text-gray-500 text-xs">
                  Source: {approval.source} &bull; Requested: {new Date(approval.created_at + 'Z').toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </p>
              )}
            </div>
          ) : (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{details.name}</h3>
              <p className="text-gray-600">{approval.issue_description}</p>
            </div>
          )}

          {/* LLM Analysis (from AI enrichment) */}
          {approval.llm_analysis && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                AI Analysis
              </h4>
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-3 text-sm">
                {approval.llm_analysis.root_cause && (
                  <div>
                    <span className="font-medium text-purple-900">Root Cause:</span>
                    <span className="text-purple-800 ml-1">{approval.llm_analysis.root_cause}</span>
                  </div>
                )}
                {approval.llm_analysis.impact && (
                  <div>
                    <span className="font-medium text-purple-900">Impact if Not Fixed:</span>
                    <span className="text-purple-800 ml-1">{approval.llm_analysis.impact}</span>
                  </div>
                )}
                {approval.llm_analysis.risk_assessment && (
                  <div>
                    <span className="font-medium text-purple-900">Risk Assessment:</span>
                    <span className="text-purple-800 ml-1">{approval.llm_analysis.risk_assessment}</span>
                  </div>
                )}
                {approval.llm_analysis.estimated_downtime && (
                  <div>
                    <span className="font-medium text-purple-900">Estimated Downtime:</span>
                    <span className={`ml-1 font-semibold ${
                      approval.llm_analysis.estimated_downtime === 'None' ? 'text-green-700' :
                      approval.llm_analysis.estimated_downtime === 'Minimal' ? 'text-yellow-700' :
                      'text-red-700'
                    }`}>{approval.llm_analysis.estimated_downtime}</span>
                  </div>
                )}
                {approval.llm_analysis.expected_outcome && (
                  <div>
                    <span className="font-medium text-purple-900">Expected Outcome:</span>
                    <span className="text-purple-800 ml-1">{approval.llm_analysis.expected_outcome}</span>
                  </div>
                )}
                {approval.llm_analysis.healing_steps && Array.isArray(approval.llm_analysis.healing_steps) && approval.llm_analysis.healing_steps.length > 0 && (
                  <div>
                    <span className="font-medium text-purple-900">Healing Steps:</span>
                    <ol className="list-decimal list-inside text-purple-800 mt-1 space-y-1">
                      {approval.llm_analysis.healing_steps.map((step, i) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
                {approval.llm_analysis.sap_recommendation && (
                  <div>
                    <span className="font-medium text-purple-900">SAP Best Practice:</span>
                    <span className="text-purple-800 ml-1">{approval.llm_analysis.sap_recommendation}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Browser Verification */}
          {approval.browser_verification && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
                SAP Documentation Verification
              </h4>
              <div className={`rounded-lg p-4 text-sm border ${
                approval.browser_verification.verified
                  ? 'bg-green-50 border-green-200'
                  : 'bg-yellow-50 border-yellow-200'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {approval.browser_verification.verified ? (
                    <>
                      <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span className="font-medium text-green-800">Commands verified against SAP documentation</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span className="font-medium text-yellow-800">Browser verification pending or unavailable</span>
                    </>
                  )}
                </div>
                {approval.browser_verification.source_url && (
                  <div className="text-xs text-gray-500 mb-2">
                    Source:{' '}
                    <a href={approval.browser_verification.source_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {approval.browser_verification.source_url}
                    </a>
                  </div>
                )}
                {approval.browser_verification.sap_guidance && typeof approval.browser_verification.sap_guidance === 'string' && (
                  <div className="text-gray-700 whitespace-pre-wrap text-xs mt-2 max-h-40 overflow-y-auto">
                    {approval.browser_verification.sap_guidance.slice(0, 500)}
                  </div>
                )}
                {approval.browser_verification.error && !approval.browser_verification.verified && (
                  <div className="text-xs text-yellow-700 mt-1">{approval.browser_verification.error}</div>
                )}
              </div>
            </div>
          )}

          {/* SAP Notes */}
          {approval.sap_notes && Array.isArray(approval.sap_notes) && approval.sap_notes.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-2">Related SAP Notes:</h4>
              <div className="flex gap-2 flex-wrap">
                {approval.sap_notes.map((note) => (
                  <a
                    key={note}
                    href={`https://me.sap.com/notes/${note}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-sm font-mono text-blue-700 hover:bg-blue-100 transition-colors"
                  >
                    SAP Note {note}
                  </a>
                ))}
              </div>
            </div>
          )}

          {isCommand ? (
            <>
              {/* AI Purpose & Risk for restricted commands */}
              {approval.llm_analysis?.purpose && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Purpose</h4>
                  <p className="text-gray-700 text-sm">{approval.llm_analysis.purpose}</p>
                </div>
              )}
              {approval.llm_analysis?.safe_alternative && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Safe Alternative</h4>
                  <p className="text-gray-700 text-sm bg-green-50 border border-green-200 rounded-lg p-3">{approval.llm_analysis.safe_alternative}</p>
                </div>
              )}
              {approval.llm_analysis?.preconditions && (
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">Preconditions</h4>
                  <p className="text-gray-700 text-sm">{approval.llm_analysis.preconditions}</p>
                </div>
              )}
            </>
          ) : (
            <>
              {/* Expected Changes */}
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Expected Changes:</h4>
                <ul className="space-y-1">
                  {details.changes.map((change, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-gray-700">
                      <span className="text-blue-600 mt-1">•</span>
                      <span>{change}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Rollback Plan */}
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">Rollback Plan:</h4>
                <ul className="space-y-1">
                  {details.rollback.map((step, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-gray-700">
                      <span className="text-orange-600 mt-1">•</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {/* Approval Form */}
          {!approved && !executed && !rejecting && (
            <div className="space-y-4 border-t border-gray-200 pt-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Name (required)
                </label>
                <input
                  type="text"
                  value={approvedBy}
                  onChange={(e) => setApprovedBy(e.target.value)}
                  placeholder="Enter your name"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Notes (optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add any notes about this approval..."
                  rows={3}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!approved && !executed && !rejecting && (
          <div className="p-6 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
            <button
              onClick={handleReject}
              disabled={rejecting || approving}
              className="px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              Reject
            </button>

            <button
              onClick={handleApprove}
              disabled={approving || rejecting}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {approving ? 'Approving...' : 'Approve & Execute'}
            </button>
          </div>
        )}

        {/* Close Button (after execution) */}
        {(executed || rejecting) && (
          <div className="p-6 border-t border-gray-200 bg-gray-50">
            <button
              onClick={onClose}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default HealingApprovalDialog;
