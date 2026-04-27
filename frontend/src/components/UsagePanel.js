import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Zap, AlertTriangle, ShoppingCart, TrendingUp, 
  MessageSquare, Users, Sparkles, Info
} from 'lucide-react';

export default function UsagePanel() {
  const { isSuperAdmin } = useAuth();
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState(null);

  const fetchUsage = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/usage`);
      setUsage(res.data);
    } catch (err) {
      console.error('Error fetching usage:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsage(); }, [fetchUsage]);

  // Check URL params for pack purchase confirmation
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const packStatus = params.get('pack');
    const packId = params.get('pack_id');
    if (packStatus === 'success' && packId) {
      confirmPack(packId);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const confirmPack = async (packId) => {
    try {
      await axios.post(`${API}/usage/confirm-pack`, { pack_id: packId });
      fetchUsage();
    } catch (err) {
      console.error('Error confirming pack:', err);
    }
  };

  const buyPack = async (packId) => {
    setBuying(packId);
    try {
      const res = await axios.post(`${API}/usage/buy-pack`, {
        pack_id: packId,
        origin_url: window.location.origin
      });
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      }
    } catch (err) {
      alert('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setBuying(null);
    }
  };

  if (isSuperAdmin || loading) return null;
  if (!usage) return null;

  const ai = usage.ai_messages;
  const leads = usage.leads;
  const packs = usage.packs_available || {};

  const aiPercentage = ai.unlimited ? 0 : Math.min(ai.percentage, 100);
  const leadsPercentage = Math.min(leads.percentage, 100);

  const getBarColor = (pct) => {
    if (pct >= 90) return '#ef4444';
    if (pct >= 70) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="usage-panel" data-testid="usage-panel">
      <h2 className="usage-title">
        <TrendingUp className="w-5 h-5" />
        Uso del Mes ({usage.period})
      </h2>

      <div className="usage-grid">
        {/* AI Messages */}
        <Card className="usage-card">
          <CardContent className="usage-card-content">
            <div className="usage-card-header">
              <div className="usage-card-icon ai">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="usage-card-label">Conversaciones IA</div>
                {ai.unlimited ? (
                  <div className="usage-card-value">Ilimitadas (key propia)</div>
                ) : (
                  <div className="usage-card-value">{ai.used.toLocaleString()} / {ai.total_available.toLocaleString()}</div>
                )}
              </div>
            </div>

            {!ai.unlimited && (
              <>
                <div className="usage-bar-container">
                  <div className="usage-bar" style={{ width: `${aiPercentage}%`, background: getBarColor(aiPercentage) }} />
                </div>
                <div className="usage-bar-labels">
                  <span>{aiPercentage}% usado</span>
                  <span>{(ai.total_available - ai.used).toLocaleString()} disponibles</span>
                </div>

                {ai.extra_balance > 0 && (
                  <div className="usage-extra-badge">
                    <Zap className="w-3 h-3" /> {ai.extra_balance.toLocaleString()} mensajes extra activos
                  </div>
                )}

                {ai.overage > 0 && (
                  <div className="usage-overage-alert">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{ai.overage} mensajes en excedente (${ai.overage_cost} USD a ${ai.overage_rate}/msg)</span>
                  </div>
                )}

                {aiPercentage >= 80 && (
                  <div className="usage-warning">
                    <Info className="w-3.5 h-3.5" />
                    <span>Te quedan pocas conversaciones. Compra un pack extra para no quedarte sin IA.</span>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Leads */}
        <Card className="usage-card">
          <CardContent className="usage-card-content">
            <div className="usage-card-header">
              <div className="usage-card-icon leads">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <div className="usage-card-label">Leads del mes</div>
                <div className="usage-card-value">{leads.used.toLocaleString()} / {leads.limit.toLocaleString()}</div>
              </div>
            </div>
            <div className="usage-bar-container">
              <div className="usage-bar" style={{ width: `${leadsPercentage}%`, background: getBarColor(leadsPercentage) }} />
            </div>
            <div className="usage-bar-labels">
              <span>{leadsPercentage}% usado</span>
              <span>{(leads.limit - leads.used).toLocaleString()} disponibles</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Buy Packs */}
      {!ai.unlimited && (
        <Card className="usage-packs" data-testid="usage-packs">
          <CardHeader>
            <CardTitle className="usage-packs-title">
              <ShoppingCart className="w-4 h-4" />
              Comprar mensajes IA extra
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="usage-packs-grid">
              {Object.entries(packs).map(([id, pack]) => (
                <div key={id} className="usage-pack-card">
                  <div className="usage-pack-info">
                    <span className="usage-pack-name">{pack.name}</span>
                    <span className="usage-pack-price">${pack.price} USD</span>
                  </div>
                  <Button 
                    size="sm" 
                    onClick={() => buyPack(id)} 
                    disabled={buying === id}
                    data-testid={`buy-${id}`}
                  >
                    {buying === id ? 'Procesando...' : 'Comprar'}
                  </Button>
                </div>
              ))}
            </div>
            <p className="usage-packs-note">
              Los mensajes extra se suman a tu balance del mes actual. Si excedes tu limite sin comprar pack, se cobra automaticamente a ${ai.overage_rate}/mensaje.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
