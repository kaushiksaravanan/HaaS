import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Zap, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { format } from 'date-fns';
import { useActivityStream } from '../hooks/useRealtime';

export default function LiveActivityStream() {
  const { activities, newActivity } = useActivityStream(30);

  const getIcon = (severity) => {
    switch (severity) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-orange-400" />;
      case 'error':
        return <AlertTriangle className="w-4 h-4 text-red-400" />;
      default:
        return <Info className="w-4 h-4 text-blue-400" />;
    }
  };

  const getBackgroundColor = (severity) => {
    switch (severity) {
      case 'success':
        return 'bg-green-500/10 border-green-500/30';
      case 'warning':
        return 'bg-orange-500/10 border-orange-500/30';
      case 'error':
        return 'bg-red-500/10 border-red-500/30';
      default:
        return 'bg-blue-500/10 border-blue-500/30';
    }
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-semibold text-white">Live Activity Stream</h3>
        </div>
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="flex items-center space-x-1"
        >
          <span className="w-2 h-2 bg-green-500 rounded-full"></span>
          <span className="text-xs text-green-400">LIVE</span>
        </motion.div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        <AnimatePresence mode="popLayout">
          {activities.map((activity, index) => (
            <motion.div
              key={activity.id}
              initial={{ opacity: 0, x: -50, scale: 0.9 }}
              animate={{ 
                opacity: 1, 
                x: 0, 
                scale: 1,
                backgroundColor: activity.id === newActivity?.id 
                  ? ['rgba(59, 130, 246, 0.3)', 'rgba(59, 130, 246, 0)', 'rgba(59, 130, 246, 0)']
                  : 'rgba(0, 0, 0, 0)'
              }}
              exit={{ opacity: 0, x: 50, scale: 0.9 }}
              transition={{ duration: 0.3, delay: index * 0.05 }}
              className={`p-3 rounded-lg border ${getBackgroundColor(activity.severity)} hover:border-opacity-50 transition-all`}
            >
              <div className="flex items-start space-x-3">
                <motion.div
                  initial={{ rotate: 0 }}
                  animate={{ rotate: activity.id === newActivity?.id ? 360 : 0 }}
                  transition={{ duration: 0.5 }}
                  className="mt-0.5"
                >
                  {getIcon(activity.severity)}
                </motion.div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white">{activity.icon} {activity.message}</span>
                    {activity.id === newActivity?.id && (
                      <motion.span
                        initial={{ opacity: 0, scale: 0 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="text-xs bg-blue-500 text-white px-2 py-0.5 rounded-full"
                      >
                        NEW
                      </motion.span>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {format(activity.timestamp, 'HH:mm:ss')}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
