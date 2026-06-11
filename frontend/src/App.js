import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import NotificationBell from './components/NotificationBell';
import ChangePassword from './components/ChangePassword';
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
import PrivacyPolicy from './pages/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService';
import DataDeletion from './pages/DataDeletion';
import InmobiliariaLanding from './pages/InmobiliariaLanding';
import DynamicLanding from './pages/DynamicLanding';
import { getTenantFromSubdomain } from './utils/subdomain';
import SuperAdminPanel from './pages/SuperAdminPanel';
import AutomatikDashboard from './pages/AutomatikDashboard';
import ClientesPage from './pages/ClientesPage';
import PagosPage from './pages/PagosPage';
import AutomatikLeads from './pages/AutomatikLeads';
import GastosPage from './pages/GastosPage';
import AuditLog from './pages/AuditLog';
import FlowBuilder from './components/FlowBuilder';
import CatalogPage from './pages/CatalogPage';
import PublicCatalog from './pages/PublicCatalog';
import WidgetAnalytics from './pages/WidgetAnalytics';
import LandingEditor from './pages/LandingEditor';
import Signup from './pages/Signup';
import Broadcast from './pages/Broadcast';
import MarketingEffectiveness from './pages/MarketingEffectiveness';
import Changelog from './pages/Changelog';
import UpdateBanner from './components/UpdateBanner';
import OnboardingTour from './components/OnboardingTour';
import { Moon, Sun, ChevronLeft, ChevronRight, Key, Building2, MessageSquare, Settings, Package, BarChart2, LayoutDashboard, Users, DollarSign, Monitor } from 'lucide-react';
import '@/App.css';

// Usar variable de entorno si está definida, sino fallback al mismo origen
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;
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
  const { user, logout, isAdmin, isSuperAdmin, isAuthenticated } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('sidebarCollapsed') === 'true';
  });
  const [showChangePassword, setShowChangePassword] = useState(false);

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
        {/* ── Menú SuperAdmin (Automatik Media) ── */}
        {isSuperAdmin ? (
          <>
            <Link
              to="/superadmin"
              className={`nav-link ${isActive('/superadmin') ? 'active' : ''}`}
              data-testid="nav-ak-dashboard"
              title="Dashboard Automatik"
            >
              <span className="icon"><LayoutDashboard size={16} /></span>
              {!isCollapsed && <span>Dashboard</span>}
            </Link>

            <Link
              to="/superadmin/clientes"
              className={`nav-link ${isActive('/superadmin/clientes') ? 'active' : ''}`}
              data-testid="nav-ak-clients"
              title="Clientes"
            >
              <span className="icon"><Users size={16} /></span>
              {!isCollapsed && <span>Clientes</span>}
            </Link>

            <Link
              to="/superadmin/pagos"
              className={`nav-link ${isActive('/superadmin/pagos') ? 'active' : ''}`}
              data-testid="nav-ak-payments"
              title="Pagos"
            >
              <span className="icon"><DollarSign size={16} /></span>
              {!isCollapsed && <span>Pagos</span>}
            </Link>

            <Link
              to="/superadmin/plataformas"
              className={`nav-link ${isActive('/superadmin/plataformas') ? 'active' : ''}`}
              data-testid="nav-ak-platforms"
              title="Plataformas"
            >
              <span className="icon"><Monitor size={16} /></span>
              {!isCollapsed && <span>Plataformas</span>}
            </Link>

            <Link
              to="/superadmin/leads"
              className={`nav-link ${isActive('/superadmin/leads') ? 'active' : ''}`}
              data-testid="nav-ak-leads"
              title="Leads del Bot"
            >
              <span className="icon">🤖</span>
              {!isCollapsed && <span>Leads del Bot</span>}
            </Link>

            <Link
              to="/superadmin/gastos"
              className={`nav-link ${isActive('/superadmin/gastos') ? 'active' : ''}`}
              data-testid="nav-ak-gastos"
              title="Gastos"
            >
              <span className="icon">💸</span>
              {!isCollapsed && <span>Gastos</span>}
            </Link>

            <div className="nav-divider" />

            <Link
              to="/config"
              className={`nav-link ${isActive('/config') ? 'active' : ''}`}
              data-testid="nav-ak-config"
              title="Configuración"
            >
              <span className="icon"><Settings size={16} /></span>
              {!isCollapsed && <span>Configuración</span>}
            </Link>

          </>
        ) : isAdmin ? (
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

            <Link
              to="/catalogo"
              className={`nav-link ${isActive('/catalogo') && !isActive('/catalogo/analytics') ? 'active' : ''}`}
              data-testid="nav-catalog"
              title="Catálogo"
            >
              <span className="icon"><Package size={16} /></span>
              {!isCollapsed && <span>Catalogo</span>}
            </Link>

            <Link
              to="/catalogo/analytics"
              className={`nav-link ${isActive('/catalogo/analytics') ? 'active' : ''}`}
              data-testid="nav-widget-analytics"
              title="Analytics del Widget"
            >
              <span className="icon"><BarChart2 size={16} /></span>
              {!isCollapsed && <span>Widget Stats</span>}
            </Link>

            <Link
              to="/marketing"
              className={`nav-link ${isActive('/marketing') ? 'active' : ''}`}
              data-testid="nav-marketing"
              title="Marketing Effectiveness"
            >
              <span className="icon">🏆</span>
              {!isCollapsed && <span>Marketing</span>}
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

        {isAdmin && !isSuperAdmin && (
          <Link
            to="/flujo"
            className={`nav-link ${isActive('/flujo') ? 'active' : ''}`}
            data-testid="nav-flow-builder"
            title="Bot"
          >
            <span className="icon">🔄</span>
            {!isCollapsed && <span>Bot</span>}
          </Link>
        )}

        {isAdmin && !isSuperAdmin && (
          <Link
            to="/config"
            className={`nav-link ${isActive('/config') ? 'active' : ''}`}
            data-testid="nav-config"
            title="Configuración"
          >
            <span className="icon"><Settings size={16} /></span>
            {!isCollapsed && <span>Configuracion</span>}
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
              <span className="user-role">{isSuperAdmin ? 'SuperAdmin' : isAdmin ? 'Administrador' : 'Asesor'}</span>
            </div>
          </div>
        )}
        {isCollapsed && (
          <div className="user-avatar-only" title={user?.name || 'Usuario'}>
            {user?.name?.charAt(0)?.toUpperCase() || 'U'}
          </div>
        )}
        <button 
          className="change-password-btn" 
          onClick={() => setShowChangePassword(true)} 
          data-testid="btn-open-change-password" 
          title="Cambiar Contraseña"
        >
          {isCollapsed ? <Key size={16} /> : <><Key size={16} /> Cambiar Contraseña</>}
        </button>
        <button className="logout-btn" onClick={logout} data-testid="btn-logout" title="Cerrar Sesión">
          {isCollapsed ? '🚪' : 'Cerrar Sesión'}
        </button>
      </div>
      
      <ChangePassword 
        isOpen={showChangePassword} 
        onClose={() => setShowChangePassword(false)} 
      />
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
  const { isAuthenticated, loading, isAdmin, isSuperAdmin } = useAuth();
  const location = useLocation();
  
  // Páginas públicas que no necesitan el layout del dashboard
  const publicPages = ['/inicio', '/privacy', '/terms', '/data-deletion', '/changelog', '/login', '/signup', '/p/'];
  const isPublicPage = publicPages.some(page => location.pathname.startsWith(page));

  // Subdomain routing: si llega por {tenant}.platform.com y no esta en una ruta especifica,
  // redirigir a /inicio/{tenant} para mostrar la landing del tenant
  const subdomainTenant = getTenantFromSubdomain();
  if (subdomainTenant && (location.pathname === '/' || location.pathname === '/inicio')) {
    return <Navigate to={`/inicio/${subdomainTenant}`} replace />;
  }

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
              isAuthenticated ? <Navigate to={isSuperAdmin ? "/superadmin" : isAdmin ? "/" : "/mi-dashboard"} replace /> : <Login />
            } />
            <Route path="/inicio" element={<DynamicLanding />} />
            <Route path="/inicio/:tenantId" element={<DynamicLanding />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/p/catalogo/:tenantId" element={<PublicCatalog />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/terms" element={<TermsOfService />} />
            <Route path="/data-deletion" element={<DataDeletion />} />
            <Route path="/changelog" element={<Changelog />} />
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
        <UpdateBanner />
        <AppHeader />
        {!isSuperAdmin && <OnboardingTour />}
        <Routes>
          {/* Rutas SuperAdmin Automatik */}
          <Route path="/superadmin" element={
            <ProtectedRoute adminOnly>
              <AutomatikDashboard />
            </ProtectedRoute>
          } />
          <Route path="/superadmin/clientes" element={
            <ProtectedRoute adminOnly>
              <ClientesPage />
            </ProtectedRoute>
          } />
          <Route path="/superadmin/pagos" element={
            <ProtectedRoute adminOnly>
              <PagosPage />
            </ProtectedRoute>
          } />
          <Route path="/superadmin/plataformas" element={
            <ProtectedRoute adminOnly>
              <SuperAdminPanel />
            </ProtectedRoute>
          } />
          <Route path="/superadmin/leads" element={
            <ProtectedRoute adminOnly>
              <AutomatikLeads />
            </ProtectedRoute>
          } />
          <Route path="/superadmin/gastos" element={
            <ProtectedRoute adminOnly>
              <GastosPage />
            </ProtectedRoute>
          } />
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
          <Route path="/catalogo" element={
            <ProtectedRoute adminOnly>
              <CatalogPage />
            </ProtectedRoute>
          } />
          <Route path="/catalogo/analytics" element={
            <ProtectedRoute adminOnly>
              <WidgetAnalytics />
            </ProtectedRoute>
          } />
          <Route path="/landing/editor" element={
            <ProtectedRoute adminOnly>
              <LandingEditor />
            </ProtectedRoute>
          } />
          <Route path="/flujo" element={
            <ProtectedRoute adminOnly>
              <FlowBuilder />
            </ProtectedRoute>
          } />
          <Route path="/broadcast" element={
            <ProtectedRoute adminOnly>
              <Broadcast />
            </ProtectedRoute>
          } />
          <Route path="/marketing" element={
            <ProtectedRoute adminOnly>
              <MarketingEffectiveness />
            </ProtectedRoute>
          } />
          <Route path="/auditoria" element={
            <ProtectedRoute adminOnly>
              <AuditLog />
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

import * as Sentry from '@sentry/react';

function ErrorFallback({ error, resetError }) {
  return (
    <div style={{
      minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '2rem', textAlign: 'center', fontFamily: 'system-ui, sans-serif',
    }}>
      <div style={{ maxWidth: 460 }}>
        <div style={{ fontSize: '2.4rem', marginBottom: '0.5rem' }}>⚠️</div>
        <h1 style={{ fontSize: '1.4rem', margin: '0 0 0.6rem', color: '#111827' }}>
          Algo salió mal
        </h1>
        <p style={{ color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Ya recibimos el reporte del error. Nuestro equipo lo va a revisar.
        </p>
        <button
          onClick={resetError}
          style={{
            padding: '10px 20px', background: '#6366f1', color: '#fff',
            border: 0, borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600,
          }}
          data-testid="error-boundary-retry"
        >
          Recargar
        </button>
      </div>
    </div>
  );
}

function App() {
  return (
    <Sentry.ErrorBoundary fallback={({ error, resetError }) => <ErrorFallback error={error} resetError={resetError} />}>
      <BrowserRouter>
        <AuthProvider>
          <NotificationProvider>
            <AppContent />
          </NotificationProvider>
        </AuthProvider>
      </BrowserRouter>
    </Sentry.ErrorBoundary>
  );
}

export default App;
