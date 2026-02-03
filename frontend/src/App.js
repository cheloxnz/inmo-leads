import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { Toaster } from 'sonner';
import Dashboard from './pages/Dashboard';
import Leads from './pages/Leads';
import LeadDetail from './pages/LeadDetail';
import FlowVisualization from './pages/FlowVisualization';
import Configuration from './pages/Configuration';
import Documentation from './pages/Documentation';
import '@/App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

function Navigation() {
  const location = useLocation();
  
  const isActive = (path) => location.pathname === path;
  
  return (
    <nav className="nav-sidebar">
      <div className="nav-logo">
        <div className="logo-icon">🏠</div>
        <h1>InmoBot AI</h1>
      </div>
      
      <div className="nav-links">
        <Link 
          to="/" 
          className={`nav-link ${isActive('/') ? 'active' : ''}`}
          data-testid="nav-dashboard"
        >
          <span className="icon">📊</span>
          <span>Dashboard</span>
        </Link>
        
        <Link 
          to="/leads" 
          className={`nav-link ${isActive('/leads') ? 'active' : ''}`}
          data-testid="nav-leads"
        >
          <span className="icon">👥</span>
          <span>Leads</span>
        </Link>
        
        <Link 
          to="/flow" 
          className={`nav-link ${isActive('/flow') ? 'active' : ''}`}
          data-testid="nav-flow"
        >
          <span className="icon">🔄</span>
          <span>Flujo Bot</span>
        </Link>
        
        <Link 
          to="/config" 
          className={`nav-link ${isActive('/config') ? 'active' : ''}`}
          data-testid="nav-config"
        >
          <span className="icon">⚙️</span>
          <span>Configuración</span>
        </Link>
        
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
        <div className="status-indicator">
          <div className="status-dot"></div>
          <span>Bot Activo</span>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:phone" element={<LeadDetail />} />
            <Route path="/flow" element={<FlowVisualization />} />
            <Route path="/config" element={<Configuration />} />
            <Route path="/docs" element={<Documentation />} />
          </Routes>
        </main>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;