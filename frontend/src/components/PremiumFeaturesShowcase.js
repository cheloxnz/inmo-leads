import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, Check, Lock, Zap } from 'lucide-react';

const CATEGORY_LABELS = {
  bot: 'Bot WhatsApp',
  dashboard: 'Dashboard',
  integrations: 'Integraciones',
  beta: 'Beta',
};

export default function PremiumFeaturesShowcase() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [contactOpen, setContactOpen] = useState(null);

  useEffect(() => {
    axios.get(`${API}/tenant/features-showcase`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data) return null;
  const { active = [], available = [] } = data;
  if (active.length === 0 && available.length === 0) return null;

  return (
    <Card className="pf-showcase-card" data-testid="premium-features-showcase">
      <CardHeader className="pf-showcase-header">
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5" style={{ color: '#8b5cf6' }} />
          Funcionalidades Premium
        </CardTitle>
        <div className="pf-showcase-count" data-testid="pf-count">
          {active.length} activas / {data.total} disponibles
        </div>
      </CardHeader>
      <CardContent className="pf-showcase-content">
        {active.length > 0 && (
          <div className="pf-showcase-section">
            <div className="pf-showcase-section-title">
              <Check className="w-4 h-4" /> Tus features activas
            </div>
            <div className="pf-showcase-grid">
              {active.map((f) => (
                <div key={f.key} className="pf-card pf-card-active" data-testid={`pf-active-${f.key}`}>
                  <div className="pf-card-cat">{CATEGORY_LABELS[f.category] || f.category}</div>
                  <div className="pf-card-label">
                    <Check className="w-3.5 h-3.5" /> {f.label}
                  </div>
                  <div className="pf-card-desc">{f.description}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {available.length > 0 && (
          <div className="pf-showcase-section">
            <div className="pf-showcase-section-title">
              <Lock className="w-4 h-4" /> Disponibles para activar
            </div>
            <div className="pf-showcase-grid">
              {available.map((f) => (
                <div key={f.key} className="pf-card pf-card-available" data-testid={`pf-available-${f.key}`}>
                  <div className="pf-card-cat">{CATEGORY_LABELS[f.category] || f.category}</div>
                  <div className="pf-card-label">{f.label}</div>
                  <div className="pf-card-desc">{f.description}</div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="pf-card-cta"
                    onClick={() => setContactOpen(f)}
                    data-testid={`pf-cta-${f.key}`}
                  >
                    <Zap className="w-3 h-3 mr-1" /> Solicitar activación
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {contactOpen && (
          <ContactModal feature={contactOpen} onClose={() => setContactOpen(null)} />
        )}
      </CardContent>
    </Card>
  );
}

function ContactModal({ feature, onClose }) {
  const subject = encodeURIComponent(`Activación de feature: ${feature.label}`);
  const body = encodeURIComponent(
    `Hola,\n\nQuisiera activar la feature "${feature.label}" (${feature.key}) en mi cuenta de InmoBot.\n\n${feature.description}\n\nGracias.`
  );
  return (
    <div className="pf-modal-overlay" onClick={onClose} data-testid="pf-contact-modal">
      <div className="pf-modal" onClick={(e) => e.stopPropagation()}>
        <h3 className="pf-modal-title">Activar: {feature.label}</h3>
        <p className="pf-modal-desc">{feature.description}</p>
        <p className="pf-modal-hint">
          Esta funcionalidad puede tener costo adicional según tu plan. Contactanos y te activamos en menos de 24hs.
        </p>
        <div className="pf-modal-actions">
          <Button variant="outline" onClick={onClose} data-testid="pf-modal-cancel">
            Cancelar
          </Button>
          <Button asChild data-testid="pf-modal-email">
            <a href={`mailto:soporte@inmobot.com?subject=${subject}&body=${body}`}>
              <Zap className="w-3.5 h-3.5 mr-1" /> Enviar solicitud
            </a>
          </Button>
        </div>
      </div>
    </div>
  );
}
