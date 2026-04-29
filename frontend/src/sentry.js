/**
 * Sentry initialization (frontend).
 * Carga ANTES del render del App. PII-safe (no envía emails ni tokens en URLs).
 */
import * as Sentry from "@sentry/react";

const DSN = process.env.REACT_APP_SENTRY_DSN;

const _PII_QUERY = ["token", "access_token", "key", "api_key", "password", "secret"];

function _scrubUrl(url) {
  try {
    if (!url) return url;
    const u = new URL(url, window.location.origin);
    if (!u.search) return u.toString();
    let dirty = false;
    _PII_QUERY.forEach((k) => {
      if (u.searchParams.has(k)) {
        u.searchParams.set(k, "[scrubbed]");
        dirty = true;
      }
    });
    return dirty ? u.toString() : url;
  } catch (_) {
    return url;
  }
}

export function initSentry() {
  if (!DSN) return false;
  try {
    Sentry.init({
      dsn: DSN,
      environment: process.env.REACT_APP_SENTRY_ENVIRONMENT || "production",
      release: process.env.REACT_APP_RELEASE || undefined,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration({
          maskAllText: true,
          blockAllMedia: true,
          maskAllInputs: true,
        }),
      ],
      tracesSampleRate: parseFloat(process.env.REACT_APP_SENTRY_TRACES_SAMPLE_RATE || "0.1"),
      replaysSessionSampleRate: 0.0, // No grabar sesiones random
      replaysOnErrorSampleRate: 1.0, // Pero sí cuando hay error
      sendDefaultPii: false,
      tracePropagationTargets: [
        /^\//,
        /\/api\//,
      ],
      ignoreErrors: [
        // Errores ruidosos comunes que no son nuestros
        "ResizeObserver loop limit exceeded",
        "Non-Error promise rejection captured",
        "Network request failed",
        // Browser extensions
        "top.GLOBALS",
        /^chrome-extension/,
      ],
      denyUrls: [
        /extensions\//i,
        /^chrome:\/\//i,
        /^moz-extension:\/\//i,
      ],
      beforeSend(event) {
        try {
          if (event.request?.url) {
            event.request.url = _scrubUrl(event.request.url);
          }
          // Quitar email del user data
          if (event.user) {
            event.user = event.user.id ? { id: event.user.id } : {};
          }
          // Quitar headers Authorization si llegaron
          const headers = event.request?.headers;
          if (headers && typeof headers === "object") {
            ["Authorization", "Cookie"].forEach((h) => {
              if (h in headers) headers[h] = "[scrubbed]";
              if (h.toLowerCase() in headers) headers[h.toLowerCase()] = "[scrubbed]";
            });
          }
        } catch (_) { /* if scrub fails, drop */ }
        return event;
      },
    });
    // eslint-disable-next-line no-console
    console.info("[Sentry] initialized");
    return true;
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn("[Sentry] init failed", err);
    return false;
  }
}
