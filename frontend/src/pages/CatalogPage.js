import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Plus, Trash2, Pencil, Package, Tag, DollarSign,
  X, Search, Filter, Sparkles, Globe, Copy,
  PackageX, AlertTriangle, CheckCircle2, Wand2, Replace, Users, Upload
} from 'lucide-react';
import ProductForm from './catalog/ProductForm';
import SubstitutesModal from './catalog/SubstitutesModal';
import SubstitutePreviewModal from './catalog/SubstitutePreviewModal';
import WaitlistModal from './catalog/WaitlistModal';
import BulkImportModal from './catalog/BulkImportModal';

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
  return null;
};

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
  const [waitlistOpen, setWaitlistOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);

  const fetchProducts = useCallback(async () => {
    try {
      const url = filterCategory ? `${API}/catalog?category=${filterCategory}` : `${API}/catalog`;
      const res = await axios.get(url);
      setProducts(Array.isArray(res.data) ? res.data : (res.data.products || []));
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  }, [filterCategory]);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/catalog/categories`);
      setCategories(Array.isArray(res.data) ? res.data : (res.data.categories || []));
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

  const handleToggleStock = async (product) => {
    const isOut = getAvailability(product) === 'out_of_stock';
    const newStock = isOut ? 10 : 0;
    try {
      const res = await axios.patch(`${API}/catalog/products/${product.product_id}/stock`, {
        stock_quantity: newStock,
      });
      const notified = res.data?.notified_leads || 0;
      if (isOut && notified > 0) {
        toast.success(`Producto repuesto (stock: 10). Avisamos a ${notified} lead(s) que lo esperaban.`);
      } else {
        toast.success(isOut ? 'Producto repuesto (stock: 10)' : 'Marcado como AGOTADO');
      }
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
            onClick={() => setBulkImportOpen(true)}
            data-testid="btn-bulk-import"
            title="Importar catálogo desde CSV"
          >
            <Upload className="w-4 h-4 mr-1" /> Importar CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => setWaitlistOpen(true)}
            data-testid="btn-open-waitlist"
            title="Lista de espera de leads"
          >
            <Users className="w-4 h-4 mr-1" /> Lista de espera
          </Button>
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

      {showForm && (
        <ProductForm
          product={editingProduct}
          onSaved={() => { setShowForm(false); fetchProducts(); fetchCategories(); }}
          onCancel={() => setShowForm(false)}
        />
      )}

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

      {subsModalProduct && (
        <SubstitutesModal
          product={subsModalProduct}
          allProducts={products}
          onSaved={() => { setSubsModalProduct(null); fetchProducts(); }}
          onClose={() => setSubsModalProduct(null)}
        />
      )}

      {previewOpen && (
        <SubstitutePreviewModal onClose={() => setPreviewOpen(false)} />
      )}

      {waitlistOpen && (
        <WaitlistModal onClose={() => setWaitlistOpen(false)} />
      )}

      {bulkImportOpen && (
        <BulkImportModal
          onClose={() => setBulkImportOpen(false)}
          onImported={() => fetchProducts()}
        />
      )}
    </div>
  );
}
