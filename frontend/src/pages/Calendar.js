import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function Calendar() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchLeads();
  }, []);

  const fetchLeads = async () => {
    try {
      const response = await axios.get(`${API}/leads`);
      // Solo leads con cita
      const leadsWithAppointments = response.data.filter(lead => lead.appointment_datetime);
      setLeads(leadsWithAppointments);
    } catch (error) {
      console.error('Error fetching leads:', error);
    } finally {
      setLoading(false);
    }
  };

  // Obtener días del mes actual
  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();
    
    return { daysInMonth, startingDay, year, month };
  };

  const { daysInMonth, startingDay, year, month } = getDaysInMonth(currentDate);

  // Obtener citas para un día específico
  const getAppointmentsForDay = (day) => {
    return leads.filter(lead => {
      const appointmentDate = new Date(lead.appointment_datetime);
      return (
        appointmentDate.getDate() === day &&
        appointmentDate.getMonth() === month &&
        appointmentDate.getFullYear() === year
      );
    });
  };

  // Navegar meses
  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
    setSelectedDate(null);
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
    setSelectedDate(null);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
    setSelectedDate(new Date().getDate());
  };

  // Formatear fecha
  const monthNames = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
  ];

  const dayNames = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];

  // Renderizar días del calendario
  const renderCalendarDays = () => {
    const days = [];
    const today = new Date();
    
    // Espacios vacíos antes del primer día
    for (let i = 0; i < startingDay; i++) {
      days.push(<div key={`empty-${i}`} className="calendar-day empty"></div>);
    }
    
    // Días del mes
    for (let day = 1; day <= daysInMonth; day++) {
      const appointments = getAppointmentsForDay(day);
      const isToday = 
        day === today.getDate() && 
        month === today.getMonth() && 
        year === today.getFullYear();
      const isSelected = selectedDate === day;
      const hasAppointments = appointments.length > 0;
      
      days.push(
        <div
          key={day}
          className={`calendar-day ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${hasAppointments ? 'has-appointments' : ''}`}
          onClick={() => setSelectedDate(day)}
          data-testid={`calendar-day-${day}`}
        >
          <span className="day-number">{day}</span>
          {hasAppointments && (
            <div className="appointment-dots">
              {appointments.slice(0, 3).map((_, idx) => (
                <span key={idx} className="dot"></span>
              ))}
              {appointments.length > 3 && <span className="more">+{appointments.length - 3}</span>}
            </div>
          )}
        </div>
      );
    }
    
    return days;
  };

  // Obtener citas del día seleccionado
  const selectedDayAppointments = selectedDate ? getAppointmentsForDay(selectedDate) : [];

  const getStatusBadge = (status) => {
    const styles = {
      hot: 'badge-hot',
      warm: 'badge-warm',
      cold: 'badge-cold'
    };
    const labels = {
      hot: '🔥 Caliente',
      warm: '🟡 Tibio',
      cold: '❄️ Frío'
    };
    return <Badge className={styles[status]}>{labels[status] || status}</Badge>;
  };

  if (loading) {
    return <div className="loading-container">Cargando calendario...</div>;
  }

  return (
    <div className="page-container" data-testid="calendar-page">
      <header className="page-header">
        <div>
          <h1>Calendario de Citas</h1>
          <p className="subtitle">{leads.length} citas programadas</p>
        </div>
        <Button onClick={goToToday} variant="outline" data-testid="btn-today">
          Hoy
        </Button>
      </header>

      <div className="calendar-layout">
        <Card className="calendar-card">
          <CardHeader className="calendar-header">
            <div className="calendar-nav">
              <Button variant="ghost" size="icon" onClick={prevMonth} data-testid="btn-prev-month">
                <ChevronLeft className="h-5 w-5" />
              </Button>
              <h2 className="calendar-title">
                {monthNames[month]} {year}
              </h2>
              <Button variant="ghost" size="icon" onClick={nextMonth} data-testid="btn-next-month">
                <ChevronRight className="h-5 w-5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="calendar-grid">
              {/* Nombres de los días */}
              {dayNames.map(dayName => (
                <div key={dayName} className="calendar-day-name">
                  {dayName}
                </div>
              ))}
              {/* Días del mes */}
              {renderCalendarDays()}
            </div>
          </CardContent>
        </Card>

        {/* Panel lateral con citas del día */}
        <Card className="appointments-panel">
          <CardHeader>
            <CardTitle>
              {selectedDate 
                ? `Citas del ${selectedDate}/${month + 1}/${year}`
                : 'Seleccioná un día'
              }
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selectedDate ? (
              selectedDayAppointments.length > 0 ? (
                <div className="day-appointments">
                  {selectedDayAppointments.map((lead) => {
                    const time = new Date(lead.appointment_datetime).toLocaleTimeString('es-AR', {
                      hour: '2-digit',
                      minute: '2-digit'
                    });
                    return (
                      <div 
                        key={lead.phone} 
                        className="appointment-item"
                        onClick={() => navigate(`/leads/${lead.phone}`)}
                        data-testid={`appointment-${lead.phone}`}
                      >
                        <div className="appointment-time">{time}</div>
                        <div className="appointment-info">
                          <div className="appointment-name">{lead.name || 'Sin nombre'}</div>
                          <div className="appointment-phone">{lead.phone}</div>
                          <div className="appointment-type">{lead.appointment_type || 'Cita'}</div>
                        </div>
                        {getStatusBadge(lead.status)}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="no-appointments">
                  <p>No hay citas para este día</p>
                </div>
              )
            ) : (
              <div className="no-appointments">
                <p>Hacé click en un día para ver las citas</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Próximas citas */}
      <Card className="upcoming-appointments">
        <CardHeader>
          <CardTitle>Próximas Citas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="upcoming-list">
            {leads
              .filter(lead => new Date(lead.appointment_datetime) >= new Date())
              .sort((a, b) => new Date(a.appointment_datetime) - new Date(b.appointment_datetime))
              .slice(0, 5)
              .map((lead) => {
                const date = new Date(lead.appointment_datetime);
                return (
                  <div 
                    key={lead.phone} 
                    className="upcoming-item"
                    onClick={() => navigate(`/leads/${lead.phone}`)}
                  >
                    <div className="upcoming-date">
                      <span className="day">{date.getDate()}</span>
                      <span className="month">{monthNames[date.getMonth()].slice(0, 3)}</span>
                    </div>
                    <div className="upcoming-info">
                      <div className="upcoming-name">{lead.name || 'Sin nombre'}</div>
                      <div className="upcoming-time">
                        {date.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })} - {lead.appointment_type || 'Cita'}
                      </div>
                    </div>
                    {getStatusBadge(lead.status)}
                  </div>
                );
              })
            }
            {leads.filter(lead => new Date(lead.appointment_datetime) >= new Date()).length === 0 && (
              <div className="no-appointments">
                <p>No hay citas próximas</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
