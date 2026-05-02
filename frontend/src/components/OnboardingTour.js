import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { API } from '../App';
import { X, ArrowRight, ArrowLeft, Rocket, Sparkles } from 'lucide-react';

/**
 * Secuencia de onboarding para admins/tenants nuevos.
 * - Corre una sola vez (flag persistido en el agente).
 * - Cada step puede tener `testid` (resalta un elemento) o ser "intro" full-screen.
 * - Navega automáticamente entre páginas.
 */
const STEPS = [
  {
    id: 'welcome',
    kind: 'intro',
    title: '¡Bienvenido a InmoBot! 🚀',
    body: 'En 2 minutos te muestro cómo sacar tu primer lead automático por WhatsApp. ¿Listo?',
    primaryLabel: 'Empezar tour',
  },
  {
    id: 'whatsapp',
    kind: 'highlight',
    path: '/config',
    testid: 'whatsapp-section',
    title: 'Conectá tu WhatsApp',
    body: 'Acá pegás las credenciales de Meta WhatsApp Cloud API. Sin esto el bot no puede responder.',
    placement: 'right',
  },
  {
    id: 'catalog',
    kind: 'highlight',
    path: '/catalogo',
    testid: 'btn-bulk-import',
    title: 'Subí tu catálogo',
    body: 'Si tenés muchos productos usá "Importar CSV" o agregalos uno por uno con "Nuevo Producto". El bot va a usar estos datos para responder preguntas.',
    placement: 'bottom',
  },
  {
    id: 'flow',
    kind: 'intro',
    path: '/flujo',
    title: 'Diseñá tu flujo del bot',
    body: 'Desde acá configurás las preguntas del bot (zona, presupuesto, tipo). InmoBot viene con un template base listo para usar.',
  },
  {
    id: 'kanban',
    kind: 'intro',
    path: '/kanban',
    title: 'Seguí leads en el Kanban',
    body: 'Cuando entren leads por WhatsApp, los vas a ver acá organizados por estado: Nuevos → Calificados → Cita → Cerrados.',
  },
  {
    id: 'roi',
    kind: 'highlight',
    path: '/',
    testid: 'roi-card',
    title: 'Medí tu ROI en tiempo real',
    body: 'Este panel te muestra cuánto pipeline, tiempo y demanda generó InmoBot para vos. Se actualiza automáticamente.',
    placement: 'bottom',
  },
  {
    id: 'done',
    kind: 'intro',
    title: '¡Ya estás listo! 🎉',
    body: 'Mandale un mensaje a tu WhatsApp conectado y vas a ver el bot responder en segundos. Si necesitás ayuda, hay un chat de soporte en la esquina inferior.',
    primaryLabel: 'Terminar',
  },
];

export default function OnboardingTour() {
  const [show, setShow] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [targetRect, setTargetRect] = useState(null);
  const navigate = useNavigate();
  const lastPathRef = useRef('');

  // Chequea si el usuario ya completó onboarding
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;
    axios.get(`${API}/auth/onboarding/status`).then(res => {
      if (!res.data.completed) {
        setShow(true);
      }
    }).catch(() => {});
  }, []);

  const step = STEPS[stepIdx];

  // Navega a la página del step y mide el target
  useEffect(() => {
    if (!show || !step) return;
    if (step.path && window.location.pathname !== step.path && lastPathRef.current !== step.path) {
      lastPathRef.current = step.path;
      navigate(step.path);
    }
    if (step.kind === 'highlight' && step.testid) {
      const measure = () => {
        const el = document.querySelector(`[data-testid="${step.testid}"]`);
        if (el) {
          el.scrollIntoView({ block: 'center', behavior: 'smooth' });
          setTimeout(() => {
            const rect = el.getBoundingClientRect();
            setTargetRect({
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
            });
          }, 400);
        } else {
          setTargetRect(null);
        }
      };
      const t = setTimeout(measure, 600);
      window.addEventListener('resize', measure);
      return () => { clearTimeout(t); window.removeEventListener('resize', measure); };
    } else {
      setTargetRect(null);
    }
  }, [stepIdx, show, step, navigate]);

  const finish = useCallback(async (skipped = false) => {
    try {
      await axios.post(`${API}/auth/onboarding/complete`, { skipped });
    } catch {}
    setShow(false);
    setStepIdx(0);
  }, []);

  const next = () => {
    if (stepIdx < STEPS.length - 1) setStepIdx(stepIdx + 1);
    else finish(false);
  };
  const prev = () => stepIdx > 0 && setStepIdx(stepIdx - 1);

  if (!show || !step) return null;

  // Tooltip position for highlight step
  let tooltipStyle = {};
  if (step.kind === 'highlight' && targetRect) {
    const placement = step.placement || 'bottom';
    const margin = 16;
    if (placement === 'bottom') {
      tooltipStyle = {
        top: Math.min(targetRect.top + targetRect.height + margin, window.innerHeight - 260),
        left: Math.max(20, Math.min(targetRect.left, window.innerWidth - 380)),
      };
    } else if (placement === 'right') {
      tooltipStyle = {
        top: Math.max(20, targetRect.top),
        left: Math.min(targetRect.left + targetRect.width + margin, window.innerWidth - 380),
      };
    } else if (placement === 'top') {
      tooltipStyle = {
        top: Math.max(20, targetRect.top - 220),
        left: Math.max(20, targetRect.left),
      };
    }
  }

  return (
    <div className="onboarding-root" data-testid="onboarding-tour">
      {step.kind === 'highlight' && targetRect ? (
        <>
          {/* 4 rectángulos alrededor del target para dejar hueco brillante */}
          <div className="onboarding-mask onboarding-mask-top" style={{ height: targetRect.top - 8 }} />
          <div
            className="onboarding-mask onboarding-mask-bottom"
            style={{ top: targetRect.top + targetRect.height + 8, height: `calc(100vh - ${targetRect.top + targetRect.height + 8}px)` }}
          />
          <div
            className="onboarding-mask onboarding-mask-left"
            style={{ top: targetRect.top - 8, left: 0, width: targetRect.left - 8, height: targetRect.height + 16 }}
          />
          <div
            className="onboarding-mask onboarding-mask-right"
            style={{ top: targetRect.top - 8, left: targetRect.left + targetRect.width + 8, width: `calc(100vw - ${targetRect.left + targetRect.width + 8}px)`, height: targetRect.height + 16 }}
          />
          <div
            className="onboarding-highlight-ring"
            style={{
              top: targetRect.top - 6,
              left: targetRect.left - 6,
              width: targetRect.width + 12,
              height: targetRect.height + 12,
            }}
          />
          <div className="onboarding-tooltip" style={tooltipStyle}>
            <StepContent step={step} stepIdx={stepIdx} total={STEPS.length} onNext={next} onPrev={prev} onSkip={() => finish(true)} />
          </div>
        </>
      ) : (
        <div className="onboarding-intro-backdrop" onClick={() => finish(true)}>
          <div className="onboarding-intro-card" onClick={e => e.stopPropagation()}>
            <div className="onboarding-intro-icon">
              {stepIdx === 0 ? <Rocket className="w-8 h-8" /> : stepIdx === STEPS.length - 1 ? <Sparkles className="w-8 h-8" /> : <Sparkles className="w-8 h-8" />}
            </div>
            <StepContent step={step} stepIdx={stepIdx} total={STEPS.length} onNext={next} onPrev={prev} onSkip={() => finish(true)} isIntro />
          </div>
        </div>
      )}
    </div>
  );
}

function StepContent({ step, stepIdx, total, onNext, onPrev, onSkip, isIntro }) {
  const isLast = stepIdx === total - 1;
  return (
    <>
      <button className="onboarding-close" onClick={onSkip} title="Saltar" data-testid="onboarding-skip">
        <X className="w-4 h-4" />
      </button>
      <div className="onboarding-progress" data-testid="onboarding-progress">
        <span>{stepIdx + 1} / {total}</span>
        <div className="onboarding-progress-bar">
          <div style={{ width: `${((stepIdx + 1) / total) * 100}%` }} />
        </div>
      </div>
      <h3 className={isIntro ? 'onboarding-title-big' : 'onboarding-title'}>{step.title}</h3>
      <p className={isIntro ? 'onboarding-body-big' : 'onboarding-body'}>{step.body}</p>
      <div className="onboarding-actions">
        {stepIdx > 0 && (
          <button className="onboarding-btn onboarding-btn-secondary" onClick={onPrev} data-testid="onboarding-prev">
            <ArrowLeft className="w-3 h-3" /> Atrás
          </button>
        )}
        <button className="onboarding-btn onboarding-btn-primary" onClick={onNext} data-testid="onboarding-next">
          {isLast ? (step.primaryLabel || 'Terminar') : (step.primaryLabel || 'Siguiente')}
          {!isLast && <ArrowRight className="w-3 h-3" />}
        </button>
      </div>
    </>
  );
}
