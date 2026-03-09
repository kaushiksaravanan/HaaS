import { useState, useEffect, useCallback } from 'react';
import { metricsAPI } from '../services/api';

/**
 * Hook for real-time data polling
 * @param {string} endpoint - API endpoint to poll
 * @param {number} interval - Polling interval in ms (default: 3000)
 */
export function useRealtime(endpoint, interval = 3000) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const response = await metricsAPI.getRealtime();
      setData(response.data);
      setLastUpdate(new Date());
      setError(null);
      setIsLoading(false);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData(); // Initial fetch
    const intervalId = setInterval(fetchData, interval);
    return () => clearInterval(intervalId);
  }, [fetchData, interval]);

  return { data, isLoading, error, lastUpdate, refresh: fetchData };
}

/**
 * Hook for real-time metrics with change detection
 */
export function useRealtimeMetrics(interval = 2000) {
  const [metrics, setMetrics] = useState(null);
  const [changes, setChanges] = useState([]);
  const [trend, setTrend] = useState({});

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await metricsAPI.getRealtime();
      const newMetrics = response.data;

      if (metrics) {
        // Detect changes
        const newChanges = [];
        
        // CPU change
        if (newMetrics.cpu_usage !== metrics.cpu_usage) {
          newChanges.push({
            id: Date.now(),
            metric: 'CPU',
            old: metrics.cpu_usage,
            new: newMetrics.cpu_usage,
            change: newMetrics.cpu_usage - metrics.cpu_usage,
            timestamp: new Date(),
          });
        }

        // Memory change
        if (newMetrics.memory_usage !== metrics.memory_usage) {
          newChanges.push({
            id: Date.now() + 1,
            metric: 'Memory',
            old: metrics.memory_usage,
            new: newMetrics.memory_usage,
            change: newMetrics.memory_usage - metrics.memory_usage,
            timestamp: new Date(),
          });
        }

        if (newChanges.length > 0) {
          setChanges(prev => [...newChanges, ...prev].slice(0, 20));
        }

        // Calculate trends
        setTrend({
          cpu: newMetrics.cpu_usage > (metrics.cpu_usage || 0) ? 'up' : 'down',
          memory: newMetrics.memory_usage > (metrics.memory_usage || 0) ? 'up' : 'down',
        });
      }

      setMetrics(newMetrics);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  }, [metrics]);

  useEffect(() => {
    fetchMetrics();
    const intervalId = setInterval(fetchMetrics, interval);
    return () => clearInterval(intervalId);
  }, [fetchMetrics, interval]);

  return { metrics, changes, trend };
}

/**
 * Hook for live activity stream
 */
export function useActivityStream(maxItems = 50) {
  const [activities, setActivities] = useState([]);
  const [newActivity, setNewActivity] = useState(null);

  const addActivity = useCallback((activity) => {
    const newItem = {
      id: Date.now(),
      timestamp: new Date(),
      ...activity,
    };
    
    setNewActivity(newItem);
    setActivities(prev => [newItem, ...prev].slice(0, maxItems));
    
    // Clear the new activity indicator after animation
    setTimeout(() => setNewActivity(null), 1000);
  }, [maxItems]);

  // Poll for new activities from backend
  useEffect(() => {
    const fetchActivities = async () => {
      try {
        const response = await metricsAPI.getActivities(maxItems)
        const fetchedActivities = response.data.activities || []
        
        // Update the activities list with new ones from backend
        if (fetchedActivities.length > 0) {
          setActivities(fetchedActivities.map(activity => ({
            id: activity.id,
            type: activity.type,
            message: activity.message,
            severity: activity.severity,
            icon: getIconForActivityType(activity.type),
            timestamp: new Date(activity.timestamp),
          })))
        }
      } catch (err) {
        console.error('Failed to fetch activities:', err)
      }
    }

    const interval = setInterval(fetchActivities, 5000)
    fetchActivities() // Initial fetch
    
    return () => clearInterval(interval)
  }, [maxItems])

  return { activities, newActivity, addActivity }
}

/**
 * Get icon emoji for activity type
 */
function getIconForActivityType(type) {
  const icons = {
    incident: '⚠️',
    action: '⚙️',
    metric: '📈',
    agent: '✅',
    config: '⚙️',
    backup: '💾',
    query: '🐌',
    security: '🔒',
  }
  return icons[type] || 'ℹ️'
}
