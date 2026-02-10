import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Calculator, TrendingUp, DollarSign, Users, Percent } from 'lucide-react';

export default function PublicROICalculator() {
  // Parámetros configurables
  const [monthlyLeads, setMonthlyLeads] = useState(100);
  const [avgCommission, setAvgCommission] = useState(5000); // USD
  const [currentConversion, setCurrentConversion] = useState(3.5); // %
  const [currentResponseRate, setCurrentResponseRate] = useState(60); // %

  // Valores con InmoBot (mejoras estimadas)
  const botResponseRate = 100; // 100% respuesta automática
  const botConversionMultiplier = 2; // Duplica conversión

  const results = useMemo(() => {
    // Sin InmoBot
    const leadsResponded = monthlyLeads * (currentResponseRate / 100);
    const salesWithout = leadsResponded * (currentConversion / 100);
    const revenueWithout = salesWithout * avgCommission;

    // Con InmoBot
    const botLeadsResponded = monthlyLeads * (botResponseRate / 100);
    const botConversion = currentConversion * botConversionMultiplier;
    const salesWith = botLeadsResponded * (botConversion / 100);
    const revenueWith = salesWith * avgCommission;

    // Comparación
    const additionalRevenue = revenueWith - revenueWithout;
    const planCost = 129; // Plan profesional
    const netGain = additionalRevenue - planCost;
    const roi = planCost > 0 ? ((netGain / planCost) * 100) : 0;

    return {
      without: {
        responseRate: currentResponseRate,
        conversion: currentConversion,
        sales: salesWithout,
        revenue: revenueWithout
      },
      with: {
        responseRate: botResponseRate,
        conversion: botConversion,
        sales: salesWith,
        revenue: revenueWith
      },
      comparison: {
        additionalRevenue,
        planCost,
        netGain,
        roi
      }
    };
  }, [monthlyLeads, avgCommission, currentConversion, currentResponseRate]);

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  return (
    <Card className="public-roi-calculator" data-testid="public-roi-calculator">
      <CardHeader>
        <CardTitle className="roi-title">
          <Calculator className="w-6 h-6" />
          Calculá tu ROI con InmoBot
        </CardTitle>
        <p className="roi-subtitle">Ajustá los valores según tu realidad y mirá cuánto podrías ganar</p>
      </CardHeader>
      <CardContent>
        <div className="roi-config-grid">
          {/* Configuración */}
          <div className="roi-config-section">
            <div className="config-item">
              <label>
                <Users className="w-4 h-4" />
                Leads mensuales
              </label>
              <div className="slider-container">
                <Slider
                  value={[monthlyLeads]}
                  onValueChange={(v) => setMonthlyLeads(v[0])}
                  min={10}
                  max={500}
                  step={10}
                  className="config-slider"
                />
                <span className="slider-value">{monthlyLeads}</span>
              </div>
            </div>

            <div className="config-item">
              <label>
                <DollarSign className="w-4 h-4" />
                Comisión promedio (USD)
              </label>
              <div className="slider-container">
                <Slider
                  value={[avgCommission]}
                  onValueChange={(v) => setAvgCommission(v[0])}
                  min={1000}
                  max={20000}
                  step={500}
                  className="config-slider"
                />
                <span className="slider-value">{formatCurrency(avgCommission)}</span>
              </div>
            </div>

            <div className="config-item">
              <label>
                <Percent className="w-4 h-4" />
                Tu tasa de conversión actual
              </label>
              <div className="slider-container">
                <Slider
                  value={[currentConversion]}
                  onValueChange={(v) => setCurrentConversion(v[0])}
                  min={1}
                  max={10}
                  step={0.5}
                  className="config-slider"
                />
                <span className="slider-value">{currentConversion}%</span>
              </div>
            </div>

            <div className="config-item">
              <label>
                <TrendingUp className="w-4 h-4" />
                % de leads que respondés hoy
              </label>
              <div className="slider-container">
                <Slider
                  value={[currentResponseRate]}
                  onValueChange={(v) => setCurrentResponseRate(v[0])}
                  min={20}
                  max={100}
                  step={5}
                  className="config-slider"
                />
                <span className="slider-value">{currentResponseRate}%</span>
              </div>
            </div>
          </div>

          {/* Resultados */}
          <div className="roi-results-section">
            <div className="roi-comparison-cards">
              <div className="comparison-card without">
                <h4>Sin InmoBot</h4>
                <div className="comparison-stats">
                  <div className="stat-row">
                    <span>Leads respondidos</span>
                    <span>{Math.round(monthlyLeads * (currentResponseRate / 100))}</span>
                  </div>
                  <div className="stat-row">
                    <span>Ventas/mes</span>
                    <span>{results.without.sales.toFixed(1)}</span>
                  </div>
                  <div className="stat-row highlight">
                    <span>Ingresos</span>
                    <span>{formatCurrency(results.without.revenue)}</span>
                  </div>
                </div>
              </div>

              <div className="comparison-card with">
                <h4>Con InmoBot</h4>
                <div className="comparison-stats">
                  <div className="stat-row">
                    <span>Leads respondidos</span>
                    <span>{monthlyLeads} (100%)</span>
                  </div>
                  <div className="stat-row">
                    <span>Ventas/mes</span>
                    <span>{results.with.sales.toFixed(1)}</span>
                  </div>
                  <div className="stat-row highlight">
                    <span>Ingresos</span>
                    <span>{formatCurrency(results.with.revenue)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="roi-bottom-line">
              <div className="bottom-line-item gain">
                <DollarSign className="w-8 h-8" />
                <div>
                  <span className="bottom-label">Ganancia adicional/mes</span>
                  <span className="bottom-value">{formatCurrency(results.comparison.netGain)}</span>
                </div>
              </div>
              <div className="bottom-line-item roi">
                <TrendingUp className="w-8 h-8" />
                <div>
                  <span className="bottom-label">ROI</span>
                  <span className="bottom-value">{results.comparison.roi.toFixed(0)}%</span>
                </div>
              </div>
            </div>

            <p className="roi-disclaimer">
              * Cálculo basado en que InmoBot responde el 100% de los leads y mejora la conversión al dar respuestas inmediatas y calificar automáticamente.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
