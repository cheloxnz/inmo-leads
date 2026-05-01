import React, { useState } from 'react';
import axios from 'axios';
import { API } from '../../App';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { X, Search, Replace } from 'lucide-react';

export default function SubstitutesModal({ product, allProducts, onSaved, onClose }) {
  const [selected, setSelected] = useState(product.substitute_product_ids || []);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');

  const candidates = allProducts.filter(p =>
    p.product_id !== product.product_id &&
    (p.active !== false) &&
    (p.stock_quantity == null || p.stock_quantity > 0) &&
    (!search || p.name.toLowerCase().includes(search.toLowerCase()))
  );

  const toggle = (pid) => {
    setSelected(prev =>
      prev.includes(pid) ? prev.filter(x => x !== pid) : [...prev, pid].slice(0, 10)
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/catalog/products/${product.product_id}/substitutes`, {
        substitute_product_ids: selected,
      });
      toast.success(`${selected.length} sustituto(s) guardado(s)`);
      onSaved();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando sustitutos');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="catalog-modal-backdrop" data-testid="substitutes-modal">
      <div className="catalog-modal">
        <div className="catalog-modal-head">
          <div>
            <h3><Replace className="w-5 h-5" /> Sustitutos para "{product.name}"</h3>
            <p className="catalog-modal-sub">
              Cuando este producto esté agotado, el bot ofrecerá primero estos sustitutos (en orden de prioridad).
              Si no configurás ninguno, la IA elegirá automáticamente por categoría + precio.
            </p>
          </div>
          <button onClick={onClose} className="catalog-modal-close"><X className="w-4 h-4" /></button>
        </div>
        <div className="catalog-modal-body">
          <div className="catalog-search" style={{ marginBottom: '0.75rem' }}>
            <Search className="w-4 h-4" />
            <input
              placeholder="Buscar producto para agregar..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              data-testid="substitutes-search"
            />
          </div>
          <div className="catalog-subs-list">
            {candidates.length === 0 ? (
              <p className="catalog-empty-sm">No hay productos disponibles para usar como sustitutos.</p>
            ) : candidates.map(c => {
              const idx = selected.indexOf(c.product_id);
              const checked = idx >= 0;
              return (
                <label
                  key={c.product_id}
                  className={`catalog-sub-row ${checked ? 'catalog-sub-row-checked' : ''}`}
                  data-testid={`sub-option-${c.product_id}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(c.product_id)}
                  />
                  <div className="catalog-sub-info">
                    <strong>{c.name}</strong>
                    <span>
                      {c.price > 0 ? `$${c.price} ${c.currency || ''}` : ''}
                      {c.category ? ` · ${c.category}` : ''}
                    </span>
                  </div>
                  {checked && <span className="catalog-sub-order">#{idx + 1}</span>}
                </label>
              );
            })}
          </div>
        </div>
        <div className="catalog-modal-foot">
          <span className="catalog-modal-count">{selected.length}/10 seleccionados</span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="outline" onClick={onClose}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving} data-testid="btn-save-substitutes">
              {saving ? 'Guardando...' : 'Guardar sustitutos'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
