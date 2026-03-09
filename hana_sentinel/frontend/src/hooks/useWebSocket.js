import { useState, useEffect, useRef } from 'react';

/**
 * WebSocket hook for real-time instance status updates
 * @param {string} url - WebSocket URL (e.g., '/ws/instance-status')
 * @returns {object} - { status, data, sendMessage }
 */
export const useWebSocket = (url) => {
  const [status, setStatus] = useState('disconnected');
  const [data, setData] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {
    const connect = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${url}`;

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('WebSocket connected');
          setStatus('connected');

          // Send ping every 30 seconds to keep connection alive
          const pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }));
            }
          }, 30000);

          ws.pingInterval = pingInterval;
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            setData(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setStatus('error');
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected');
          setStatus('disconnected');

          // Clear ping interval
          if (ws.pingInterval) {
            clearInterval(ws.pingInterval);
          }

          // Attempt reconnect after 5 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, 5000);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        setStatus('error');
      }
    };

    connect();

    return () => {
      // Cleanup on unmount
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [url]);

  const sendMessage = (message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected. Cannot send message.');
    }
  };

  return { status, data, sendMessage };
};
