/**
 * Calcula el contraste (WCAG 2.1) entre dos colores hex.
 * Retorna ratio: 1 (idéntico) - 21 (negro vs blanco).
 *
 * Pasa AA: ratio >= 4.5 (texto normal), ratio >= 3 (texto grande/UI)
 * Pasa AAA: ratio >= 7
 */
function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return null;
  return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
}

function relativeLuminance(rgb) {
  const [r, g, b] = rgb.map(c => {
    const cs = c / 255;
    return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(c1, c2) {
  const rgb1 = hexToRgb(c1);
  const rgb2 = hexToRgb(c2);
  if (!rgb1 || !rgb2) return 0;
  const l1 = relativeLuminance(rgb1);
  const l2 = relativeLuminance(rgb2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function evaluateColorContrast(primary) {
  // Evaluamos contraste contra los 2 backgrounds reales que usa la landing:
  // - Texto del CTA blanco sobre el color (badge, step-number, button bg)
  // - El color sobre fondo claro (#fafafa) cuando se usa como icon/accent
  const ratioOnWhite = contrastRatio(primary, '#ffffff');
  const ratioOnLightBg = contrastRatio(primary, '#fafafa');
  // El "peor caso" relevante: el color como elemento sobre fondo claro
  // (lo que ven los usuarios al usar el primary_color como ícono/border).
  const worstUseCase = Math.min(ratioOnWhite, ratioOnLightBg);

  let level = 'fail';
  let message = '';
  if (worstUseCase >= 7) {
    level = 'aaa';
    message = `Excelente contraste (${worstUseCase.toFixed(1)}:1) — WCAG AAA`;
  } else if (worstUseCase >= 4.5) {
    level = 'aa';
    message = `Buen contraste (${worstUseCase.toFixed(1)}:1) — WCAG AA`;
  } else if (worstUseCase >= 3) {
    level = 'aa-large';
    message = `Contraste limitado (${worstUseCase.toFixed(1)}:1) — solo apto para texto grande/UI`;
  } else {
    level = 'fail';
    message = `Contraste insuficiente (${worstUseCase.toFixed(1)}:1) — el texto blanco será ilegible`;
  }
  return { level, message, bestRatio: worstUseCase, bestText: '#ffffff' };
}

/**
 * Evalúa la coherencia entre primary y accent.
 * Si son MUY similares (ratio < 1.5), advierte (paleta aburrida/poco diferenciada).
 * Si son MUY contrastantes (ratio > 12), advierte (paleta caótica).
 * Ideal: 2-8.
 */
export function evaluatePaletteHarmony(primary, accent) {
  const ratio = contrastRatio(primary, accent);
  if (ratio === 0) return { level: 'ok', message: '' };
  if (ratio < 1.5) {
    return {
      level: 'warn-low',
      message: `Los colores son casi idénticos (${ratio.toFixed(1)}:1). El acento no se va a notar.`
    };
  }
  if (ratio > 14) {
    return {
      level: 'warn-high',
      message: `Combinación muy contrastante (${ratio.toFixed(1)}:1). Puede verse agresiva.`
    };
  }
  if (ratio >= 2 && ratio <= 8) {
    return {
      level: 'ok',
      message: `Paleta coherente (ratio ${ratio.toFixed(1)}:1).`
    };
  }
  return { level: 'ok', message: '' };
}
