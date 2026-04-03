import { memo } from 'react'
import { motion } from 'framer-motion'
import { Handle, Position } from 'reactflow'

export default memo(({ data, selected }) => {
  const isProcessing = data.status === 'processing'
  const isError = data.status === 'error'
  const isActive = data.status === 'active'
  const isInteractive = data.isInteractive
  const isTool = data.nodeType === 'tool_group'
  const isSupervisor = data.nodeType === 'supervisor'
  
  return (
    <motion.div 
      initial={{ scale: 0, opacity: 0 }}
      animate={{ 
        scale: 1, 
        opacity: 1,
        boxShadow: isProcessing
          ? [`0 0 6px ${data.color}40`, `0 0 18px ${data.color}80`, `0 0 6px ${data.color}40`]
          : selected
          ? `0 0 12px ${data.color}60`
          : `0 0 0px transparent`,
      }}
      whileHover={{ scale: 1.05, boxShadow: `0 0 20px ${data.color}60` }}
      transition={isProcessing ? { boxShadow: { duration: 1, repeat: Infinity } } : {}}
      className={`shadow-lg relative overflow-hidden ${
        isTool
          ? 'px-2.5 py-1.5 rounded-md border w-[130px]'
          : isSupervisor
          ? 'px-4 py-3 rounded-xl border-2 w-[190px]'
          : 'px-3 py-2 rounded-lg border-2 w-[170px]'
      } ${isTool ? 'bg-gray-800/70' : 'bg-gray-800'} ${
        isInteractive ? 'cursor-pointer' : ''
      }`}
      style={{ 
        borderColor: isProcessing ? '#3b82f6' : isError ? '#ef4444' : data.color,
        borderStyle: isTool ? 'dashed' : 'solid',
      }}
    >
      {/* Subtle background gradient */}
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          background: `linear-gradient(135deg, ${data.color}, transparent)`,
        }}
      />
      
      <Handle type="target" position={Position.Top} className="w-2.5 h-2.5" style={{ background: data.color }} />
      
      <div className="relative z-10">
        {/* Title row */}
        <div className="flex items-center gap-1">
          {isTool && <span className="text-[9px] text-indigo-400">⚙</span>}
          {isSupervisor && <span className="text-[10px] text-purple-400">👑</span>}
          <div className={`font-semibold text-white truncate flex-1 ${
            isTool ? 'text-[11px]' : isSupervisor ? 'text-sm' : 'text-xs'
          }`}>
            {data.label}
          </div>
          {isInteractive && !isTool && (
            <div className="w-1.5 h-1.5 rounded-full bg-purple-400 opacity-50 flex-shrink-0" title="Interactive" />
          )}
        </div>

        {/* Description — truncated to 1 line for agents, hidden for tools */}
        {!isTool && data.description && (
          <div className="text-[10px] text-gray-500 mt-0.5 truncate">{data.description}</div>
        )}
        
        {/* Status bar */}
        <div className={`flex items-center gap-1 ${isTool ? 'mt-1' : 'mt-1.5'}`}>
          <motion.span 
            animate={isProcessing ? { scale: [1, 1.5, 1] } : { scale: [1, 1.2, 1] }}
            transition={{ duration: isProcessing ? 0.6 : 2, repeat: Infinity }}
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              isActive ? 'bg-green-500' : 
              isProcessing ? 'bg-blue-500' : 
              isError ? 'bg-red-500' :
              'bg-gray-500'
            }`}
          />
          <span className={`text-[10px] capitalize flex-1 ${
            isProcessing ? 'text-blue-400' : isError ? 'text-red-400' : 'text-gray-500'
          }`}>{isTool ? 'tool' : data.status}</span>
          {isProcessing && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
              className="w-2.5 h-2.5 border-[1.5px] border-blue-400 border-t-transparent rounded-full"
            />
          )}
          {data.riskTier && !isTool && (
            <span className={`text-[8px] px-1 py-0.5 rounded leading-none ${ 
              data.riskTier === 'low' ? 'bg-green-500/10 text-green-400' :
              data.riskTier === 'high' ? 'bg-red-500/10 text-red-400' :
              data.riskTier === 'orchestrator' ? 'bg-purple-500/10 text-purple-400' :
              'bg-yellow-500/10 text-yellow-400'
            }`}>
              {data.riskTier === 'orchestrator' ? '⚡' : data.riskTier}
            </span>
          )}
        </div>
      </div>
      
      <Handle type="source" position={Position.Bottom} className="w-2.5 h-2.5" style={{ background: data.color }} />
    </motion.div>
  )
})
