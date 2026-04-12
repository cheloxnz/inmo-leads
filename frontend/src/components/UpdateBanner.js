import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, X } from 'lucide-react';
import axios from 'axios';
import { API } from '../App';

const CHECK_INTERVAL = 60000; // Chequear cada 60 segundos

export default function UpdateBanner() {
  const [updateInfo, setUpdateInfo] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [knownVersion, setKnownVersion] = useState(() => {
    return localStorage.getItem('inmobot_app_version') || null;
  });

  const checkForUpdates = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/app/version`);
      const data = res.data;

      if (!data.update_message) {
        setUpdateInfo(null);
        return;
      }

      // Si hay mensaje de actualización y la versión cambió
      if (data.version !== knownVersion || data.update_message) {
        setUpdateInfo(data);
        setDismissed(false);
      }
    } catch {
      // Silently fail
    }
  }, [knownVersion]);

  useEffect(() => {
    checkForUpdates();
    const interval = setInterval(checkForUpdates, CHECK_INTERVAL);
    return () => clearInterval(interval);
  }, [checkForUpdates]);

  const handleRefresh = () => {
    if (updateInfo?.version) {
      localStorage.setItem('inmobot_app_version', updateInfo.version);
    }
    window.location.reload();
  };

  const handleDismiss = () => {
    setDismissed(true);
    if (updateInfo?.version) {
      localStorage.setItem('inmobot_app_version', updateInfo.version);
    }
  };

  if (!updateInfo || !updateInfo.update_message || dismissed) return null;

  return (
    <div className="update-banner" data-testid="update-banner">
      <div className="update-banner-content">
        <RefreshCw className="update-banner-icon" />
        <span>{updateInfo.update_message}</span>
        <button className="update-refresh-btn" onClick={handleRefresh} data-testid="update-refresh-btn">
          Actualizar ahora
        </button>
        <button className="update-dismiss-btn" onClick={handleDismiss} data-testid="update-dismiss-btn">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
