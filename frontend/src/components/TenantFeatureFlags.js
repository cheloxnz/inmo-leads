import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '@/components/ui/button';
import { Loader2, Flag, Check, X } from 'lucide-react';
import { toast } from 'sonner';

const CATEGORY_LABELS = {
  bot: 'Bot WhatsApp',
  dashboard: 'Dashboard',
  integrations: 'Integraciones',
  beta: 'Beta / Misceláneo',
};

const CATEGORY_COLORS = {
  bot: '#6366f1',
  dashboard: '#10b981',
  integrations: '#f59e0b',
  beta: '#8b5cf6',
};

export default function TenantFeatureFlags({ tenantId }) {
  const [registry, setRegistry] = useState([]);
  const [features, setFeatures] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(null);

  useEffect(() => {
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [reg, t] = await Promise.all([
        axios.get(`${API}/superadmin/feature-flags/registry`),
        axios.get(`${API}/superadmin/tenants/${tenantId}/features`),
      ]);
      setRegistry(reg.data.flags || []);
      setFeatures(t.data.features || {});
    } catch (e) {
      toast.error('Error cargando feature flags');
    } finally {
      setLoading(false);
    }
  };

  const toggleFlag = async (key, currentValue) => {
    setSavingKey(key);
    try {
      await axios.put(`${API}/superadmin/tenants/${tenantId}/features`, {
        feature: key,
        enabled: !currentValue,
      });
      setFeatures((prev) => ({ ...prev, [key]: !currentValue }));
      toast.success(`${key}: ${!currentValue ? 'activado' : 'desactivado'}`);
    } catch (e) {
      toast.error('Error guardando flag: ' + (e.response?.data?.detail || e.message));
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="sa-ff-loading" data-testid={`feature-flags-loading-${tenantId}`}>
        <Loader2 className="w-4 h-4 animate-spin" /> Cargando feature flags…
      </div>
    );
  }

  // Group by category
  const grouped = {};
  registry.forEach((f) => {
    const c = f.category || 'beta';
    if (!grouped[c]) grouped[c] = [];
    grouped[c].push(f);
  });

  return (
    <div className="sa-ff-section" data-testid={`feature-flags-${tenantId}`}>
      <div className="sa-ff-header">
        <Flag className="w-4 h-4" />
        <strong>Feature Flags</strong>
        <span className="sa-ff-hint">Activá/desactivá funcionalidades específicas para este cliente</span>
      </div>
      {Object.entries(grouped).map(([cat, flags]) => (
        <div key={cat} className="sa-ff-group">
          <div className="sa-ff-cat" style={{ color: CATEGORY_COLORS[cat] || '#6b7280' }}>
            {CATEGORY_LABELS[cat] || cat}
          </div>
          <div className="sa-ff-list">
            {flags.map((f) => {
              const enabled = !!features[f.key];
              const saving = savingKey === f.key;
              return (
                <div
                  key={f.key}
                  className={`sa-ff-row ${enabled ? 'enabled' : ''}`}
                  data-testid={`flag-row-${f.key}`}
                >
                  <div className="sa-ff-row-info">
                    <div className="sa-ff-row-label">{f.label}</div>
                    <div className="sa-ff-row-desc">{f.description}</div>
                    <div className="sa-ff-row-key">{f.key}</div>
                  </div>
                  <Button
                    size="sm"
                    variant={enabled ? 'default' : 'outline'}
                    onClick={() => toggleFlag(f.key, enabled)}
                    disabled={saving}
                    data-testid={`toggle-flag-${f.key}`}
                    className={enabled ? 'sa-ff-btn-on' : ''}
                  >
                    {saving ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : enabled ? (
                      <><Check className="w-3 h-3 mr-1" /> Activo</>
                    ) : (
                      <><X className="w-3 h-3 mr-1" /> Inactivo</>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
