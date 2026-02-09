import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './AuthContext';
import { toast } from 'sonner';

const NotificationContext = createContext(null);

// Sonidos de notificación (Base64 encoded beeps)
const SOUND_URGENT = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YVoGAACBgoSFh4mKjI2Oj5GSk5WWl5mamZqbnJ2enp+goaKipKWlpqeoqaqrrK2trq+xsbKztLS1tre3uLm6u7u8vb6/v8DBwsPDxMXGx8jIycrLy8zNzs7P0NDR0tPT1NTU1dbX19jY2dna2tvb3Nzd3t7f3+Dg4OHh4uLj4+Pk5OXl5ebl5ufn5+jo6enp6erq6uvr6+zs7O3t7e3u7u/v7+/w8PDx8fHy8vLy8vPz8/P09PT09PX19fX19vb29vb39/f39/j4+Pj4+Pn5+fn5+fn6+vr6+vr6+/v7+/v7+/z8/Pz8/Pz8/f39/f39/f39/f7+/v7+/v7+/v7+/v7+';
const SOUND_HOT = 'data:audio/wav;base64,UklGRjIAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ4AAAB/fn18e3p5eHd2dXR0';
const SOUND_MESSAGE = 'data:audio/wav;base64,UklGRjIAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ4AAAB/gIGCg4SFhoeI';

// Función para reproducir sonido
const playSound = (soundData, volume = 0.5) => {
  try {
    const audio = new Audio(soundData);
    audio.volume = volume;
    audio.play().catch(e => console.log('Audio play failed:', e));
  } catch (e) {
    console.log('Sound not available');
  }
};

export function NotificationProvider({ children }) {
  const { token, isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);

  const handleNotification = useCallback((data) => {
    if (data.type === 'heartbeat' || data.type === 'connected') {
      return;
    }

    const notification = {
      id: Date.now(),
      ...data,
      read: false,
      receivedAt: new Date().toISOString()
    };

    setNotifications(prev => [notification, ...prev].slice(0, 50));
    setUnreadCount(prev => prev + 1);

    // Reproducir sonido según tipo de notificación
    if (soundEnabled) {
      switch (data.type) {
        case 'urgent_lead':
          playSound(SOUND_URGENT, 0.8);
          break;
        case 'new_lead_assigned':
        case 'high_value_lead':
          playSound(SOUND_HOT, 0.6);
          break;
        case 'customer_replied':
          playSound(SOUND_MESSAGE, 0.4);
          break;
        default:
          playSound(SOUND_MESSAGE, 0.3);
      }
    }

    switch (data.type) {
      case 'urgent_lead':
        toast.error(data.title, { description: data.message, duration: 10000 });
        break;
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
  }, [soundEnabled]);

  useEffect(() => {
    // Solo conectar si está autenticado con token válido
    if (!token || !isAuthenticated) {
      console.log('No conectando WebSocket - usuario no autenticado');
      return;
    }

    // WebSocket se conecta directamente sin /api
    const wsUrl = process.env.REACT_APP_BACKEND_URL
      .replace('https://', 'wss://')
      .replace('http://', 'ws://');
    
    // Intentar primero con /api/ws y luego sin /api
    const ws = new WebSocket(`${wsUrl}/api/ws/notifications?token=${token}`);
    
    ws.onopen = () => {
      console.log('WebSocket conectado');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Solo procesar notificaciones si sigue autenticado
        if (isAuthenticated) {
          handleNotification(data);
        }
      } catch (e) {
        console.error('Error parsing notification:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket desconectado');
      setConnected(false);
      
      reconnectTimeout.current = setTimeout(() => {
        // Will reconnect on next effect run
      }, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 25000);

    return () => {
      clearInterval(pingInterval);
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      ws.close();
    };
  }, [token, isAuthenticated, handleNotification]);

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

  const toggleSound = useCallback(() => {
    setSoundEnabled(prev => !prev);
  }, []);

  return (
    <NotificationContext.Provider value={{
      notifications,
      unreadCount,
      connected,
      soundEnabled,
      markAsRead,
      markAllAsRead,
      clearNotifications,
      toggleSound
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
