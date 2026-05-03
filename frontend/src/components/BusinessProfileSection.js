import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Save, Plus, X, Building2, Info } from 'lucide-react';

/**
 * Panel donde el admin del tenant carga los DATOS DEL NEGOCIO que
 * el bot usa para responder preguntas sin inventar.
 *
 * NOTA TÉCNICA: Field y Switch están definidos FUERA del componente
 * principal (no como sub-funciones internas) para evitar que React
 * los re-cree en cada render — eso causaba pérdida de foco al tipear.
 */

// ============================================================
// Sub-componentes definidos fuera (críticos para el foco)
// ============================================================

const FieldInput = React.memo(function FieldInput({
  field, label, placeholder, type = 'text', value, onChange, full = false,
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : 'auto' }}>
      <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
        {label}
      </label>
      <Input
        type={type}
        value={value || ''}
        onChange={e => onChange(field, e.target.value)}
        placeholder={placeholder}
        data-testid={`bp-${field}`}
      />
    </div>
  );
});

const FieldTextarea = React.memo(function FieldTextarea({
  field, label, placeholder, value, onChange, full = false,
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : 'auto' }}>
      <label style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
        {label}
      </label>
      <Textarea
        value={value || ''}
        onChange={e => onChange(field, e.target.value)}
        placeholder={placeholder}
        rows={2}
        data-testid={`bp-${field}`}
      />
    </div>
  );
});

const SwitchRow = React.memo(function SwitchRow({ field, label, checked, onChange }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '6px 0', fontSize: 13 }}>
      <input
        type="checkbox"
        checked={!!checked}
        onChange={e => onChange(field, e.target.checked)}
        data-testid={`bp-${field}`}
        style={{ width: 18, height: 18 }}
      />
      <span>{label}</span>
    </label>
  );
});

const SectionHeader = ({ children }) => (
  <h4 style={{
    fontSize: 13, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase',
    letterSpacing: '0.05em', marginBottom: 8,
  }}>{children}</h4>
);

// ============================================================
// Componente principal
// ============================================================

export default function BusinessProfileSection() {
  const [data, setData] = useState({
    business_name: '', business_description: '', industry: '',
    address: '', city: '', phone: '', email: '', website: '',
    google_maps_url: '', business_hours: '',
    accepts_cash: false, accepts_credit_card: false, accepts_debit_card: false,
    accepts_transfer: false, accepts_crypto: false, accepts_mercadopago: false,
    payment_notes: '',
    offers_delivery: false, delivery_zones: '', delivery_cost: '',
    offers_pickup: false, offers_in_person: false, has_parking: false,
    return_policy: '', warranty_policy: '', appointment_required: false,
    not_offered: '',
    custom_faqs: [],
    bot_tone: 'neutro',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newFaq, setNewFaq] = useState({ question: '', answer: '' });

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await axios.get(`${API}/business-profile`);
      const { exists, tenant_id, ...rest } = res.data;
      setData(prev => ({ ...prev, ...rest }));
    } catch (err) {
      console.error('Error fetching profile:', err);
    } finally {
      setLoading(false);
    }
  };

  // useCallback no es estrictamente necesario porque uso React.memo en hijos
  // y la función se pasa solo a hijos memo. setData con función actualizadora
  // evita la dependencia.
  const handleChange = (field, value) => {
    setData(prev => ({ ...prev, [field]: value }));
  };

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/business-profile`, data);
      toast.success('Datos del negocio guardados — el bot ya los usa para responder');
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const addFaq = () => {
    if (!newFaq.question.trim() || !newFaq.answer.trim()) return;
    setData(prev => ({ ...prev, custom_faqs: [...(prev.custom_faqs || []), { ...newFaq }] }));
    setNewFaq({ question: '', answer: '' });
  };

  const removeFaq = (idx) => {
    setData(prev => ({
      ...prev,
      custom_faqs: (prev.custom_faqs || []).filter((_, i) => i !== idx),
    }));
  };

  if (loading) {
    return <Card><CardContent style={{ padding: 20 }}>Cargando...</CardContent></Card>;
  }

  return (
    <Card data-testid="business-profile-section">
      <CardHeader>
        <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Building2 className="w-5 h-5" />
          Datos del Negocio
        </CardTitle>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 8, padding: '10px 14px', background: '#eff6ff', borderRadius: 8, border: '1px solid #bfdbfe', fontSize: 12, color: '#1e3a8a', lineHeight: 1.5 }}>
          <Info className="w-4 h-4 flex-shrink-0" style={{ marginTop: 2 }} />
          <div>
            El bot va a usar TODA esta info para responder preguntas. Si un campo está vacío,
            el bot dirá honestamente "no tengo esa info, te paso con un humano" en lugar
            de inventar respuestas. Cuanto más completo, más útil el bot.
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <SectionHeader>Identidad</SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, marginBottom: 20 }}>
          <FieldInput field="business_name" label="Nombre del negocio" placeholder="Inmobiliaria López" value={data.business_name} onChange={handleChange} />
          <FieldInput field="industry" label="Rubro / Industria" placeholder="Inmobiliaria, panadería, clínica..." value={data.industry} onChange={handleChange} />
          <FieldTextarea field="business_description" label="Descripción corta" placeholder="Vendemos y alquilamos propiedades en CABA desde 1995" value={data.business_description} onChange={handleChange} full />
        </div>

        <SectionHeader>Ubicación y contacto</SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, marginBottom: 20 }}>
          <FieldInput field="address" label="Dirección" placeholder="Av. Corrientes 1234, Piso 5" value={data.address} onChange={handleChange} />
          <FieldInput field="city" label="Ciudad" placeholder="CABA" value={data.city} onChange={handleChange} />
          <FieldInput field="phone" label="Teléfono" placeholder="+54 9 11 1234-5678" value={data.phone} onChange={handleChange} />
          <FieldInput field="email" label="Email" placeholder="info@negocio.com" value={data.email} onChange={handleChange} />
          <FieldInput field="website" label="Sitio web" placeholder="https://negocio.com" value={data.website} onChange={handleChange} />
          <FieldInput field="google_maps_url" label="Google Maps URL" placeholder="https://maps.google.com/..." value={data.google_maps_url} onChange={handleChange} />
          <FieldInput field="business_hours" label="Horarios" placeholder="Lun-Vie 9-18, Sáb 10-14, Dom cerrado" value={data.business_hours} onChange={handleChange} full />
        </div>

        <SectionHeader>Medios de pago</SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginBottom: 12 }}>
          <SwitchRow field="accepts_cash" label="Efectivo" checked={data.accepts_cash} onChange={handleChange} />
          <SwitchRow field="accepts_credit_card" label="Tarjeta de crédito" checked={data.accepts_credit_card} onChange={handleChange} />
          <SwitchRow field="accepts_debit_card" label="Tarjeta de débito" checked={data.accepts_debit_card} onChange={handleChange} />
          <SwitchRow field="accepts_transfer" label="Transferencia" checked={data.accepts_transfer} onChange={handleChange} />
          <SwitchRow field="accepts_mercadopago" label="Mercado Pago" checked={data.accepts_mercadopago} onChange={handleChange} />
          <SwitchRow field="accepts_crypto" label="Crypto" checked={data.accepts_crypto} onChange={handleChange} />
        </div>
        <div style={{ marginBottom: 20 }}>
          <FieldTextarea field="payment_notes" label="Notas de pago" placeholder="3 cuotas sin interés, descuento 10% pago en efectivo, etc." value={data.payment_notes} onChange={handleChange} full />
        </div>

        <SectionHeader>Modalidades de atención</SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginBottom: 14 }}>
          <SwitchRow field="offers_delivery" label="Hacemos delivery" checked={data.offers_delivery} onChange={handleChange} />
          <SwitchRow field="offers_pickup" label="Retiro en local" checked={data.offers_pickup} onChange={handleChange} />
          <SwitchRow field="offers_in_person" label="Atención presencial" checked={data.offers_in_person} onChange={handleChange} />
          <SwitchRow field="has_parking" label="Tenemos estacionamiento" checked={data.has_parking} onChange={handleChange} />
          <SwitchRow field="appointment_required" label="Se atiende con cita previa" checked={data.appointment_required} onChange={handleChange} />
        </div>
        {data.offers_delivery && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, marginBottom: 20 }}>
            <FieldInput field="delivery_zones" label="Zonas de delivery" placeholder="CABA y GBA Norte" value={data.delivery_zones} onChange={handleChange} />
            <FieldInput field="delivery_cost" label="Costo de envío" placeholder="$500 fijo o gratis sobre $5000" value={data.delivery_cost} onChange={handleChange} />
          </div>
        )}

        <SectionHeader>Políticas</SectionHeader>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, marginBottom: 20 }}>
          <FieldTextarea field="return_policy" label="Cambios y devoluciones" placeholder="30 días con ticket" value={data.return_policy} onChange={handleChange} />
          <FieldTextarea field="warranty_policy" label="Garantía" placeholder="6 meses, fallas de fábrica" value={data.warranty_policy} onChange={handleChange} />
          <FieldTextarea field="not_offered" label="❗ NO ofrecemos / NO hacemos" placeholder="Ej: No hacemos envíos al exterior. No atendemos los domingos." value={data.not_offered} onChange={handleChange} full />
        </div>

        <SectionHeader>Preguntas frecuentes específicas</SectionHeader>
        <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
          Casos específicos del negocio que el bot debería saber responder con texto exacto.
        </p>
        {(data.custom_faqs || []).map((faq, idx) => (
          <div key={idx} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-start', padding: 10, background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb' }}>
            <div style={{ flex: 1, fontSize: 13 }}>
              <div><strong>Q:</strong> {faq.question}</div>
              <div style={{ marginTop: 4, color: '#374151' }}><strong>A:</strong> {faq.answer}</div>
            </div>
            <Button size="sm" variant="outline" onClick={() => removeFaq(idx)} data-testid={`bp-remove-faq-${idx}`}>
              <X className="w-3 h-3" />
            </Button>
          </div>
        ))}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 8, alignItems: 'flex-start', marginBottom: 20 }}>
          <Input
            placeholder="¿Pregunta?"
            value={newFaq.question}
            onChange={e => setNewFaq(prev => ({ ...prev, question: e.target.value }))}
            data-testid="bp-new-faq-q"
          />
          <Input
            placeholder="Respuesta"
            value={newFaq.answer}
            onChange={e => setNewFaq(prev => ({ ...prev, answer: e.target.value }))}
            data-testid="bp-new-faq-a"
          />
          <Button size="sm" variant="outline" onClick={addFaq} disabled={!newFaq.question.trim() || !newFaq.answer.trim()} data-testid="bp-add-faq">
            <Plus className="w-4 h-4" />
          </Button>
        </div>

        <SectionHeader>Tono del bot</SectionHeader>
        <select
          value={data.bot_tone || 'neutro'}
          onChange={e => handleChange('bot_tone', e.target.value)}
          data-testid="bp-bot_tone"
          style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13, marginBottom: 20 }}
        >
          <option value="neutro">Neutro y profesional</option>
          <option value="casual">Casual y cercano</option>
          <option value="formal">Formal y serio</option>
          <option value="vendedor">Vendedor y entusiasta</option>
        </select>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 12, borderTop: '1px solid #e5e7eb' }}>
          <Button onClick={save} disabled={saving} data-testid="bp-save" style={{ background: '#16a34a', color: '#fff' }}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Guardando...' : 'Guardar datos del negocio'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
