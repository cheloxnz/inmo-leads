import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Calculator, TrendingUp, DollarSign, Users } from 'lucide-react';

export default function ROICalculator() {
  const [monthlyLeads, setMonthlyLeads] = useState(100);
  const [roiData, setRoiData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    calculateROI();
  }, [monthlyLeads]);

  const calculateROI = async () => {
    if (monthlyLeads < 1) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${API}/calculator/roi?monthly_leads=${monthlyLeads}`);
      setRoiData(response.data);
    } catch (error) {
      console.error('Error calculating ROI:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatPercent = (value) => {
    return new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value) + '%';
  };

  return (
    <Card className="roi-calculator-card" data-testid="roi-calculator">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calculator className="w-5 h-5 text-primary" />
          Calculadora ROI
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="roi-input-section">
          <label className="roi-label">
            <Users className="w-4 h-4" />
            Leads mensuales estimados
          </label>
          <Input
            type="number"
            value={monthlyLeads}
            onChange={(e) => setMonthlyLeads(Math.max(1, parseInt(e.target.value) || 1))}
            min="1"
            max="10000"
            className="roi-input"
            data-testid="roi-leads-input"
          />
        </div>

        {loading ? (
          <div className="roi-loading">Calculando...</div>
        ) : roiData ? (
          <div className="roi-results">
            <div className="roi-comparison">
              <div className="roi-column roi-without">
                <h4>Sin InmoBot</h4>
                <div className="roi-stat">
                  <span className="roi-stat-label">Tasa respuesta</span>
                  <span className="roi-stat-value">{roiData.without_inmobot?.response_rate}</span>
                </div>
                <div className="roi-stat">
                  <span className="roi-stat-label">Conversión</span>
                  <span className="roi-stat-value">{roiData.without_inmobot?.conversion_rate}</span>
                </div>
                <div className="roi-stat">
                  <span className="roi-stat-label">Ingresos est.</span>
                  <span className="roi-stat-value negative">
                    {formatCurrency(roiData.without_inmobot?.estimated_revenue || 0)}
                  </span>
                </div>
              </div>

              <div className="roi-column roi-with">
                <h4>Con InmoBot</h4>
                <div className="roi-stat">
                  <span className="roi-stat-label">Tasa respuesta</span>
                  <span className="roi-stat-value">{roiData.with_inmobot?.response_rate}</span>
                </div>
                <div className="roi-stat">
                  <span className="roi-stat-label">Conversión</span>
                  <span className="roi-stat-value">{roiData.with_inmobot?.conversion_rate}</span>
                </div>
                <div className="roi-stat">
                  <span className="roi-stat-label">Ingresos est.</span>
                  <span className="roi-stat-value positive">
                    {formatCurrency(roiData.with_inmobot?.estimated_revenue || 0)}
                  </span>
                </div>
              </div>
            </div>

            <div className="roi-summary">
              <div className="roi-highlight">
                <DollarSign className="w-6 h-6" />
                <div>
                  <span className="roi-highlight-label">Ganancia adicional</span>
                  <span className="roi-highlight-value">
                    {formatCurrency(roiData.comparison?.net_gain || 0)}
                  </span>
                </div>
              </div>
              
              <div className="roi-highlight roi-percent">
                <TrendingUp className="w-6 h-6" />
                <div>
                  <span className="roi-highlight-label">ROI</span>
                  <span className="roi-highlight-value">
                    {formatPercent(roiData.comparison?.roi_percentage || 0)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
