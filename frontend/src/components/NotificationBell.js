import React, { useState } from 'react';
import { useNotifications } from '../context/NotificationContext';
import { useNavigate } from 'react-router-dom';

export default function NotificationBell() {
  const { notifications, unreadCount, connected, soundEnabled, markAsRead, markAllAsRead, toggleSound } = useNotifications();
  const [showDropdown, setShowDropdown] = useState(false);
  const navigate = useNavigate();

  const handleNotificationClick = (notification) => {
    markAsRead(notification.id);
    
    if (notification.lead_phone) {
      navigate(`/leads/${notification.lead_phone}`);
    }
    
    setShowDropdown(false);
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'urgent_lead': return '🚨';
      case 'new_lead_assigned': return '🔥';
      case 'customer_replied': return '💬';
      case 'high_value_lead': return '🎯';
      case 'appointment_reminder': return '⏰';
      case 'inactive_lead': return '🟡';
      case 'agent_overloaded': return '⚠️';
      case 'daily_goal_reached': return '🎉';
      case 'note_added': return '📝';
      default: return '🔔';
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = (now - date) / 1000;

    if (diff < 60) return 'Ahora';
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return date.toLocaleDateString('es-AR');
  };

  return (
    <div className="notification-bell" data-testid="notification-bell">
      <button 
        className="bell-button"
        onClick={() => setShowDropdown(!showDropdown)}
        data-testid="btn-notifications"
      >
        <span className="bell-icon">🔔</span>
        {unreadCount > 0 && (
          <span className="badge-count" data-testid="notification-count">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
        <span className={`connection-indicator ${connected ? 'connected' : 'disconnected'}`} />
      </button>

      {showDropdown && (
        <div className="notification-dropdown" data-testid="notification-dropdown">
          <div className="dropdown-header">
            <h4>Notificaciones</h4>
            <div className="header-actions">
              <button 
                className={`sound-toggle ${soundEnabled ? 'enabled' : 'disabled'}`}
                onClick={toggleSound}
                title={soundEnabled ? 'Silenciar notificaciones' : 'Activar sonido'}
                data-testid="btn-toggle-sound"
              >
                {soundEnabled ? '🔊' : '🔇'}
              </button>
              {unreadCount > 0 && (
                <button 
                  className="mark-all-btn"
                  onClick={markAllAsRead}
                  data-testid="btn-mark-all-read"
                >
                  Marcar leídas
                </button>
              )}
            </div>
          </div>

          <div className="notification-list">
            {notifications.length === 0 ? (
              <div className="empty-notifications">
                <span>🔔</span>
                <p>No hay notificaciones</p>
              </div>
            ) : (
              notifications.slice(0, 10).map(notification => (
                <div
                  key={notification.id}
                  className={`notification-item ${notification.read ? 'read' : 'unread'} ${notification.type === 'urgent_lead' ? 'urgent' : ''}`}
                  onClick={() => handleNotificationClick(notification)}
                  data-testid={`notification-${notification.id}`}
                >
                  <span className="notification-icon">
                    {getNotificationIcon(notification.type)}
                  </span>
                  <div className="notification-content">
                    <p className="notification-title">{notification.title}</p>
                    <p className="notification-message">{notification.message}</p>
                    <span className="notification-time">
                      {formatTime(notification.timestamp || notification.receivedAt)}
                    </span>
                  </div>
                  {!notification.read && <span className="unread-dot" />}
                </div>
              ))
            )}
          </div>

          {notifications.length > 10 && (
            <div className="dropdown-footer">
              <button onClick={() => navigate('/notifications')}>
                Ver todas ({notifications.length})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
