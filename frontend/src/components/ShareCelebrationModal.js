import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { X, Download, Copy, Twitter, Linkedin, Loader2, Sparkles } from 'lucide-react';

const CARD_W = 1200;
const CARD_H = 630;

/* Dibuja la celebration card en un canvas usando branding del tenant. */
function drawCard(canvas, data) {
  const ctx = canvas.getContext('2d');
  // Fondo: gradient diagonal usando primary -> accent
  const grad = ctx.createLinearGradient(0, 0, CARD_W, CARD_H);
  grad.addColorStop(0, data.primary_color || '#3b82f6');
  grad.addColorStop(1, data.accent_color || '#8b5cf6');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  // Overlay sutil
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  for (let i = 0; i < 12; i++) {
    ctx.beginPath();
    ctx.arc(Math.random() * CARD_W, Math.random() * CARD_H, Math.random() * 80 + 20, 0, Math.PI * 2);
    ctx.fill();
  }

  // Card blanca con padding
  const PAD = 60;
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.roundRect(PAD, PAD, CARD_W - 2 * PAD, CARD_H - 2 * PAD, 32);
  ctx.fill();

  // Emoji grande
  ctx.font = 'bold 140px system-ui, -apple-system, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillStyle = '#0f172a';
  ctx.fillText(data.emoji || '🎉', PAD + 60, PAD + 180);

  // Título (multi-line manual)
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 56px system-ui, -apple-system, sans-serif';
  const title = (data.title || '').replace(/^[^\w\sáéíóúñÁÉÍÓÚÑ¡!]+\s*/u, ''); // quitar emoji inicial
  wrapText(ctx, title, PAD + 60, PAD + 280, CARD_W - 2 * PAD - 120, 70);

  // Métrica grande si hay
  if (data.metric) {
    ctx.fillStyle = data.primary_color || '#3b82f6';
    ctx.font = 'bold 100px system-ui, -apple-system, sans-serif';
    ctx.fillText(`${data.metric}`, PAD + 60, PAD + 460);
  }

  // Footer: nombre del negocio + Powered by
  ctx.font = 'bold 32px system-ui, -apple-system, sans-serif';
  ctx.fillStyle = '#475569';
  ctx.textAlign = 'left';
  ctx.fillText(data.business_name || '', PAD + 60, CARD_H - PAD - 60);

  ctx.font = '24px system-ui, -apple-system, sans-serif';
  ctx.fillStyle = '#94a3b8';
  ctx.textAlign = 'right';
  ctx.fillText(`✨ Hecho con ${data.powered_by || 'InmoBot AI'}`, CARD_W - PAD - 60, CARD_H - PAD - 60);
}

function wrapText(ctx, text, x, y, maxW, lineH) {
  const words = (text || '').split(' ');
  let line = '';
  let yy = y;
  for (let i = 0; i < words.length; i++) {
    const test = line + words[i] + ' ';
    if (ctx.measureText(test).width > maxW && i > 0) {
      ctx.fillText(line.trim(), x, yy);
      line = words[i] + ' ';
      yy += lineH;
    } else {
      line = test;
    }
  }
  ctx.fillText(line.trim(), x, yy);
}

export default function ShareCelebrationModal({ celebration, onClose }) {
  const canvasRef = useRef(null);
  const [cardData, setCardData] = useState(null);
  const [shareText, setShareText] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        // Track con platform=unknown para fetchear card_data + share_text iniciales
        const r = await axios.post(
          `${API}/coach/celebrations/${celebration.celebration_id}/share`,
          { platform: 'unknown' },
        );
        if (!alive) return;
        setCardData(r.data.card_data);
        setShareText(r.data.share_text);
      } catch (e) {
        // fallback con datos del prop
        setCardData({
          emoji: celebration.emoji,
          title: celebration.title,
          body: celebration.body,
          metric: celebration.metric,
          business_name: 'Mi negocio',
          primary_color: '#3b82f6',
          accent_color: '#8b5cf6',
          powered_by: 'InmoBot AI',
        });
        setShareText(`${celebration.emoji || '🎉'} ${celebration.title} con InmoBot AI 🚀`);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [celebration.celebration_id, celebration.emoji, celebration.title, celebration.body, celebration.metric]);

  useEffect(() => {
    if (!cardData || !canvasRef.current) return;
    drawCard(canvasRef.current, cardData);
  }, [cardData]);

  const trackPlatform = async (platform) => {
    try {
      await axios.post(
        `${API}/coach/celebrations/${celebration.celebration_id}/share`,
        { platform },
      );
    } catch { /* silencioso */ }
  };

  const downloadImage = async () => {
    if (!canvasRef.current) return;
    setBusy(true);
    try {
      const dataUrl = canvasRef.current.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `celebracion-${celebration.celebration_type}.png`;
      link.href = dataUrl;
      link.click();
      await trackPlatform('download');
      toast.success('Imagen descargada — adjuntala a tu post');
    } finally {
      setBusy(false);
    }
  };

  const copyImage = async () => {
    if (!canvasRef.current) return;
    setBusy(true);
    try {
      canvasRef.current.toBlob(async (blob) => {
        try {
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
          await trackPlatform('copy');
          toast.success('Imagen copiada — pegala en cualquier post');
        } catch (e) {
          toast.error('Tu navegador no soporta copiar imagen, usá Descargar');
        } finally {
          setBusy(false);
        }
      }, 'image/png');
    } catch {
      setBusy(false);
    }
  };

  const shareTwitter = async () => {
    await trackPlatform('twitter');
    const intent = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`;
    window.open(intent, '_blank', 'noopener,noreferrer,width=600,height=600');
  };

  const shareLinkedIn = async () => {
    await trackPlatform('linkedin');
    // LinkedIn requiere URL para preview con OG image; usamos el origin de la app
    const url = window.location.origin;
    const intent = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
    window.open(intent, '_blank', 'noopener,noreferrer,width=600,height=600');
  };

  return (
    <div
      data-testid="share-celebration-modal"
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-6 border-b">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            Compartí tu logro
          </h3>
          <button
            data-testid="share-modal-close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700"
            aria-label="Cerrar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-gray-600">
            Generamos una imagen lista para postear en redes con tu marca. Descargala y subila a LinkedIn, X, Instagram o donde quieras.
          </p>

          <div className="bg-gray-100 rounded-lg p-2 flex items-center justify-center min-h-[300px]">
            {loading ? (
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            ) : (
              <canvas
                ref={canvasRef}
                width={CARD_W}
                height={CARD_H}
                data-testid="share-canvas"
                className="max-w-full h-auto rounded-md shadow-md"
                style={{ aspectRatio: `${CARD_W}/${CARD_H}` }}
              />
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="share-download-btn"
              onClick={downloadImage}
              disabled={busy || loading}
            >
              <Download className="w-4 h-4 mr-2" /> Descargar imagen
            </Button>
            <Button
              data-testid="share-copy-btn"
              variant="outline"
              onClick={copyImage}
              disabled={busy || loading}
            >
              <Copy className="w-4 h-4 mr-2" /> Copiar
            </Button>
            <Button
              data-testid="share-twitter-btn"
              variant="outline"
              onClick={shareTwitter}
              className="border-[#1DA1F2] text-[#1DA1F2] hover:bg-[#1DA1F2]/10"
            >
              <Twitter className="w-4 h-4 mr-2" /> X / Twitter
            </Button>
            <Button
              data-testid="share-linkedin-btn"
              variant="outline"
              onClick={shareLinkedIn}
              className="border-[#0A66C2] text-[#0A66C2] hover:bg-[#0A66C2]/10"
            >
              <Linkedin className="w-4 h-4 mr-2" /> LinkedIn
            </Button>
          </div>

          {shareText && (
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 text-xs text-gray-600">
              <p className="font-semibold mb-1 text-gray-700">Texto sugerido:</p>
              <p className="whitespace-pre-line">{shareText}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
