import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './AuthContext';
import { toast } from 'sonner';

const NotificationContext = createContext(null);

export function NotificationProvider({ children }) {
  const { token, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);

  const connectWebSocket = useCallback(() => {
    if (!token || !isAuthenticated) return;

    const wsUrl = process.env.REACT_APP_BACKEND_URL
      .replace('https://', 'wss://')
      .replace('http://', 'ws://');
    
    const ws = new WebSocket(`${wsUrl}/ws/notifications?token=${token}`);
    
    ws.onopen = () => {
      console.log('WebSocket conectado');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'heartbeat' || data.type === 'connected') {
          return;
        }

        // Agregar notificación
        const notification = {
          id: Date.now(),
          ...data,
          read: false,
          receivedAt: new Date().toISOString()
        };

        setNotifications(prev => [notification, ...prev].slice(0, 50));
        setUnreadCount(prev => prev + 1);

        // Mostrar toast según tipo
        switch (data.type) {
          case 'new_lead_assigned':
            toast.success(data.title, { description: data.message });
            break;
          case 'customer_replied':
            toast.info(data.title, { description: data.message });
            break;
          case 'high_value_lead':
            toast.warning(data.title, { description: data.message });
            break;
          case 'appointment_reminder':
            toast(data.title, { description: data.message, icon: '⏰' });
            break;
          case 'inactive_lead':
            toast(data.title, { description: data.message, icon: '🟡' });
            break;
          case 'agent_overloaded':
            toast.error(data.title, { description: data.message });
            break;
          case 'daily_goal_reached':
            toast.success(data.title, { description: data.message, icon: '🎉' });
            break;
          default:
            toast(data.title || 'Nueva notificación', { description: data.message });
        }
      } catch (e) {
        console.error('Error parsing notification:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket desconectado');
      setConnected(false);
      
      // Reconectar después de 5 segundos
      reconnectTimeout.current = setTimeout(() => {
        if (token && isAuthenticated) {
          connectWebSocket();
        }
      }, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    // Ping cada 25 segundos
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 25000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [token, isAuthenticated]);

  useEffect(() => {
    const cleanup = connectWebSocket();
    
    return () => {
      if (cleanup) cleanup();
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  const markAsRead = useCallback((notificationId) => {
    setNotifications(prev => 
      prev.map(n => n.id === notificationId ? { ...n, read: true } : n)
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    setUnreadCount(0);
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  return (
    <NotificationContext.Provider value={{
      notifications,
      unreadCount,
      connected,
      markAsRead,
      markAllAsRead,
      clearNotifications
    }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications debe usarse dentro de NotificationProvider');
  }
  return context;
}
