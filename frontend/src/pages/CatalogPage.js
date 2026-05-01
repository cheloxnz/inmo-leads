import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Plus, Trash2, Pencil, Package, Tag, DollarSign,
  Send, X, Search, Filter, Sparkles, Globe, Copy,
  PackageX, AlertTriangle, CheckCircle2, Wand2, Replace
} from 'lucide-react';

// ---------------- Helpers ----------------
const getAvailability = (p) => {
  if (p?.active === false) return 'out_of_stock';
  const s = p?.stock_quantity;
  if (s === null || s === undefined) return 'no_tracking';
  if (s <= 0) return 'out_of_stock';
  if (s <= 3) return 'low_stock';
  return 'available';
};

const AvailabilityBadge = ({ product }) => {
  const status = getAvailability(product);
  if (status === 'out_of_stock') {
    return (
      <span className="catalog-badge catalog-badge-out" data-testid="badge-out-of-stock">
        <PackageX className="w-3 h-3" /> AGOTADO
      </span>
    );
  }
  if (status === 'low_stock') {
    return (
      <span className="catalog-badge catalog-badge-low" data-testid="badge-low-stock">
        <AlertTriangle className="w-3 h-3" /> Poco stock ({product.stock_quantity})
      </span>
    );
  }
  if (status === 'available') {
    return (
      <span className="catalog-badge catalog-badge-ok" data-testid="badge-in-stock">
        <CheckCircle2 className="w-3 h-3" /> Stock: {product.stock_quantity}
      </span>
    );
  }
  return null; // no_tracking: no mostramos badge
};

// ---------------- Main Page ----------------
export default function CatalogPage() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [filterCategory, setFilterCategory] = useState('');
  const [search, setSearch] = useState('');
  const [aiQuery, setAiQuery] = useState('');
  const [aiRecs, setAiRecs] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [publicLink, setPublicLink] = useState('');
  const [subsModalProduct, setSubsModalProduct] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const fetchProducts = useCallback(async () => {
    try {
      const url = filterCategory ? `${API}/catalog?category=${filterCategory}` : `${API}/catalog`;
      const res = await axios.get(url);
      setProducts(res.data);
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  }, [filterCategory]);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/catalog/categories`);
      setCategories(res.data);
    } catch (err) {
      console.error('Error:', err);
    }
  }, []);

  useEffect(() => { fetchProducts(); fetchCategories(); }, [fetchProducts, fetchCategories]);

  useEffect(() => {
    if (products.length > 0 && !publicLink) {
      const tid = products[0].tenant_id;
      if (tid) setPublicLink(`${window.location.origin}/p/catalogo/${tid}`);
    }
  }, [products, publicLink]);

  const handleAiRecommend = async (e) => {
    e.preventDefault();
    if (!aiQuery.trim()) return;
    setAiLoading(true);
    try {
      const res = await axios.post(`${API}/catalog/recommend`, { query: aiQuery, max_results: 3 });
      setAiRecs(res.data.recommendations || []);
      setAiEnabled(res.data.ai_enabled);
    } catch (err) {
      toast.error('Error en recomendaciones IA');
    } finally {
      setAiLoading(false);
    }
  };

  const copyPublicLink = () => {
    navigator.clipboard.writeText(publicLink);
    toast.success('Link publico copiado');
  };

  const handleDelete = async (product) => {
    if (!window.confirm(`Eliminar "${product.name}"?`)) return;
    try {
      await axios.delete(`${API}/catalog/${product.product_id}`);
      toast.success('Producto eliminado');
      fetchProducts();
    } catch (err) {
      toast.error('Error eliminando producto');
    }
  };

  // 1-click toggle: marcar como AGOTADO o reponer
  const handleToggleStock = async (product) => {
    const isOut = getAvailability(product) === 'out_of_stock';
    const newStock = isOut ? 10 : 0; // reponer a 10 o marcar agotado
    try {
      await axios.patch(`${API}/catalog/products/${product.product_id}/stock`, {
        stock_quantity: newStock,
      });
      toast.success(isOut ? 'Producto repuesto (stock: 10)' : 'Marcado como AGOTADO');
      fetchProducts();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error actualizando stock');
    }
  };

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="catalog-page" data-testid="catalog-page">
      <div className="catalog-header">
        <div>
          <h1>Catalogo</h1>
          <p>{products.length} productos</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Button
            variant="outline"
            onClick={() => setPreviewOpen(true)}
            data-testid="btn-substitute-preview"
            title="Probar sustitución IA"
          >
            <Wand2 className="w-4 h-4 mr-1" /> Probar sustitución
          </Button>
          <Button onClick={() => { setEditingProduct(null); setShowForm(true); }} data-testid="btn-add-product">
            <Plus className="w-4 h-4 mr-1" /> Nuevo Producto
          </Button>
        </div>
      </div>

      {/* Public link + AI preview */}
      {products.length > 0 && (
        <div className="catalog-pro-panel" data-testid="catalog-pro-panel">
          <div className="catalog-pro-row">
            <div className="catalog-pro-link">
              <Globe className="w-4 h-4" />
              <span className="catalog-pro-label">Link publico:</span>
              <code data-testid="catalog-public-link">{publicLink}</code>
              <button onClick={copyPublicLink} data-testid="catalog-copy-link" title="Copiar">
                <Copy className="w-3 h-3" />
              </button>
              <a href={publicLink} target="_blank" rel="noopener noreferrer" className="catalog-pro-open">Abrir</a>
            </div>
          </div>
          <form className="catalog-pro-row catalog-ai-form" onSubmit={handleAiRecommend}>
            <Sparkles className="w-4 h-4" />
            <input
              placeholder="Preview IA: que buscaria un cliente? Ej: casa para familia..."
              value={aiQuery}
              onChange={e => setAiQuery(e.target.value)}
              data-testid="catalog-ai-input"
            />
            <Button type="submit" disabled={aiLoading} data-testid="catalog-ai-submit" size="sm">
              {aiLoading ? '...' : 'Probar IA'}
            </Button>
            {aiRecs.length > 0 && (
              <button type="button" onClick={() => { setAiRecs([]); setAiQuery(''); }} className="catalog-ai-clear">
                <X className="w-3 h-3" />
              </button>
            )}
          </form>
          {aiRecs.length > 0 && (
            <div className="catalog-ai-result" data-testid="catalog-ai-result">
              <strong>Top {aiRecs.length} recomendados{!aiEnabled ? ' (fallback, IA no configurada)' : ''}:</strong>
              <ul>
                {aiRecs.map(p => (
                  <li key={p.product_id}>{p.name} {p.price ? `- $${p.price}` : ''} {p.category ? `(${p.category})` : ''}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="catalog-toolbar">
        <div className="catalog-search">
          <Search className="w-4 h-4" />
          <input placeholder="Buscar producto..." value={search} onChange={e => setSearch(e.target.value)} data-testid="catalog-search" />
        </div>
        <div className="catalog-filter">
          <Filter className="w-4 h-4" />
          <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} data-testid="catalog-filter">
            <option value="">Todas las categorias</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* Product Form */}
      {showForm && (
        <ProductForm
          product={editingProduct}
          onSaved={() => { setShowForm(false); fetchProducts(); fetchCategories(); }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* Product Grid */}
      <div className="catalog-grid">
        {loading ? (
          <div className="catalog-empty">Cargando...</div>
        ) : filteredProducts.length === 0 ? (
          <div className="catalog-empty">
            {search || filterCategory ? 'No se encontraron productos' : 'No hay productos. Agrega el primero.'}
          </div>
        ) : (
          filteredProducts.map(product => {
            const isOut = getAvailability(product) === 'out_of_stock';
            return (
              <Card
                key={product.product_id || product.name}
                className={`catalog-product-card ${isOut ? 'catalog-product-card-out' : ''}`}
                data-testid={`product-${product.name}`}
              >
                <CardContent className="catalog-product-content">
                  {product.image_url ? (
                    <div className="catalog-product-img" style={{ backgroundImage: `url(${product.image_url})` }}>
                      {isOut && <div className="catalog-product-out-overlay">AGOTADO</div>}
                    </div>
                  ) : (
                    <div className="catalog-product-img catalog-product-img-placeholder">
                      <Package className="w-8 h-8" />
                      {isOut && <div className="catalog-product-out-overlay">AGOTADO</div>}
                    </div>
                  )}
                  <div className="catalog-product-info">
                    <div className="catalog-product-info-head">
                      <h3>{product.name}</h3>
                      <AvailabilityBadge product={product} />
                    </div>
                    {product.description && <p className="catalog-product-desc">{product.description}</p>}
                    <div className="catalog-product-meta">
                      {product.price > 0 && (
                        <span className="catalog-product-price">
                          <DollarSign className="w-3 h-3" /> {product.price} {product.currency}
                        </span>
                      )}
                      {product.category && (
                        <span className="catalog-product-cat">
                          <Tag className="w-3 h-3" /> {product.category}
                        </span>
                      )}
                      {product.substitute_product_ids?.length > 0 && (
                        <span className="catalog-product-subs" title="Sustitutos manuales configurados">
                          <Replace className="w-3 h-3" /> {product.substitute_product_ids.length} sustituto(s)
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="catalog-product-actions">
                    <button
                      onClick={() => handleToggleStock(product)}
                      title={isOut ? 'Reponer stock' : 'Marcar como AGOTADO'}
                      data-testid={`btn-toggle-stock-${product.product_id}`}
                      className={isOut ? 'catalog-action-restock' : 'catalog-action-out'}
                    >
                      {isOut ? <CheckCircle2 className="w-4 h-4" /> : <PackageX className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => setSubsModalProduct(product)}
                      title="Configurar sustitutos"
                      data-testid={`btn-substitutes-${product.product_id}`}
                    >
                      <Replace className="w-4 h-4" />
                    </button>
                    <button onClick={() => { setEditingProduct(product); setShowForm(true); }} title="Editar">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(product)} title="Eliminar">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      {/* Substitutes Modal */}
      {subsModalProduct && (
        <SubstitutesModal
          product={subsModalProduct}
          allProducts={products}
          onSaved={() => { setSubsModalProduct(null); fetchProducts(); }}
          onClose={() => setSubsModalProduct(null)}
        />
      )}

      {/* Substitute Preview Modal */}
      {previewOpen && (
        <SubstitutePreviewModal onClose={() => setPreviewOpen(false)} />
      )}
    </div>
  );
}

// ---------------- Product Form ----------------
function ProductForm({ product, onSaved, onCancel }) {
  const [form, setForm] = useState({
    name: product?.name || '',
    description: product?.description || '',
    price: product?.price || '',
    currency: product?.currency || 'USD',
    category: product?.category || '',
    image_url: product?.image_url || '',
    stock_quantity: product?.stock_quantity ?? '',
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Nombre es requerido'); return; }
    setSaving(true);
    try {
      const stockRaw = form.stock_quantity;
      const stockParsed = stockRaw === '' || stockRaw === null ? null : parseInt(stockRaw, 10);
      const data = {
        ...form,
        price: parseFloat(form.price) || 0,
        stock_quantity: Number.isNaN(stockParsed) ? null : stockParsed,
      };
      if (product) {
        await axios.put(`${API}/catalog/${product.product_id}`, data);
        // Si el usuario tocó el stock, usar el endpoint dedicado para que sincronice active
        if (product.stock_quantity !== data.stock_quantity) {
          await axios.patch(`${API}/catalog/products/${product.product_id}/stock`, {
            stock_quantity: data.stock_quantity,
          });
        }
        toast.success('Producto actualizado');
      } else {
        await axios.post(`${API}/catalog`, data);
        toast.success('Producto creado');
      }
      onSaved();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando producto');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="catalog-form" data-testid="product-form">
      <CardHeader>
        <CardTitle className="text-sm">{product ? 'Editar Producto' : 'Nuevo Producto'}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="catalog-form-grid">
            <div className="catalog-form-field">
              <label>Nombre *</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required data-testid="input-product-name" />
            </div>
            <div className="catalog-form-field">
              <label>Categoria</label>
              <input value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} placeholder="Ej: Departamentos, Servicios..." data-testid="input-product-category" />
            </div>
            <div className="catalog-form-field">
              <label>Precio</label>
              <input type="number" step="0.01" value={form.price} onChange={e => setForm({ ...form, price: e.target.value })} data-testid="input-product-price" />
            </div>
            <div className="catalog-form-field">
              <label>Moneda</label>
              <select value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}>
                <option value="USD">USD</option>
                <option value="ARS">ARS</option>
                <option value="MXN">MXN</option>
                <option value="COP">COP</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
            <div className="catalog-form-field">
              <label>
                Stock disponible
                <span className="catalog-form-hint"> (vacío = sin tracking; 0 = AGOTADO)</span>
              </label>
              <input
                type="number"
                step="1"
                min="0"
                value={form.stock_quantity}
                onChange={e => setForm({ ...form, stock_quantity: e.target.value })}
                placeholder="Ej: 10 (o vacío)"
                data-testid="input-product-stock"
              />
            </div>
            <div className="catalog-form-field full">
              <label>Descripcion</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} data-testid="input-product-desc" />
            </div>
            <div className="catalog-form-field full">
              <label>URL de imagen (opcional)</label>
              <input value={form.image_url} onChange={e => setForm({ ...form, image_url: e.target.value })} placeholder="https://..." />
            </div>
          </div>
          <div className="catalog-form-actions">
            <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button type="submit" disabled={saving} data-testid="btn-save-product">{saving ? 'Guardando...' : 'Guardar'}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// ---------------- Substitutes Modal ----------------
function SubstitutesModal({ product, allProducts, onSaved, onClose }) {
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

// ---------------- Substitute Preview Modal ----------------
function SubstitutePreviewModal({ onClose }) {
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
