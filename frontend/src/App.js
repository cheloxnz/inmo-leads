import React from 'react';
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
import AgentManagement from './pages/AgentManagement';
import MyDashboard from './pages/MyDashboard';
import PrivacyPolicy from './pages/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService';
import DataDeletion from './pages/DataDeletion';
import '@/App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

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

  if (!isAuthenticated) return null;

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="nav-sidebar">
      <div className="nav-logo">
        <div className="logo-icon">🏠</div>
        <h1>InmoBot AI</h1>
      </div>

      <div className="nav-links">
        {isAdmin ? (
          <>
            <Link
              to="/"
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
              data-testid="nav-dashboard"
            >
              <span className="icon">📊</span>
              <span>Dashboard General</span>
            </Link>

            <Link
              to="/leads"
              className={`nav-link ${isActive('/leads') ? 'active' : ''}`}
              data-testid="nav-leads"
            >
              <span className="icon">👥</span>
              <span>Todos los Leads</span>
            </Link>

            <Link
              to="/asesores"
              className={`nav-link ${isActive('/asesores') ? 'active' : ''}`}
              data-testid="nav-agents"
            >
              <span className="icon">👔</span>
              <span>Gestión Asesores</span>
            </Link>
          </>
        ) : (
          <>
            <Link
              to="/mi-dashboard"
              className={`nav-link ${isActive('/mi-dashboard') ? 'active' : ''}`}
              data-testid="nav-my-dashboard"
            >
              <span className="icon">📊</span>
              <span>Mi Dashboard</span>
            </Link>

            <Link
              to="/my-leads"
              className={`nav-link ${isActive('/my-leads') ? 'active' : ''}`}
              data-testid="nav-my-leads"
            >
              <span className="icon">👥</span>
              <span>Mis Leads</span>
            </Link>
          </>
        )}

        <Link
          to="/flow"
          className={`nav-link ${isActive('/flow') ? 'active' : ''}`}
          data-testid="nav-flow"
        >
          <span className="icon">🔄</span>
          <span>Flujo Bot</span>
        </Link>

        {isAdmin && (
          <Link
            to="/config"
            className={`nav-link ${isActive('/config') ? 'active' : ''}`}
            data-testid="nav-config"
          >
            <span className="icon">⚙️</span>
            <span>Configuración</span>
          </Link>
        )}

        <Link
          to="/docs"
          className={`nav-link ${isActive('/docs') ? 'active' : ''}`}
          data-testid="nav-docs"
        >
          <span className="icon">📚</span>
          <span>Documentación</span>
        </Link>
      </div>

      <div className="nav-footer">
        <div className="user-info">
          <div className="user-avatar">
            {user?.name?.charAt(0)?.toUpperCase() || 'U'}
          </div>
          <div className="user-details">
            <span className="user-name">{user?.name || 'Usuario'}</span>
            <span className="user-role">{isAdmin ? 'Administrador' : 'Asesor'}</span>
          </div>
        </div>
        <button className="logout-btn" onClick={logout} data-testid="btn-logout">
          Cerrar Sesión
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

  if (loading) {
    return <div className="loading-container">Cargando aplicación...</div>;
  }

  return (
    <div className="App">
      <Navigation />
      <main className={`main-content ${!isAuthenticated ? 'full-width' : ''}`}>
        <AppHeader />
        <Routes>
          <Route path="/login" element={
            isAuthenticated ? <Navigate to={isAdmin ? "/" : "/mi-dashboard"} replace /> : <Login />
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

          {/* Política de Privacidad - Pública */}
          <Route path="/privacy" element={<PrivacyPolicy />} />

          {/* Redirect por defecto */}
          <Route path="*" element={
            <Navigate to={isAuthenticated ? (isAdmin ? "/" : "/mi-dashboard") : "/login"} replace />
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
