import React, { useState } from 'react';
import axios from 'axios';
import { API } from '../../App';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { X, Send, Wand2, PackageX } from 'lucide-react';

export default function SubstitutePreviewModal({ onClose }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleTest = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await axios.post(`${API}/catalog/substitute-preview`, { query: query.trim() });
      setResult(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error en preview');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="catalog-modal-backdrop" data-testid="preview-modal">
      <div className="catalog-modal">
        <div className="catalog-modal-head">
          <div>
            <h3><Wand2 className="w-5 h-5" /> Probar sustitución IA</h3>
            <p className="catalog-modal-sub">
              Simulá lo que un cliente preguntaría por WhatsApp sobre un producto agotado. Te mostramos qué responderá el bot.
            </p>
          </div>
          <button onClick={onClose} className="catalog-modal-close"><X className="w-4 h-4" /></button>
        </div>
        <div className="catalog-modal-body">
          <form onSubmit={handleTest} className="catalog-preview-form">
            <input
              placeholder='Ej: "tienen el iPhone 15?" o "quiero el producto X"'
              value={query}
              onChange={e => setQuery(e.target.value)}
              data-testid="preview-query-input"
              autoFocus
            />
            <Button type="submit" disabled={loading} data-testid="btn-run-preview">
              <Send className="w-4 h-4 mr-1" />
              {loading ? 'Probando...' : 'Probar'}
            </Button>
          </form>

          {result && (
            <div className="catalog-preview-result" data-testid="preview-result">
              {!result.out_of_stock_product ? (
                <div className="catalog-preview-empty">
                  <p><strong>No se detectó match con ningún producto agotado.</strong></p>
                  <p className="catalog-preview-sub">
                    {result.reason || 'Asegurate de que existe un producto agotado (stock=0) con un nombre similar a la query.'}
                  </p>
                </div>
              ) : (
                <>
                  <div className="catalog-preview-block">
                    <span className="catalog-preview-label">Producto agotado detectado:</span>
                    <strong className="catalog-preview-out">
                      <PackageX className="w-4 h-4" /> {result.out_of_stock_product.name}
                    </strong>
                  </div>
                  <div className="catalog-preview-block">
                    <span className="catalog-preview-label">
                      Sustitutos propuestos ({result.substitutes.length}):
                    </span>
                    {result.substitutes.length === 0 ? (
                      <em className="catalog-preview-sub">Sin sustitutos disponibles en este momento.</em>
                    ) : (
                      <ul className="catalog-preview-subs">
                        {result.substitutes.map((s, i) => (
                          <li key={s.product_id}>
                            <strong>#{i + 1} {s.name}</strong>
                            {s.price > 0 && <span> · ${s.price} {s.currency}</span>}
                            {s.category && <span> · {s.category}</span>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="catalog-preview-block">
                    <span className="catalog-preview-label">Mensaje WhatsApp:</span>
                    <div className="catalog-preview-message" data-testid="preview-message">
                      {result.message || '(sin mensaje)'}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
