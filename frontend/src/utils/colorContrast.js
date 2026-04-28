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
  const ratioWhite = contrastRatio(primary, '#ffffff');
  const ratioBlack = contrastRatio(primary, '#000000');
  const bestRatio = Math.max(ratioWhite, ratioBlack);
  const bestText = ratioWhite >= ratioBlack ? '#ffffff' : '#000000';

  let level = 'fail';
  let message = '';
  if (bestRatio >= 7) {
    level = 'aaa';
    message = `Excelente contraste (${bestRatio.toFixed(1)}:1) — WCAG AAA`;
  } else if (bestRatio >= 4.5) {
    level = 'aa';
    message = `Buen contraste (${bestRatio.toFixed(1)}:1) — WCAG AA`;
  } else if (bestRatio >= 3) {
    level = 'aa-large';
    message = `Contraste limitado (${bestRatio.toFixed(1)}:1) — solo apto para texto grande/UI`;
  } else {
    level = 'fail';
    message = `Contraste insuficiente (${bestRatio.toFixed(1)}:1) — el texto puede ser ilegible`;
  }
  return { level, message, bestRatio, bestText };
}
