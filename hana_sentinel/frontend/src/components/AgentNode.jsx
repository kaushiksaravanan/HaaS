import { memo } from 'react'
import { motion } from 'framer-motion'
import { Handle, Position } from 'reactflow'

export default memo(({ data }) => {
  const statusColor = data.status === 'active' ? 'border-green-500' : 
                     data.status === 'processing' ? 'border-blue-500' : 
                     'border-gray-600'
  
  return (
    <motion.div 
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      whileHover={{ scale: 1.05, boxShadow: `0 0 20px ${data.color}` }}
      className={`px-4 py-3 rounded-lg border-2 ${statusColor} bg-gray-800 shadow-lg min-w-[180px] relative overflow-hidden`}
      style={{ borderColor: data.color }}
    >
      {/* Animated background gradient */}
      <motion.div
        animate={{
          backgroundPosition: ['0% 0%', '100% 100%', '0% 0%'],
        }}
        transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 opacity-10"
        style={{
          background: `linear-gradient(135deg, ${data.color}, transparent)`,
          backgroundSize: '200% 200%',
        }}
      />
      
      <Handle type="target" position={Position.Top} className="w-3 h-3" style={{ background: data.color }} />
      
      <div className="relative z-10">
        <div className="font-semibold text-white text-sm mb-1">{data.label}</div>
        <div className="text-xs text-gray-400">{data.description}</div>
        
        <div className="mt-2 flex items-center justify-between">
          <motion.span 
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className={`w-2 h-2 rounded-full mr-1 ${
              data.status === 'active' ? 'bg-green-500' : 
              data.status === 'processing' ? 'bg-blue-500' : 
              'bg-gray-500'
            }`}
          />
          <span className="text-xs text-gray-400 capitalize flex-1">{data.status}</span>
          {data.status === 'processing' && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full"
            />
          )}
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="w-3 h-3" style={{ background: data.color }} />
    </motion.div>
  )
})
