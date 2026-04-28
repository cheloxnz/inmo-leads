/**
 * Detecta el tenant_id desde el subdominio del hostname.
 * Solo activa si REACT_APP_PLATFORM_DOMAIN esta configurado y el hostname termina con ese dominio.
 *
 * Ejemplos:
 *   PLATFORM=inmobot.app
 *   "clinica.inmobot.app" -> "clinica"
 *   "demo-clinica.inmobot.app" -> "demo-clinica"
 *   "www.inmobot.app" -> null (reservado)
 *   "inmobot.app" -> null (sin subdominio)
 *   "preview.emergentagent.com" -> null (no matchea PLATFORM)
 */
const RESERVED_SUBDOMAINS = new Set([
  'www', 'app', 'api', 'admin', 'panel', 'dashboard',
  'auth', 'mail', 'static', 'cdn', 'assets', 'preview',
  'staging', 'dev', 'demo'
]);

export function getTenantFromSubdomain(hostname = window.location.hostname) {
  const platform = process.env.REACT_APP_PLATFORM_DOMAIN;
  if (!platform) return null;

  const host = hostname.toLowerCase();
  const platformLow = platform.toLowerCase().replace(/^\./, '');

  if (host === platformLow) return null; // root domain
  if (!host.endsWith('.' + platformLow)) return null; // no matchea

  const subdomainPart = host.slice(0, host.length - platformLow.length - 1);
  // Si tiene mas dots, ej "x.y.platform.com" → no soportamos sub-sub yet
  if (subdomainPart.includes('.')) return null;

  if (RESERVED_SUBDOMAINS.has(subdomainPart)) return null;

  // tenant_id valido: lowercase alphanum + dashes
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(subdomainPart)) return null;

  return subdomainPart;
}
