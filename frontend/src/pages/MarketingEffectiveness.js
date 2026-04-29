import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, BarChart, Bar,
} from 'recharts';
import {
  Share2, Eye, MousePointer2, UserPlus, TrendingUp, Trophy,
  Twitter, Linkedin, Download, Loader2, ArrowDown, Sparkles,
} from 'lucide-react';

const FUNNEL_STEPS = [
  { key: 'shares_explicit', label: 'Compartidas', icon: Share2, color: '#8b5cf6' },
  { key: 'html_views', label: 'Vistas en redes', icon: Eye, color: '#3b82f6' },
  { key: 'leads_captured', label: 'Leads capturados', icon: MousePointer2, color: '#10b981' },
  { key: 'signups_converted', label: 'Signups convertidos', icon: UserPlus, color: '#f59e0b' },
];

const CELEBRATION_LABELS = {
  whatsapp_connected: 'WhatsApp conectado',
  first_lead: 'Primer lead',
  branding_customized: 'Branding personalizado',
  first_ai_edit: 'Primer edit IA',
};

export default function MarketingEffectiveness() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const [error, setError] = useState('');

  useEffect(() => {
    fetchData(days);
  }, [days]);

  const fetchData = async (d) => {
    setLoading(true);
    setError('');
    try {
      const r = await axios.get(`${API}/coach/effectiveness?days=${d}`);
      setData(r.data);
    } catch (e) {
      const msg = e?.response?.data?.detail || 'No se pudo cargar el dashboard';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="page-container" data-testid="marketing-error">
        <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Datos para los charts
  const funnelChartData = FUNNEL_STEPS.map(s => ({
    name: s.label,
    value: data.funnel[s.key] ?? 0,
    fill: s.color,
  }));

  // Conseguir el max para calcular % visual del funnel
  const funnelMax = Math.max(...funnelChartData.map(d => d.value), 1);

  const platformData = [
    { name: 'X / Twitter', value: data.by_platform.twitter, fill: '#1DA1F2' },
    { name: 'LinkedIn', value: data.by_platform.linkedin, fill: '#0A66C2' },
    { name: 'Descarga', value: data.by_platform.download, fill: '#10b981' },
  ];

  return (
    <div className="page-container space-y-6" data-testid="marketing-effectiveness-page">
      <header className="page-header flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2">
            <Trophy className="w-7 h-7 text-amber-500" />
            Marketing Effectiveness
          </h1>
          <p className="subtitle">
            Funnel de adquisición vía celebraciones compartidas. Medí qué te trae usuarios reales.
          </p>
        </div>
        <div className="flex gap-2" data-testid="window-selector">
          {[7, 30, 90].map(d => (
            <Button
              key={d}
              data-testid={`window-${d}`}
              variant={days === d ? 'default' : 'outline'}
              size="sm"
              onClick={() => setDays(d)}
            >
              {d}d
            </Button>
          ))}
        </div>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {FUNNEL_STEPS.map(step => {
          const Icon = step.icon;
          const value = data.funnel[step.key] ?? 0;
          return (
            <Card
              key={step.key}
              data-testid={`kpi-${step.key}`}
              className="border-l-4"
              style={{ borderLeftColor: step.color }}
            >
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <Icon className="w-5 h-5" style={{ color: step.color }} />
                  <span className="text-xs text-gray-400 uppercase font-semibold">
                    {step.label}
                  </span>
                </div>
                <div className="text-3xl font-bold mt-2" style={{ color: step.color }}>
                  {value.toLocaleString()}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Funnel Visual + Conversion rates */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card data-testid="funnel-visual">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ArrowDown className="w-4 h-4" />
              Funnel de Adquisición
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {funnelChartData.map((d, i) => {
                const pct = (d.value / funnelMax) * 100;
                const next = funnelChartData[i + 1];
                const stepRateRaw = next && d.value > 0 ? (next.value / d.value) * 100 : null;
                const stepRate = stepRateRaw !== null ? Math.min(100, stepRateRaw).toFixed(1) : null;
                const stepOverflow = stepRateRaw !== null && stepRateRaw > 100;
                return (
                  <div key={d.name}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="font-medium">{d.name}</span>
                      <span className="text-gray-500 font-mono">{d.value.toLocaleString()}</span>
                    </div>
                    <div className="h-8 bg-gray-100 rounded-md overflow-hidden">
                      <div
                        className="h-full transition-all duration-500 flex items-center justify-end pr-2 text-white text-xs font-semibold"
                        style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: d.fill }}
                      >
                        {pct >= 15 && `${pct.toFixed(0)}%`}
                      </div>
                    </div>
                    {stepRate !== null && (
                      <div className="text-xs text-gray-500 mt-1 ml-2 flex items-center gap-1">
                        <ArrowDown className="w-3 h-3" />
                        {stepRate}%{stepOverflow ? '+' : ''} al siguiente paso
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-6 pt-4 border-t grid grid-cols-2 gap-3 text-xs">
              <div data-testid="rate-view-to-lead">
                <span className="text-gray-500">Vista → Lead</span>
                <div className="text-lg font-bold text-emerald-600">
                  {data.funnel_rates.view_to_lead}%
                </div>
              </div>
              <div data-testid="rate-lead-to-signup">
                <span className="text-gray-500">Lead → Signup</span>
                <div className="text-lg font-bold text-amber-600">
                  {data.funnel_rates.lead_to_signup}%
                </div>
              </div>
              <div data-testid="rate-share-to-view">
                <span className="text-gray-500">Share → Vista</span>
                <div className="text-lg font-bold text-blue-600">
                  {data.funnel_rates.share_to_view}%
                </div>
              </div>
              <div data-testid="rate-overall">
                <span className="text-gray-500">Share → Signup</span>
                <div className="text-lg font-bold text-purple-600">
                  {data.funnel_rates.overall_share_to_signup}%
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Time series chart */}
        <Card data-testid="timeseries-chart">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="w-4 h-4" />
              Evolución últimos {days} días
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.timeseries.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-12">
                Sin actividad en este período. Empezá a compartir celebraciones para ver datos.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data.timeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone" dataKey="leads" stroke="#10b981" strokeWidth={2}
                    name="Leads" dot={{ r: 3 }}
                  />
                  <Line
                    type="monotone" dataKey="converted" stroke="#f59e0b" strokeWidth={2}
                    name="Convertidos" dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Platform breakdown + Top celebrations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card data-testid="platform-breakdown" className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Shares por plataforma</CardTitle>
          </CardHeader>
          <CardContent>
            {platformData.every(p => p.value === 0) ? (
              <div className="text-sm text-gray-500 text-center py-8">
                Aún no hay shares trackeados.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={platformData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {platformData.map((p, i) => (
                      <rect key={i} fill={p.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            <div className="grid grid-cols-3 gap-2 mt-3 text-xs text-center">
              <div className="flex flex-col items-center gap-1">
                <Twitter className="w-4 h-4 text-[#1DA1F2]" />
                <span className="font-bold">{data.by_platform.twitter}</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <Linkedin className="w-4 h-4 text-[#0A66C2]" />
                <span className="font-bold">{data.by_platform.linkedin}</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                <Download className="w-4 h-4 text-emerald-600" />
                <span className="font-bold">{data.by_platform.download}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card data-testid="top-celebrations" className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Top celebraciones por impacto
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.top_celebrations.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-8">
                Sin celebraciones aún. Activá milestones desde el Dashboard.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 uppercase border-b">
                      <th className="py-2 font-semibold">Celebración</th>
                      <th className="py-2 font-semibold text-right">Shares</th>
                      <th className="py-2 font-semibold text-right">Vistas</th>
                      <th className="py-2 font-semibold text-right">Leads</th>
                      <th className="py-2 font-semibold text-right">Signups</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_celebrations.map((tc) => (
                      <tr
                        key={tc.celebration_id}
                        data-testid={`top-celeb-${tc.celebration_type}`}
                        className="border-b hover:bg-gray-50 transition-colors"
                      >
                        <td className="py-2.5">
                          <div className="font-medium">{tc.title}</div>
                          <div className="text-xs text-gray-500">
                            {CELEBRATION_LABELS[tc.celebration_type] || tc.celebration_type}
                          </div>
                        </td>
                        <td className="py-2.5 text-right font-mono">{tc.shares_total}</td>
                        <td className="py-2.5 text-right font-mono">{tc.html_views}</td>
                        <td className="py-2.5 text-right font-mono text-emerald-600 font-semibold">
                          {tc.leads}
                        </td>
                        <td className="py-2.5 text-right font-mono text-amber-600 font-semibold">
                          {tc.converted}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
