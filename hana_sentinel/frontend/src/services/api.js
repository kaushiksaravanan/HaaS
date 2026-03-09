import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Incidents
export const incidentsAPI = {
  create: (data) => api.post('/incidents', data),
  get: (id) => api.get(`/incidents/${id}`),
  list: () => api.get('/incidents'),
  getTimeline: (id) => api.get(`/incidents/${id}/timeline`),
};

// Remediations
export const remediationsAPI = {
  propose: (incidentId, data) => api.post(`/incidents/${incidentId}/remediation`, data),
  approve: (certId, data) => api.post(`/remediations/${certId}/approve`, data),
  execute: (certId) => api.post(`/remediations/${certId}/execute`),
  rollback: (certId) => api.post(`/remediations/${certId}/rollback`),
};

// Risk Budget
export const riskBudgetAPI = {
  get: (systemId) => api.get(`/risk-budgets/${systemId}`),
  getTransactions: (systemId) => api.get(`/risk-budgets/${systemId}/transactions`),
};

// Tools
export const toolsAPI = {
  queryHANA: (sql) => api.post('/tools/hana-query', { sql }),
  checkConnection: () => api.get('/tools/hana-connection'),
  remoteExec: (command) => api.post('/tools/remote-exec', { command }),
  ragQuery: (question) => api.post('/tools/rag', { question }),
};

// Agent Chat
export const agentAPI = {
  chat: (message, conversationId, options = {}) =>
    api.post('/agent/chat', { message, conversation_id: conversationId, ...options }),
  getConversation: (conversationId) => api.get(`/agent/conversation/${conversationId}`),
  browse: (query) => api.post('/agent/browse', { query }),
};

// Metrics and Monitoring
export const metricsAPI = {
  getRealtime: () => api.get('/metrics/realtime'),
  forceReconnect: () => api.post('/force-reconnect'),
  forceReconnectStatus: () => api.get('/force-reconnect'),
  getHistory: (hours = 24) => api.get(`/metrics/history?hours=${hours}`),
  getActivities: (limit = 20) => api.get(`/activities/recent?limit=${limit}`),
  getHealth: () => api.get('/health'),
  getServices: () => api.get('/metrics/services'),
  getTopQueries: () => api.get('/metrics/top-queries'),
  getActiveTransactions: () => api.get('/metrics/active-transactions'),
};

// Instance Monitoring
export const instanceAPI = {
  // Diagnostics
  runDiagnostics: (instanceName) =>
    api.post('/instance/diagnostics', { instance_name: instanceName }),
  getDiagnostic: (diagnosticId) =>
    api.get(`/instance/diagnostics/${diagnosticId}`),
  getLatestDiagnostic: () =>
    api.get('/instance/diagnostics/latest'),

  // Snapshots
  createSnapshot: (description) =>
    api.post('/instance/snapshot', { description }),
  listSnapshots: () =>
    api.get('/instance/snapshots'),

  // Healing
  proposeHealing: (diagnosticId, issueType) =>
    api.post('/instance/healing/propose', { diagnostic_id: diagnosticId, issue_type: issueType }),
  approveHealing: (certificateId, approvedBy, notes) =>
    api.post(`/instance/healing/${certificateId}/approve`, { approved_by: approvedBy, notes }),
  rejectHealing: (certificateId, rejectedBy, reason) =>
    api.post(`/instance/healing/${certificateId}/reject`, { rejected_by: rejectedBy, reason }),
  executeHealing: (certificateId) =>
    api.post(`/instance/healing/${certificateId}/execute`),

  // Status
  getStatus: () =>
    api.get('/instance/status'),
};

export default api;
