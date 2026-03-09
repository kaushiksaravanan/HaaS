import React from 'react';
import { Link } from 'react-router-dom';

const InstanceDiagnosticCard = ({ diagnostic }) => {
  if (!diagnostic) return null;

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'ok':
        return 'text-green-600 bg-green-50';
      case 'warning':
        return 'text-yellow-600 bg-yellow-50';
      case 'critical':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'ok':
        return '✓';
      case 'warning':
        return '⚠';
      case 'critical':
        return '✗';
      default:
        return 'ℹ';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Diagnostic Report
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              ID: {diagnostic.diagnostic_id}
            </p>
            <p className="text-sm text-gray-600">
              {new Date(diagnostic.timestamp).toLocaleString()}
            </p>
          </div>

          <div className="text-right">
            <div className={`inline-block px-4 py-2 rounded-lg font-bold ${getSeverityColor(diagnostic.overall_status)}`}>
              {diagnostic.overall_status.toUpperCase()}
            </div>
            <div className="text-sm text-gray-600 mt-2">
              {diagnostic.issue_count} {diagnostic.issue_count === 1 ? 'issue' : 'issues'} detected
            </div>
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="p-6 border-b border-gray-200 bg-gray-50">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-600">Instance</div>
            <div className="font-semibold">{diagnostic.instance_name}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">SID</div>
            <div className="font-semibold">{diagnostic.sid}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Instance Number</div>
            <div className="font-semibold">{diagnostic.instance_number}</div>
          </div>
        </div>
      </div>

      {/* Issues Detected */}
      {diagnostic.issues_detected && diagnostic.issues_detected.length > 0 && (
        <div className="p-6 border-b border-gray-200 bg-red-50">
          <h3 className="text-lg font-semibold text-red-900 mb-3">Issues Detected</h3>
          <ul className="space-y-2">
            {diagnostic.issues_detected.map((issue, idx) => (
              <li key={idx} className="flex items-start gap-2 text-red-800">
                <span className="text-red-600 mt-0.5">•</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>

          {diagnostic.issues_detected.length > 0 && (
            <Link
              to="/instance-approvals"
              className="mt-4 inline-block px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Review Healing Options →
            </Link>
          )}
        </div>
      )}

      {/* Diagnostic Checks */}
      <div className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Diagnostic Checks</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(diagnostic.checks || {}).map(([checkName, checkResult]) => (
            <div
              key={checkName}
              className={`p-4 rounded-lg border-2 ${
                checkResult.severity === 'ok' ? 'border-green-200 bg-green-50' :
                checkResult.severity === 'warning' ? 'border-yellow-200 bg-yellow-50' :
                checkResult.severity === 'critical' ? 'border-red-200 bg-red-50' :
                'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold text-gray-900 capitalize">
                  {checkName.replace(/_/g, ' ')}
                </div>
                <div className={`text-2xl ${getSeverityColor(checkResult.severity)}`}>
                  {getSeverityIcon(checkResult.severity)}
                </div>
              </div>

              <div className="text-sm text-gray-700 space-y-1">
                {/* Process Status */}
                {checkName === 'process_status' && checkResult.processes && (
                  <div>
                    <div className="font-medium mb-1">
                      {checkResult.processes.length} processes
                    </div>
                    {checkResult.processes.map((proc, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs">
                        <span className={
                          proc.status === 'GREEN' ? 'text-green-600' :
                          proc.status === 'YELLOW' ? 'text-yellow-600' : 'text-red-600'
                        }>
                          {proc.status}
                        </span>
                        <span>{proc.name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Disk Usage */}
                {checkName === 'disk_usage' && checkResult.partitions && (
                  <div>
                    <div className="font-medium mb-1">Max Usage: {checkResult.max_usage}%</div>
                    {checkResult.partitions.slice(0, 3).map((part, idx) => (
                      <div key={idx} className="text-xs">
                        {part.mount_point}: {part.use_percent}% ({part.available} free)
                      </div>
                    ))}
                  </div>
                )}

                {/* Memory Usage */}
                {checkName === 'memory_usage' && checkResult.memory_info && (
                  <div>
                    <div className="font-medium mb-1">
                      Usage: {checkResult.usage_percent}%
                    </div>
                    <div className="text-xs">
                      Used: {checkResult.memory_info.used} / {checkResult.memory_info.total}
                    </div>
                  </div>
                )}

                {/* Userstore */}
                {checkName === 'userstore' && (
                  <div>
                    <div className="font-medium mb-1">
                      {checkResult.key_count} keys configured
                    </div>
                    {checkResult.missing_keys && checkResult.missing_keys.length > 0 && (
                      <div className="text-xs text-red-600">
                        Missing: {checkResult.missing_keys.join(', ')}
                      </div>
                    )}
                  </div>
                )}

                {/* Backup Status */}
                {checkName === 'backup_status' && checkResult.backup_info && (
                  <div>
                    <div className="font-medium mb-1">
                      Last: {checkResult.age_hours}h ago
                    </div>
                    <div className="text-xs">
                      Type: {checkResult.backup_info.type}
                    </div>
                    <div className="text-xs">
                      State: {checkResult.backup_info.state}
                    </div>
                  </div>
                )}

                {/* System Parameters */}
                {checkName === 'system_parameters' && checkResult.parameters && (
                  <div>
                    {Object.entries(checkResult.parameters).map(([param, data]) => (
                      <div key={param} className="text-xs flex items-center gap-2">
                        <span className={data.ok ? 'text-green-600' : 'text-red-600'}>
                          {data.ok ? '✓' : '✗'}
                        </span>
                        <span>{param}: {data.value}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Database Alerts */}
                {checkName === 'database_alerts' && (
                  <div>
                    <div className="font-medium mb-1">
                      {checkResult.alert_count} alerts
                    </div>
                  </div>
                )}

                {/* Generic Message */}
                {checkResult.message && (
                  <div className="text-xs">{checkResult.message}</div>
                )}

                {/* Error */}
                {checkResult.error && (
                  <div className="text-xs text-red-600">{checkResult.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default InstanceDiagnosticCard;
