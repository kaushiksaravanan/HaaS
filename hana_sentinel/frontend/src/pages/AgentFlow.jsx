import { useCallback, useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Zap, Activity, TrendingUp } from 'lucide-react'
import AgentNode from '../components/AgentNode'

const nodeTypes = {
  agentNode: AgentNode,
}

// Define the agent architecture
const initialNodes = [
  {
    id: 'supervisor',
    type: 'agentNode',
    position: { x: 400, y: 50 },
    data: { 
      label: 'Supervisor Agent',
      description: 'Orchestrates all agents & enforces policy',
      status: 'active',
      color: '#8b5cf6'
    },
  },
  {
    id: 'health',
    type: 'agentNode',
    position: { x: 100, y: 250 },
    data: { 
      label: 'Health Agent',
      description: 'Monitors system health metrics',
      status: 'active',
      color: '#10b981'
    },
  },
  {
    id: 'backup',
    type: 'agentNode',
    position: { x: 300, y: 250 },
    data: { 
      label: 'Backup Agent',
      description: 'Manages backup operations',
      status: 'active',
      color: '#3b82f6'
    },
  },
  {
    id: 'recovery',
    type: 'agentNode',
    position: { x: 500, y: 250 },
    data: { 
      label: 'Recovery Agent',
      description: 'Handles disaster recovery',
      status: 'active',
      color: '#f59e0b'
    },
  },
  {
    id: 'sql_tuning',
    type: 'agentNode',
    position: { x: 700, y: 250 },
    data: { 
      label: 'SQL Tuning Agent',
      description: 'Optimizes query performance',
      status: 'active',
      color: '#06b6d4'
    },
  },
  {
    id: 'capacity',
    type: 'agentNode',
    position: { x: 200, y: 450 },
    data: { 
      label: 'Capacity Agent',
      description: 'Manages resource capacity',
      status: 'active',
      color: '#ec4899'
    },
  },
  {
    id: 'security',
    type: 'agentNode',
    position: { x: 400, y: 450 },
    data: { 
      label: 'Security Agent',
      description: 'Monitors security threats',
      status: 'active',
      color: '#ef4444'
    },
  },
  {
    id: 'browser',
    type: 'agentNode',
    position: { x: 600, y: 450 },
    data: { 
      label: 'Browser Agent',
      description: 'Searches SAP documentation',
      status: 'active',
      color: '#14b8a6'
    },
  },
  // Tool nodes
  {
    id: 'hana_tools',
    type: 'agentNode',
    position: { x: 100, y: 650 },
    data: { 
      label: 'HANA Tools',
      description: 'Direct HANA connection',
      status: 'idle',
      color: '#6366f1'
    },
  },
  {
    id: 'remote_exec',
    type: 'agentNode',
    position: { x: 350, y: 650 },
    data: { 
      label: 'Remote Exec',
      description: 'OS-level operations via HTTP',
      status: 'idle',
      color: '#6366f1'
    },
  },
  {
    id: 'rag_tools',
    type: 'agentNode',
    position: { x: 600, y: 650 },
    data: { 
      label: 'RAG Tools',
      description: 'Knowledge base queries',
      status: 'idle',
      color: '#6366f1'
    },
  },
]

const initialEdges = [
  // Supervisor connections
  { id: 'e-sup-health', source: 'supervisor', target: 'health', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-backup', source: 'supervisor', target: 'backup', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-recovery', source: 'supervisor', target: 'recovery', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-sql', source: 'supervisor', target: 'sql_tuning', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-capacity', source: 'supervisor', target: 'capacity', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-security', source: 'supervisor', target: 'security', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sup-browser', source: 'supervisor', target: 'browser', type: 'smoothstep', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  
  // Tool connections
  { id: 'e-health-hana', source: 'health', target: 'hana_tools', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-backup-hana', source: 'backup', target: 'hana_tools', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-recovery-exec', source: 'recovery', target: 'remote_exec', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-sql-hana', source: 'sql_tuning', target: 'hana_tools', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-capacity-hana', source: 'capacity', target: 'hana_tools', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-security-exec', source: 'security', target: 'remote_exec', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
  { id: 'e-browser-rag', source: 'browser', target: 'rag_tools', type: 'smoothstep', style: { stroke: '#888' }, markerEnd: { type: MarkerType.ArrowClosed } },
]

export default function AgentFlow() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [activeEdges, setActiveEdges] = useState([])

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  )

  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node)
  }, [])

  // The flow diagram is now static, showing the architecture
  // Node status updates would come from actual backend events in production

  return (
    <div className="h-screen flex">
      {/* Flow Canvas */}
      <div className="flex-1 bg-gradient-to-br from-gray-900 via-blue-900/10 to-purple-900/10">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="h-16 bg-gray-800/90 backdrop-blur border-b border-gray-700 flex items-center px-6"
        >
          <motion.div
            animate={{ 
              scale: [1, 1.1, 1],
              rotate: [0, 180, 360]
            }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            <Zap className="w-6 h-6 text-yellow-400 mr-3" />
          </motion.div>
          <div>
            <h2 className="text-xl font-semibold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Agent Flow Architecture
            </h2>
            <p className="text-xs text-gray-400">Interactive Multi-Agent System</p>
          </div>
          <div className="ml-auto flex items-center space-x-6">
            <motion.div 
              className="flex items-center space-x-2"
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              <Activity className="w-4 h-4 text-green-400" />
              <span className="text-sm text-gray-300">{nodes.length} Agents Active</span>
            </motion.div>
            <div className="flex items-center space-x-2">
              <motion.span 
                className="w-3 h-3 bg-green-500 rounded-full"
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              />
              <span className="text-sm text-gray-300">Live System</span>
            </div>
          </div>
        </motion.div>
        
        <div className="h-[calc(100vh-4rem)]">
          <ReactFlow
            nodes={nodes}
            edges={edges.map(edge => ({
              ...edge,
              animated: activeEdges.includes(edge.id) || edge.animated,
              style: {
                ...edge.style,
                stroke: activeEdges.includes(edge.id) ? '#3b82f6' : edge.style?.stroke,
                strokeWidth: activeEdges.includes(edge.id) ? 3 : 1,
              }
            }))}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Controls />
            <MiniMap 
              nodeColor={(node) => node.data.color || '#666'}
              maskColor="rgba(0, 0, 0, 0.6)"
            />
            <Background variant="dots" gap={12} size={1} color="#3b82f6" />
          </ReactFlow>
        </div>
      </div>

      {/* Details Panel */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 25 }}
            className="w-96 bg-gray-800 border-l border-gray-700 overflow-y-auto"
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <motion.h3 
                    initial={{ y: -10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="text-lg font-semibold text-white"
                  >
                    {selectedNode.data.label}
                  </motion.h3>
                  <p className="text-sm text-gray-400 mt-1">{selectedNode.data.description}</p>
                </div>
                <motion.button 
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => setSelectedNode(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </motion.button>
              </div>

              <div className="space-y-4">
                <motion.div
                  initial={{ x: -20, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.1 }}
                >
                  <label className="text-xs text-gray-500 uppercase">Status</label>
                  <div className="mt-1 flex items-center">
                    <motion.span 
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ repeat: Infinity, duration: 2 }}
                      className={`w-2 h-2 rounded-full mr-2 ${
                        selectedNode.data.status === 'active' ? 'bg-green-500' : 
                        selectedNode.data.status === 'processing' ? 'bg-blue-500' : 
                        'bg-gray-500'
                      }`}
                    />
                    <span className="text-sm text-white capitalize">{selectedNode.data.status}</span>
                  </div>
                </motion.div>

                <motion.div
                  initial={{ x: -20, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.2 }}
                >
                  <label className="text-xs text-gray-500 uppercase">Node ID</label>
                  <div className="mt-1 text-sm text-white font-mono bg-gray-700/50 px-3 py-2 rounded">
                    {selectedNode.id}
                  </div>
                </motion.div>

                <motion.div
                  initial={{ x: -20, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  <label className="text-xs text-gray-500 uppercase">Capabilities</label>
                  <div className="mt-2 space-y-1">
                    {getCapabilities(selectedNode.id).map((cap, idx) => (
                      <motion.div 
                        key={idx}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: 0.4 + idx * 0.05 }}
                        whileHover={{ x: 5, backgroundColor: 'rgba(59, 130, 246, 0.1)' }}
                        className="text-sm text-gray-300 flex items-center p-2 rounded"
                      >
                        <span className="mr-2">•</span>
                        {cap}
                      </motion.div>
                    ))}
                  </div>
                </motion.div>

                <motion.div
                  initial={{ x: -20, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  <label className="text-xs text-gray-500 uppercase">Recent Activity</label>
                  <div className="mt-2 space-y-2">
                    <ActivityItem time="2 min ago" action="Health check executed" />
                    <ActivityItem time="15 min ago" action="Metric collection completed" />
                    <ActivityItem time="1 hour ago" action="Alert threshold adjusted" />
                  </div>
                </motion.div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function getCapabilities(nodeId) {
  const capabilities = {
    supervisor: [
      'Policy enforcement',
      'Agent orchestration',
      'Risk budget management',
      'Action approval workflow'
    ],
    health: [
      'System health monitoring',
      'Service status checks',
      'Alert detection',
      'Performance metrics'
    ],
    backup: [
      'Backup scheduling',
      'Backup verification',
      'Recovery point tracking',
      'Storage management'
    ],
    recovery: [
      'Disaster recovery planning',
      'System restoration',
      'Failover management',
      'Data recovery'
    ],
    sql_tuning: [
      'Query performance analysis',
      'Index recommendations',
      'Execution plan optimization',
      'Statistics updates'
    ],
    capacity: [
      'Resource utilization tracking',
      'Capacity forecasting',
      'Growth trend analysis',
      'Scaling recommendations'
    ],
    security: [
      'Security audit',
      'Access control monitoring',
      'Threat detection',
      'Compliance checks'
    ],
    browser: [
      'SAP note search',
      'Documentation lookup',
      'KB article retrieval',
      'Solution recommendations'
    ],
    hana_tools: [
      'SQL query execution',
      'System view access',
      'Configuration management',
      'Direct HANA connection'
    ],
    remote_exec: [
      'OS command execution',
      'File system access',
      'Process management',
      'System configuration'
    ],
    rag_tools: [
      'Vector search',
      'Semantic retrieval',
      'Knowledge base queries',
      'Context-aware responses'
    ]
  }
  return capabilities[nodeId] || []
}

function ActivityItem({ time, action }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ x: 5, backgroundColor: 'rgba(59, 130, 246, 0.1)' }}
      className="text-sm p-2 rounded"
    >
      <div className="text-gray-400 text-xs">{time}</div>
      <div className="text-white">{action}</div>
    </motion.div>
  )
}
