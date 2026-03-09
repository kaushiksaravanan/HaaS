import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Zap, CheckCircle, XCircle, Clock } from 'lucide-react';
import { useState, useEffect } from 'react';
import Confetti from 'react-confetti';

export default function ParameterChangeVisualizer() {
  const [changes, setChanges] = useState([]);
  const [showConfetti, setShowConfetti] = useState(false);

  // In production, this would fetch real parameter changes from the backend
  // For now, we'll just show an empty state or fetch from API
  useEffect(() => {
    // TODO: Fetch actual parameter changes from backend API
    // For now, just maintain empty state
  }, []);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'applying':
        return <ClockLoader />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-blue-400" />;
    }
  };

  const getImpactColor = (impact) => {
    switch (impact) {
      case 'high':
        return 'from-red-500 to-orange-500';
      case 'medium':
        return 'from-orange-500 to-yellow-500';
      default:
        return 'from-blue-500 to-cyan-500';
    }
  };

  const getImpactBadge = (impact) => {
    const colors = {
      high: 'bg-red-500/20 text-red-400 border-red-500/30',
      medium: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    };
    return colors[impact] || colors.low;
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 relative">
      {showConfetti && (
        <Confetti
          width={400}
          height={400}
          recycle={false}
          numberOfPieces={200}
          gravity={0.3}
        />
      )}

      <div className="flex items-center space-x-3 mb-6">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 3, ease: "linear" }}
        >
          <Settings className="w-6 h-6 text-purple-500" />
        </motion.div>
        <div>
          <h3 className="text-lg font-semibold text-white">Parameter Changes</h3>
          <p className="text-sm text-gray-400">Real-time VM configuration updates</p>
        </div>
      </div>

      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {changes.map((change) => (
            <motion.div
              key={change.id}
              initial={{ opacity: 0, x: -100, rotateX: -90 }}
              animate={{ opacity: 1, x: 0, rotateX: 0 }}
              exit={{ opacity: 0, x: 100, rotateX: 90 }}
              transition={{ type: "spring", stiffness: 100 }}
              className="relative overflow-hidden rounded-lg"
            >
              {/* Animated gradient background */}
              <motion.div
                animate={{
                  backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
                }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                className={`absolute inset-0 bg-gradient-to-r ${getImpactColor(change.impact)} opacity-10`}
                style={{ backgroundSize: '200% 200%' }}
              />

              <div className="relative p-4 border border-gray-700 rounded-lg bg-gray-800/90 backdrop-blur">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    {getStatusIcon(change.status)}
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <code className="text-sm font-mono text-white bg-gray-700/50 px-2 py-1 rounded">
                          {change.param}
                        </code>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${getImpactBadge(change.impact)}`}>
                          {change.impact} impact
                        </span>
                      </div>

                      <div className="flex items-center space-x-2 text-sm">
                        <span className="text-gray-400">{change.old}</span>
                        <motion.div
                          animate={{ x: [0, 10, 0] }}
                          transition={{ repeat: Infinity, duration: 1.5 }}
                        >
                          <Zap className="w-4 h-4 text-yellow-400" />
                        </motion.div>
                        <span className="text-green-400 font-semibold">{change.new}</span>
                      </div>

                      {/* Progress bar for applying status */}
                      {change.status === 'applying' && (
                        <div className="mt-2">
                          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                            <motion.div
                              animate={{ x: ['0%', '100%'] }}
                              transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                              className="h-full w-1/3 bg-gradient-to-r from-blue-500 to-purple-500"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                    className="text-xs text-gray-500"
                  >
                    {change.status}
                  </motion.div>
                </div>

                {/* Impact visualization */}
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  className="mt-3 pt-3 border-t border-gray-700"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Performance Impact</span>
                    <div className="flex items-center space-x-1">
                      {[...Array(change.impact === 'high' ? 3 : change.impact === 'medium' ? 2 : 1)].map((_, i) => (
                        <motion.div
                          key={i}
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: i * 0.1 }}
                          className={`w-2 h-2 rounded-full ${
                            change.impact === 'high' ? 'bg-red-500' :
                            change.impact === 'medium' ? 'bg-orange-500' :
                            'bg-blue-500'
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {changes.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-8 text-gray-500"
        >
          <Settings className="w-12 h-12 mx-auto mb-2 opacity-20" />
          <p>No recent parameter changes</p>
        </motion.div>
      )}
    </div>
  );
}

function ClockLoader() {
  return (
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
    >
      <Clock className="w-5 h-5 text-blue-400" />
    </motion.div>
  );
}
