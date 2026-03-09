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
              Healing Script Approval
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
              Healing script rejected.
            </div>
          )}

          {/* Execution Status */}
          {executing && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                <span className="text-blue-800 font-medium">Executing healing script...</span>
              </div>
            </div>
          )}

          {/* Execution Result */}
          {executed && executionResult && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="text-green-800 font-medium mb-2">✓ Healing script executed successfully</div>
              <div className="text-sm text-green-700">
                Verification: {executionResult.verification?.overall_status || 'pending'}
              </div>
            </div>
          )}

          {/* Script Details */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{details.name}</h3>
            <p className="text-gray-600">{approval.issue_description}</p>
          </div>

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
