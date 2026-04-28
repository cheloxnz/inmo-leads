import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Plus, Trash2, Pencil, Package, Tag, DollarSign,
  Image, Send, X, Search, Filter, Sparkles, Globe, Copy
} from 'lucide-react';

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

  // Compute public catalog link from tenant_id of first product (lazy)
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
        <Button onClick={() => { setEditingProduct(null); setShowForm(true); }} data-testid="btn-add-product">
          <Plus className="w-4 h-4 mr-1" /> Nuevo Producto
        </Button>
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
          filteredProducts.map(product => (
            <Card key={product.product_id || product.name} className="catalog-product-card" data-testid={`product-${product.name}`}>
              <CardContent className="catalog-product-content">
                {product.image_url ? (
                  <div className="catalog-product-img" style={{ backgroundImage: `url(${product.image_url})` }} />
                ) : (
                  <div className="catalog-product-img catalog-product-img-placeholder">
                    <Package className="w-8 h-8" />
                  </div>
                )}
                <div className="catalog-product-info">
                  <h3>{product.name}</h3>
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
                  </div>
                </div>
                <div className="catalog-product-actions">
                  <button onClick={() => { setEditingProduct(product); setShowForm(true); }} title="Editar">
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(product)} title="Eliminar">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}


function ProductForm({ product, onSaved, onCancel }) {
  const [form, setForm] = useState({
    name: product?.name || '',
    description: product?.description || '',
    price: product?.price || '',
    currency: product?.currency || 'USD',
    category: product?.category || '',
    image_url: product?.image_url || '',
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Nombre es requerido'); return; }
    setSaving(true);
    try {
      const data = { ...form, price: parseFloat(form.price) || 0 };
      if (product) {
        await axios.put(`${API}/catalog/${product.product_id}`, data);
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
            <Button type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
