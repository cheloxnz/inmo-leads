import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Brain, Plus, Trash2, Edit2, Check, X, Power, PowerOff, Search } from 'lucide-react';

/**
 * Panel de gestión de respuestas aprendidas del bot.
 *
 * Lista todas las learned_responses del tenant con:
 * - Pregunta + respuesta + uses count
 * - Edit inline (pregunta y/o respuesta)
 * - Toggle active/inactive
 * - Delete permanente
 * - Add manual (sin esperar a que un asesor lo guarde desde un chat)
 * - Tester de match (probar si una pregunta hace hit)
 */
export default function BotLearningPanel() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newQ, setNewQ] = useState('');
  const [newA, setNewA] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editQ, setEditQ] = useState('');
  const [editA, setEditA] = useState('');
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/bot-learning?include_inactive=true`);
      setItems(res.data.items || []);
    } catch (err) {
      console.error('Error:', err);
      toast.error('Error cargando respuestas aprendidas');
    } finally {
      setLoading(false);
    }
  };

  const addNew = async () => {
    if (!newQ.trim() || !newA.trim()) return;
    try {
      await axios.post(`${API}/bot-learning`, { question: newQ.trim(), answer: newA.trim() });
      toast.success('Respuesta agregada');
      setNewQ(''); setNewA(''); setShowAdd(false);
      fetchAll();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  const startEdit = (item) => {
    setEditingId(item.id);
    setEditQ(item.question);
    setEditA(item.answer);
  };

  const saveEdit = async (id) => {
    try {
      await axios.put(`${API}/bot-learning/${id}`, { question: editQ.trim(), answer: editA.trim() });
      toast.success('Actualizado');
      setEditingId(null);
      fetchAll();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  const toggleActive = async (item) => {
    try {
      await axios.put(`${API}/bot-learning/${item.id}`, { active: !item.active });
      fetchAll();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  const remove = async (id) => {
    if (!window.confirm('¿Borrar definitivamente esta respuesta aprendida?')) return;
    try {
      await axios.delete(`${API}/bot-learning/${id}`);
      toast.success('Eliminada');
      fetchAll();
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    }
  };

  const testMatch = async () => {
    if (!testQuery.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await axios.post(`${API}/bot-learning/test`, { message: testQuery.trim() });
      setTestResult(res.data);
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card data-testid="bot-learning-panel">
      <CardHeader>
        <CardTitle style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Brain className="w-5 h-5" />
          Cerebro del Bot
        </CardTitle>
        <div style={{ marginTop: 8, padding: '10px 14px', background: '#f0fdf4', borderRadius: 8, border: '1px solid #bbf7d0', fontSize: 12, color: '#14532d', lineHeight: 1.5 }}>
          Cada vez que un asesor escribe una buena respuesta y la marca como
          "Enseñar al bot" desde el chat, se guarda acá. El bot la va a usar
          literal cuando alguien haga una pregunta similar — sin gastar tokens
          de IA y con tono más humano.
        </div>
      </CardHeader>
      <CardContent>
        {/* Tester */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 18, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4, display: 'block' }}>
              Probar: ¿qué responde el bot a...?
            </label>
            <Input
              value={testQuery}
              onChange={e => setTestQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && testMatch()}
              placeholder="Escribí una pregunta de cliente y probá si hay match"
              data-testid="bl-test-input"
            />
          </div>
          <Button onClick={testMatch} disabled={testing || !testQuery.trim()} data-testid="bl-test-btn">
            <Search className="w-4 h-4 mr-1" />
            {testing ? 'Probando...' : 'Probar'}
          </Button>
        </div>
        {testResult && (
          <div style={{
            marginBottom: 18, padding: '12px 14px', borderRadius: 8,
            border: `1px solid ${testResult.matched ? '#bbf7d0' : '#fecaca'}`,
            background: testResult.matched ? '#f0fdf4' : '#fef2f2',
            fontSize: 13, color: testResult.matched ? '#14532d' : '#7f1d1d',
          }}>
            {testResult.matched ? (
              <>
                <div><strong>✅ Match (score {testResult.match.score})</strong></div>
                <div style={{ marginTop: 6 }}><em>Pregunta similar guardada:</em> "{testResult.match.learned_question}"</div>
                <div style={{ marginTop: 6 }}><em>El bot responderá:</em></div>
                <div style={{ marginTop: 4, padding: '8px 12px', background: '#fff', borderRadius: 6, border: '1px solid #d1fae5' }}>
                  {testResult.match.answer}
                </div>
              </>
            ) : (
              <div>
                <strong>❌ Sin match.</strong> El bot va a usar la IA contextual o el catálogo para responder.
              </div>
            )}
          </div>
        )}

        {/* Add manual */}
        {!showAdd ? (
          <Button size="sm" variant="outline" onClick={() => setShowAdd(true)} style={{ marginBottom: 14 }} data-testid="bl-show-add">
            <Plus className="w-4 h-4 mr-1" />
            Agregar respuesta manual
          </Button>
        ) : (
          <div style={{ marginBottom: 18, padding: 12, background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb' }}>
            <Input value={newQ} onChange={e => setNewQ(e.target.value)} placeholder="Pregunta típica del cliente" style={{ marginBottom: 8 }} data-testid="bl-new-q" />
            <Textarea value={newA} onChange={e => setNewA(e.target.value)} placeholder="Respuesta que dará el bot" rows={3} style={{ marginBottom: 8 }} data-testid="bl-new-a" />
            <div style={{ display: 'flex', gap: 6 }}>
              <Button size="sm" onClick={addNew} disabled={!newQ.trim() || !newA.trim()} data-testid="bl-save-new">Guardar</Button>
              <Button size="sm" variant="outline" onClick={() => { setShowAdd(false); setNewQ(''); setNewA(''); }}>Cancelar</Button>
            </div>
          </div>
        )}

        {/* Lista */}
        {loading ? (
          <div>Cargando...</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#6b7280', fontSize: 13 }}>
            Aún no hay respuestas aprendidas. El bot se va a entrenar a medida
            que tus asesores marquen sus respuestas con "Enseñar al bot" desde
            las conversaciones.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map(item => (
              <div key={item.id} style={{
                padding: 12, borderRadius: 8,
                background: item.active ? '#fff' : '#f9fafb',
                border: '1px solid #e5e7eb',
                opacity: item.active ? 1 : 0.6,
              }}
                data-testid={`bl-item-${item.id}`}
              >
                {editingId === item.id ? (
                  <>
                    <Input value={editQ} onChange={e => setEditQ(e.target.value)} style={{ marginBottom: 6 }} />
                    <Textarea value={editA} onChange={e => setEditA(e.target.value)} rows={3} style={{ marginBottom: 6 }} />
                    <div style={{ display: 'flex', gap: 6 }}>
                      <Button size="sm" onClick={() => saveEdit(item.id)} data-testid={`bl-save-${item.id}`}>
                        <Check className="w-3 h-3 mr-1" />
                        Guardar
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>
                        <X className="w-3 h-3 mr-1" />
                        Cancelar
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>
                          Q: {item.question}
                        </div>
                        <div style={{ fontSize: 13, color: '#374151', marginTop: 4, whiteSpace: 'pre-wrap' }}>
                          A: {item.answer}
                        </div>
                        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 6 }}>
                          Usos: {item.used_count || 0}
                          {item.last_used_at && ` · último uso: ${new Date(item.last_used_at).toLocaleString('es-AR')}`}
                          {!item.active && ' · INACTIVA'}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <Button size="sm" variant="outline" onClick={() => toggleActive(item)} title={item.active ? 'Desactivar' : 'Activar'}>
                          {item.active ? <PowerOff className="w-3 h-3" /> : <Power className="w-3 h-3" />}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => startEdit(item)} title="Editar" data-testid={`bl-edit-${item.id}`}>
                          <Edit2 className="w-3 h-3" />
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => remove(item.id)} title="Borrar" style={{ borderColor: '#fecaca', color: '#dc2626' }} data-testid={`bl-delete-${item.id}`}>
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
