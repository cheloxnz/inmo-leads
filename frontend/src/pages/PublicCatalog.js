import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Package, Tag, DollarSign, Search, Sparkles, MessageCircle } from 'lucide-react';
import './PublicCatalog.css';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function PublicCatalog() {
  const { tenantId } = useParams();
  const [searchParams] = useSearchParams();
  const isEmbed = searchParams.get('embed') === '1';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [recLoading, setRecLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');

  const fetchCatalog = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND}/api/public/catalog/${tenantId}`);
      setData(res.data);
      // SEO/branding: setear document.title con el tenant
      if (res.data?.tenant?.business_name) {
        document.title = `${res.data.tenant.business_name} - Catalogo`;
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Catalogo no disponible');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { fetchCatalog(); }, [fetchCatalog]);

  const handleRecommend = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setRecLoading(true);
    try {
      const res = await axios.post(`${BACKEND}/api/public/catalog/${tenantId}/recommend`, { query, max_results: 3 });
      setRecommendations(res.data.recommendations || []);
    } catch (err) {
      setRecommendations([]);
    } finally {
      setRecLoading(false);
    }
  };

  const openWhatsApp = (product) => {
    const phone = (data?.tenant?.whatsapp_phone || '').replace(/\D/g, '');
    if (!phone) return;
    const msg = encodeURIComponent(`Hola! Me interesa el producto: ${product.name}`);
    window.open(`https://wa.me/${phone}?text=${msg}`, '_blank');
  };

  if (loading) {
    return <div className="public-catalog-root"><div className="pc-loading">Cargando catalogo...</div></div>;
  }
  if (error) {
    return <div className="public-catalog-root"><div className="pc-error">{error}</div></div>;
  }
  if (!data) return null;

  const filtered = (data.products || []).filter(p =>
    !filterCategory || p.category === filterCategory
  );
  const displayProducts = recommendations.length > 0 ? recommendations : filtered;

  return (
    <div className={`public-catalog-root ${isEmbed ? 'pc-embed' : ''}`} data-testid="public-catalog">
      {!isEmbed && (
        <header className="pc-header">
          <h1>{data.tenant.business_name || data.tenant.name}</h1>
          {data.tenant.business_tagline && <p>{data.tenant.business_tagline}</p>}
        </header>
      )}

      <form className="pc-ai-search" onSubmit={handleRecommend} data-testid="pc-ai-form">
        <div className="pc-ai-input">
          <Sparkles className="w-4 h-4" />
          <input
            type="text"
            placeholder="Describi lo que buscas (IA)... ej: casa para familia con jardin"
            value={query}
            onChange={e => setQuery(e.target.value)}
            data-testid="pc-ai-input"
          />
          <button type="submit" disabled={recLoading} data-testid="pc-ai-submit">
            {recLoading ? 'Buscando...' : 'Recomendar'}
          </button>
        </div>
        {recommendations.length > 0 && (
          <button
            type="button"
            className="pc-ai-clear"
            onClick={() => { setRecommendations([]); setQuery(''); }}
            data-testid="pc-ai-clear"
          >Ver todo el catalogo</button>
        )}
      </form>

      {recommendations.length === 0 && data.categories?.length > 0 && (
        <div className="pc-filters">
          <button className={!filterCategory ? 'active' : ''} onClick={() => setFilterCategory('')}>
            Todos
          </button>
          {data.categories.map(c => (
            <button
              key={c}
              className={filterCategory === c ? 'active' : ''}
              onClick={() => setFilterCategory(c)}
            >
              <Tag className="w-3 h-3" /> {c}
            </button>
          ))}
        </div>
      )}

      <div className="pc-grid" data-testid="pc-grid">
        {displayProducts.length === 0 ? (
          <div className="pc-empty">No hay productos para mostrar</div>
        ) : (
          displayProducts.map(product => (
            <article key={product.product_id || product.name} className="pc-card" data-testid={`pc-product-${product.product_id}`}>
              {product.image_url ? (
                <div className="pc-card-img" style={{ backgroundImage: `url(${product.image_url})` }} />
              ) : (
                <div className="pc-card-img pc-card-img-ph"><Package className="w-10 h-10" /></div>
              )}
              <div className="pc-card-body">
                <h3>{product.name}</h3>
                {product.description && <p>{product.description}</p>}
                <div className="pc-card-meta">
                  {product.price > 0 && (
                    <span className="pc-price"><DollarSign className="w-3 h-3" />{product.price} {product.currency}</span>
                  )}
                  {product.category && (
                    <span className="pc-cat"><Tag className="w-3 h-3" />{product.category}</span>
                  )}
                </div>
                {data.tenant.whatsapp_phone && (
                  <button className="pc-card-cta" onClick={() => openWhatsApp(product)} data-testid={`pc-wa-${product.product_id}`}>
                    <MessageCircle className="w-4 h-4" /> Consultar por WhatsApp
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </div>

      {!isEmbed && (
        <footer className="pc-footer">
          Powered by <strong>InmoBot AI</strong>
        </footer>
      )}
    </div>
  );
}
