import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import NotificationBell from './components/NotificationBell';
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import FlowVisualization from './pages/FlowVisualization';
import Configuration from './pages/Configuration';
import Documentation from './pages/Documentation';
import Login from './pages/Login';
import KanbanView from './pages/KanbanView';
import AgentManagement from './pages/AgentManagement';
import MyDashboard from './pages/MyDashboard';
import Calendar from './pages/Calendar';
import Pricing from './pages/Pricing';
import PaymentSuccess from './pages/PaymentSuccess';
import Demo from './pages/Demo';
import PrivacyPolicy from './pages/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService';
import DataDeletion from './pages/DataDeletion';
import LandingPage from './pages/LandingPage';
import { Moon, Sun, ChevronLeft, ChevronRight } from 'lucide-react';
import '@/App.css';

// Siempre usar la URL actual del navegador (mismo dominio)
const BACKEND_URL = window.location.origin;
export const API = `${BACKEND_URL}/api`;

// Hook para tema oscuro
function useTheme() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return { theme, toggleTheme };
}

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, loading, isAdmin } = useAuth();

  if (loading) {
    return <div className="loading-container">Cargando...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/mi-dashboard" replace />;
  }

  return children;
}

function Navigation() {
  const location = useLocation();
  const { user, logout, isAdmin, isAuthenticated } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('sidebarCollapsed') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('sidebarCollapsed', isCollapsed);
  }, [isCollapsed]);

  if (!isAuthenticated) return null;

  const isActive = (path) => location.pathname === path;

  const toggleSidebar = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <nav className={`nav-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="nav-logo">
        <img 
          src="/logo192.png" 
          alt="InmoBot" 
          className="logo-image"
        />
        {!isCollapsed && <h1>InmoBot AI</h1>}
      </div>

      <button 
        className="sidebar-toggle" 
        onClick={toggleSidebar}
        data-testid="btn-toggle-sidebar"
        title={isCollapsed ? 'Expandir menú' : 'Contraer menú'}
      >
        {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>

      <div className="nav-links">
        {isAdmin ? (
          <>
            <Link
              to="/"
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
              data-testid="nav-dashboard"
              title="Dashboard General"
            >
              <span className="icon">📊</span>
              {!isCollapsed && <span>Dashboard General</span>}
            </Link>

            <Link
              to="/leads"
              className={`nav-link ${isActive('/leads') ? 'active' : ''}`}
              data-testid="nav-leads"
              title="Todos los Leads"
            >
              <span className="icon">👥</span>
              {!isCollapsed && <span>Todos los Leads</span>}
            </Link>

            <Link
              to="/kanban"
              className={`nav-link ${isActive('/kanban') ? 'active' : ''}`}
              data-testid="nav-kanban"
              title="Pipeline (Kanban)"
            >
              <span className="icon">📋</span>
              {!isCollapsed && <span>Pipeline (Kanban)</span>}
            </Link>

            <Link
              to="/calendario"
              className={`nav-link ${isActive('/calendario') ? 'active' : ''}`}
              data-testid="nav-calendar"
              title="Calendario"
            >
              <span className="icon">📅</span>
              {!isCollapsed && <span>Calendario</span>}
            </Link>

            <Link
              to="/asesores"
              className={`nav-link ${isActive('/asesores') ? 'active' : ''}`}
              data-testid="nav-agents"
              title="Gestión Asesores"
            >
              <span className="icon">👔</span>
              {!isCollapsed && <span>Gestión Asesores</span>}
            </Link>
          </>
        ) : (
          <>
            <Link
              to="/mi-dashboard"
              className={`nav-link ${isActive('/mi-dashboard') ? 'active' : ''}`}
              data-testid="nav-my-dashboard"
              title="Mi Dashboard"
            >
              <span className="icon">📊</span>
              {!isCollapsed && <span>Mi Dashboard</span>}
            </Link>

            <Link
              to="/my-leads"
              className={`nav-link ${isActive('/my-leads') ? 'active' : ''}`}
              data-testid="nav-my-leads"
              title="Mis Leads"
            >
              <span className="icon">👥</span>
              {!isCollapsed && <span>Mis Leads</span>}
            </Link>

            <Link
              to="/calendario"
              className={`nav-link ${isActive('/calendario') ? 'active' : ''}`}
              data-testid="nav-calendar-asesor"
              title="Calendario"
            >
              <span className="icon">📅</span>
              {!isCollapsed && <span>Calendario</span>}
            </Link>
          </>
        )}

        <Link
          to="/flow"
          className={`nav-link ${isActive('/flow') ? 'active' : ''}`}
          data-testid="nav-flow"
          title="Flujo Bot"
        >
          <span className="icon">🔄</span>
          {!isCollapsed && <span>Flujo Bot</span>}
        </Link>

        {isAdmin && (
          <Link
            to="/config"
            className={`nav-link ${isActive('/config') ? 'active' : ''}`}
            data-testid="nav-config"
            title="Configuración"
          >
            <span className="icon">⚙️</span>
            {!isCollapsed && <span>Configuración</span>}
          </Link>
        )}
      </div>

      <div className="nav-footer">
        <button 
          className="theme-toggle" 
          onClick={toggleTheme}
          data-testid="btn-theme-toggle"
          title={theme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>
        {!isCollapsed && (
          <div className="user-info">
            <div className="user-avatar">
              {user?.name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name || 'Usuario'}</span>
              <span className="user-role">{isAdmin ? 'Administrador' : 'Asesor'}</span>
            </div>
          </div>
        )}
        {isCollapsed && (
          <div className="user-avatar-only" title={user?.name || 'Usuario'}>
            {user?.name?.charAt(0)?.toUpperCase() || 'U'}
          </div>
        )}
        <button className="logout-btn" onClick={logout} data-testid="btn-logout" title="Cerrar Sesión">
          {isCollapsed ? '🚪' : 'Cerrar Sesión'}
        </button>
      </div>
    </nav>
  );
}

function AppHeader() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) return null;

  return (
    <header className="app-header">
      <div className="header-right">
        <NotificationBell />
      </div>
    </header>
  );
}

function MyLeadsPage() {
  const { user } = useAuth();
  return <Leads filterByAgent={user?.email} />;
}

function AppContent() {
  const { isAuthenticated, loading, isAdmin } = useAuth();
  const location = useLocation();
  
  // Páginas públicas que no necesitan el layout del dashboard
  const publicPages = ['/inicio', '/planes', '/demo', '/pago-exitoso', '/privacy', '/terms', '/data-deletion', '/login'];
  const isPublicPage = publicPages.some(page => location.pathname.startsWith(page)) || location.pathname === '/inicio';

  if (loading) {
    return <div className="loading-container">Cargando aplicación...</div>;
  }

  // Si es página pública, mostrar sin navegación lateral
  if (isPublicPage || !isAuthenticated) {
    return (
      <div className="App public-layout">
        <main className="main-content full-width">
          <Routes>
            <Route path="/login" element={
              isAuthenticated ? <Navigate to={isAdmin ? "/" : "/mi-dashboard"} replace /> : <Login />
            } />
            <Route path="/inicio" element={<LandingPage />} />
            <Route path="/planes" element={<Pricing />} />
            <Route path="/demo" element={<Demo />} />
            <Route path="/pago-exitoso" element={<PaymentSuccess />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/terms" element={<TermsOfService />} />
            <Route path="/data-deletion" element={<DataDeletion />} />
            <Route path="*" element={<Navigate to="/inicio" replace />} />
          </Routes>
        </main>
      </div>
    );
  }

  return (
    <div className="App">
      <Navigation />
      <main className="main-content">
        <AppHeader />
        <Routes>
          {/* Rutas Admin */}
          <Route path="/" element={
            <ProtectedRoute adminOnly>
              <Dashboard />
            </ProtectedRoute>
          } />
          <Route path="/leads" element={
            <ProtectedRoute adminOnly>
              <Leads />
            </ProtectedRoute>
          } />
          <Route path="/kanban" element={
            <ProtectedRoute adminOnly>
              <KanbanView />
            </ProtectedRoute>
          } />
          <Route path="/asesores" element={
            <ProtectedRoute adminOnly>
              <AgentManagement />
            </ProtectedRoute>
          } />
          <Route path="/config" element={
            <ProtectedRoute adminOnly>
              <Configuration />
            </ProtectedRoute>
          } />
          <Route path="/calendario" element={
            <ProtectedRoute>
              <Calendar />
            </ProtectedRoute>
          } />

          {/* Rutas Asesor */}
          <Route path="/mi-dashboard" element={
            <ProtectedRoute>
              <MyDashboard />
            </ProtectedRoute>
          } />
          <Route path="/my-leads" element={
            <ProtectedRoute>
              <MyLeadsPage />
            </ProtectedRoute>
          } />

          {/* Rutas compartidas */}
          <Route path="/leads/:phone" element={
            <ProtectedRoute>
              <LeadDetail />
            </ProtectedRoute>
          } />
          <Route path="/flow" element={
            <ProtectedRoute>
              <FlowVisualization />
            </ProtectedRoute>
          } />
          <Route path="/docs" element={
            <ProtectedRoute>
              <Documentation />
            </ProtectedRoute>
          } />

          {/* Redirect por defecto para usuarios autenticados */}
          <Route path="*" element={
            <Navigate to={isAdmin ? "/" : "/mi-dashboard"} replace />
          } />
        </Routes>
      </main>
      <Toaster position="top-right" richColors />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
          <AppContent />
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
