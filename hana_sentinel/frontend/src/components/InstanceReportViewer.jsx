import React, { useState, useEffect } from 'react';
import axios from 'axios';

const InstanceReportViewer = ({ reportId, onClose }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);

  useEffect(() => {
    if (reportId) {
      loadReport();
    }
  }, [reportId]);

  const loadReport = async () => {
    setLoading(true);
    setError(null);

    try {
      // Get report metadata
      const response = await axios.get(`/api/v1/instance/reports/${reportId}`);
      setReport(response.data);

      // Create PDF URL for iframe
      setPdfUrl(`/api/v1/instance/reports/${reportId}/download`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load report');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    window.open(`/api/v1/instance/reports/${reportId}/download`, '_blank');
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-lg shadow-2xl p-8">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="text-gray-800 font-medium">Loading report...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-lg shadow-2xl max-w-md w-full p-6">
          <div className="mb-4">
            <h2 className="text-xl font-bold text-red-900 mb-2">Error Loading Report</h2>
            <p className="text-red-700">{error}</p>
          </div>
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              Instance Report
            </h2>
            {report && (
              <p className="text-sm text-gray-600 mt-1">
                Generated: {new Date(report.timestamp).toLocaleString()}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download
            </button>

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

        {/* Report Summary */}
        {report && report.summary && (
          <div className="p-4 bg-gray-50 border-b border-gray-200">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-gray-600">Report Type</div>
                <div className="font-semibold text-gray-900">
                  {report.report_type || 'Instance Operation'}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Instance</div>
                <div className="font-semibold text-gray-900">
                  {report.instance_name || 'Unknown'}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Status</div>
                <div className={`font-semibold ${
                  report.status === 'success' ? 'text-green-600' :
                  report.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                }`}>
                  {report.status?.toUpperCase() || 'COMPLETED'}
                </div>
              </div>
            </div>

            {report.summary && (
              <div className="mt-3">
                <div className="text-sm text-gray-600 mb-1">Summary</div>
                <div className="text-sm text-gray-900">{report.summary}</div>
              </div>
            )}
          </div>
        )}

        {/* PDF Viewer */}
        <div className="flex-1 overflow-hidden">
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title="Instance Report PDF"
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-sm">Report not available</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <div>
              Report ID: {reportId}
            </div>
            {report && (
              <div>
                {report.page_count && `${report.page_count} pages • `}
                {report.file_size && `${(report.file_size / 1024).toFixed(1)} KB`}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default InstanceReportViewer;
