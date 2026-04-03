import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AgentFlow from './pages/AgentFlow'
import AgentChat from './pages/AgentChat'
import Monitoring from './pages/Monitoring'
import InstanceMonitoring from './pages/InstanceMonitoring'
import InstanceApprovals from './pages/InstanceApprovals'

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="agent-flow" element={<AgentFlow />} />
          <Route path="agent-chat" element={<AgentChat />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="instance-monitoring" element={<InstanceMonitoring />} />
          <Route path="instance-approvals" element={<InstanceApprovals />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
