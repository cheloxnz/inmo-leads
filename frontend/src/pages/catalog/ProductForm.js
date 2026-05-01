import React, { useState } from 'react';
import axios from 'axios';
import { API } from '../../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export default function ProductForm({ product, onSaved, onCancel }) {
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
