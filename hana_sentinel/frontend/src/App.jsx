import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AgentFlow from './pages/AgentFlow'
import AgentChat from './pages/AgentChat'
import Incidents from './pages/Incidents'
import RiskBudget from './pages/RiskBudget'
import Monitoring from './pages/Monitoring'
import InstanceMonitoring from './pages/InstanceMonitoring'
import InstanceApprovals from './pages/InstanceApprovals'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="agent-flow" element={<AgentFlow />} />
          <Route path="agent-chat" element={<AgentChat />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="risk-budget" element={<RiskBudget />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="instance-monitoring" element={<InstanceMonitoring />} />
          <Route path="instance-approvals" element={<InstanceApprovals />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
