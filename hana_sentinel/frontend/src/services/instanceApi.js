import axios from 'axios';

const API_BASE_URL = '/api/v1';

// ============================================================================
// Instance Management API
// ============================================================================

/**
 * Run diagnostic check on target instance
 */
export const runInstanceDiagnostic = async (instanceName = import.meta.env.VITE_HANA_INSTANCE_NAME || null) => {
  const payload = instanceName ? { instance_name: instanceName } : {};
  const response = await axios.post(`${API_BASE_URL}/instance/diagnostics`, payload);
  return response.data;
};

/**
 * Get diagnostic results by ID
 */
export const getInstanceDiagnostic = async (diagnosticId) => {
  const response = await axios.get(`${API_BASE_URL}/instance/diagnostics/${diagnosticId}`);
  return response.data;
};

/**
 * Get latest diagnostic
 */
export const getLatestDiagnostic = async () => {
  const response = await axios.get(`${API_BASE_URL}/instance/diagnostics/latest`);
  return response.data;
};

/**
 * Create VM snapshot
 */
export const createInstanceSnapshot = async () => {
  const response = await axios.post(`${API_BASE_URL}/instance/snapshot`, {});
  return response.data;
};

/**
 * List all VM snapshots
 */
export const listInstanceSnapshots = async () => {
  const response = await axios.get(`${API_BASE_URL}/instance/snapshots`);
  return response.data;
};

/**
 * Propose healing script execution
 */
export const proposeInstanceHealing = async (diagnosticId, scriptName, issueDescription, parameters = {}) => {
  const response = await axios.post(`${API_BASE_URL}/instance/healing/propose`, {
    diagnostic_id: diagnosticId,
    script_name: scriptName,
    issue_description: issueDescription,
    parameters
  });
  return response.data;
};

/**
 * Approve healing script
 */
export const approveInstanceHealing = async (certificateId, approvedBy, notes = '') => {
  const response = await axios.post(`${API_BASE_URL}/instance/healing/${certificateId}/approve`, {
    approved_by: approvedBy,
    notes
  });
  return response.data;
};

/**
 * Reject healing script
 */
export const rejectInstanceHealing = async (certificateId, rejectedBy, notes = '') => {
  const response = await axios.post(`${API_BASE_URL}/instance/healing/${certificateId}/reject`, {
    approved_by: rejectedBy,
    notes
  });
  return response.data;
};

/**
 * Execute approved healing script
 */
export const executeInstanceHealing = async (certificateId) => {
  const response = await axios.post(`${API_BASE_URL}/instance/healing/${certificateId}/execute`, {});
  return response.data;
};

/**
 * Get instance status
 */
export const getInstanceStatus = async () => {
  const response = await axios.get(`${API_BASE_URL}/instance/status`);
  return response.data;
};

// Export existing API functions (add to existing api.js)
// This assumes api.js already exists with other functions
