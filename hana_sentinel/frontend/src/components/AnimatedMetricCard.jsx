import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function AnimatedMetricCard({ 
  title, 
  value, 
  previousValue,
  icon: Icon, 
  color, 
  bgColor, 
  unit = '',
  threshold = null 
}) {
  const [shouldAnimate, setShouldAnimate] = useState(false);
  
  const change = previousValue !== undefined ? value - previousValue : 0;
  const changePercent = previousValue ? ((change / previousValue) * 100).toFixed(1) : 0;
  
  const isWarning = threshold && value > threshold;
  const displayColor = isWarning ? 'text-red-500' : color;
  const displayBgColor = isWarning ? 'bg-red-500/10' : bgColor;

  useEffect(() => {
    if (change !== 0) {
      setShouldAnimate(true);
      const timer = setTimeout(() => setShouldAnimate(false), 1000);
      return () => clearTimeout(timer);
    }
  }, [change]);

  const getTrendIcon = () => {
    if (change > 0) return <TrendingUp className="w-4 h-4 text-green-400" />;
    if (change < 0) return <TrendingDown className="w-4 h-4 text-red-400" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  return (
    <motion.div
      animate={{
        scale: shouldAnimate ? [1, 1.05, 1] : 1,
        borderColor: shouldAnimate ? ['#374151', displayColor, '#374151'] : '#374151'
      }}
      transition={{ duration: 0.5 }}
      className="bg-gray-800 border-2 border-gray-700 rounded-lg p-6 relative overflow-hidden"
    >
      {/* Background pulse effect on change */}
      {shouldAnimate && (
        <motion.div
          initial={{ opacity: 0.5, scale: 0 }}
          animate={{ opacity: 0, scale: 2 }}
          transition={{ duration: 1 }}
          className={`absolute inset-0 ${displayBgColor} rounded-lg`}
        />
      )}

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-3">
          <motion.div
            animate={{ rotate: shouldAnimate ? [0, 15, -15, 0] : 0 }}
            transition={{ duration: 0.5 }}
            className={`p-3 rounded-lg ${displayBgColor}`}
          >
            <Icon className={`w-6 h-6 ${displayColor}`} />
          </motion.div>
          
          {change !== 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center space-x-1"
            >
              {getTrendIcon()}
              <span className={`text-xs ${change > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {change > 0 ? '+' : ''}{changePercent}%
              </span>
            </motion.div>
          )}
        </div>

        <div className="space-y-2">
          <motion.div
            key={value}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="text-3xl font-bold text-white"
          >
            {value}{unit}
          </motion.div>
          
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-400">{title}</div>
            {isWarning && (
              <motion.span
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded"
              >
                ⚠️ HIGH
              </motion.span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {threshold && (
          <div className="mt-3">
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((value / threshold) * 100, 100)}%` }}
                transition={{ duration: 0.5 }}
                className={`h-full ${isWarning ? 'bg-red-500' : 'bg-blue-500'}`}
              />
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
