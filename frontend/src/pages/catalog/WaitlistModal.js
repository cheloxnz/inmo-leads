import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../../App';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { X, Users, Send, Loader2, Phone, Clock, PackageX } from 'lucide-react';

export default function WaitlistModal({ onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notifyingPid, setNotifyingPid] = useState(null);

  const fetchWaitlist = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/catalog/waitlist`);
      setData(res.data);
    } catch (err) {
      toast.error('Error cargando lista de espera');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchWaitlist(); }, [fetchWaitlist]);

  const handleNotifyNow = async (pid, productName) => {
    if (!window.confirm(
      `¿Enviar mensaje de "vuelve a estar disponible" ahora a todos los leads que esperaban "${productName}"? `
      + `(El producto debe estar con stock > 0 para que se dispare el envío)`
    )) return;
    setNotifyingPid(pid);
    try {
      const res = await axios.post(`${API}/catalog/waitlist/notify/${pid}`);
      const n = res.data?.notified_leads || 0;
      if (n > 0) {
        toast.success(`Avisados ${n} lead(s)`);
        fetchWaitlist();
      } else {
        toast.info('No se notificó a nadie. ¿El producto sigue agotado?');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error notificando');
    } finally {
      setNotifyingPid(null);
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  return (
    <div className="catalog-modal-backdrop" data-testid="waitlist-modal">
      <div className="catalog-modal" style={{ maxWidth: 760 }}>
        <div className="catalog-modal-head">
          <div>
            <h3><Users className="w-5 h-5" /> Lista de espera de productos</h3>
            <p className="catalog-modal-sub">
              Leads que preguntaron por productos agotados. Se les avisará automáticamente cuando repongas stock,
              o podés disparar el aviso manualmente con el botón "Avisar ahora".
            </p>
          </div>
          <button onClick={onClose} className="catalog-modal-close"><X className="w-4 h-4" /></button>
        </div>
        <div className="catalog-modal-body">
          {loading ? (
            <div className="catalog-empty"><Loader2 className="w-5 h-5 animate-spin" /> Cargando...</div>
          ) : !data || data.total_pending === 0 ? (
            <div className="waitlist-empty" data-testid="waitlist-empty">
              <Users className="w-10 h-10" />
              <p><strong>Nadie está esperando productos agotados.</strong></p>
              <p className="catalog-preview-sub">
                Cuando un lead pregunte por un producto agotado, aparecerá acá automáticamente.
              </p>
            </div>
          ) : (
            <>
              <div className="waitlist-stats">
                <div className="waitlist-stat">
                  <span className="waitlist-stat-num" data-testid="waitlist-total-pending">
                    {data.total_pending}
                  </span>
                  <span className="waitlist-stat-label">Leads esperando</span>
                </div>
                <div className="waitlist-stat">
                  <span className="waitlist-stat-num">{data.unique_products}</span>
                  <span className="waitlist-stat-label">Productos únicos</span>
                </div>
              </div>

              <div className="waitlist-list">
                {data.by_product.map(p => (
                  <div key={p.product_id} className="waitlist-product" data-testid={`waitlist-product-${p.product_id}`}>
                    <div className="waitlist-product-head">
                      <div>
                        <strong>{p.product_name || '(producto eliminado)'}</strong>
                        <div className="waitlist-product-meta">
                          {p.is_out_of_stock ? (
                            <span className="catalog-badge catalog-badge-out">
                              <PackageX className="w-3 h-3" /> AGOTADO
                            </span>
                          ) : (
                            <span className="catalog-badge catalog-badge-ok">
                              Stock: {p.stock_quantity ?? '—'}
                            </span>
                          )}
                          {p.price > 0 && <span className="waitlist-meta-item">${p.price} {p.currency}</span>}
                          {p.category && <span className="waitlist-meta-item">{p.category}</span>}
                        </div>
                      </div>
                      <div className="waitlist-product-actions">
                        <span className="waitlist-leads-count">
                          {p.leads_count} {p.leads_count === 1 ? 'lead' : 'leads'}
                        </span>
                        <Button
                          size="sm"
                          variant={p.is_out_of_stock ? 'outline' : 'default'}
                          disabled={p.is_out_of_stock || notifyingPid === p.product_id}
                          onClick={() => handleNotifyNow(p.product_id, p.product_name)}
                          data-testid={`btn-notify-${p.product_id}`}
                          title={p.is_out_of_stock
                            ? 'El producto sigue agotado. Reponé stock primero o usá el botón 1-click.'
                            : 'Enviar aviso ahora'}
                        >
                          {notifyingPid === p.product_id ? (
                            <><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Enviando...</>
                          ) : (
                            <><Send className="w-3 h-3 mr-1" /> Avisar ahora</>
                          )}
                        </Button>
                      </div>
                    </div>
                    <div className="waitlist-leads">
                      {p.leads.slice(0, 6).map((l, i) => (
                        <div key={i} className="waitlist-lead">
                          <Phone className="w-3 h-3" /> {l.lead_phone}
                          <span className="waitlist-lead-time">
                            <Clock className="w-3 h-3" /> {formatDate(l.asked_at)}
                          </span>
                        </div>
                      ))}
                      {p.leads.length > 6 && (
                        <div className="waitlist-lead waitlist-lead-more">
                          +{p.leads.length - 6} más
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
