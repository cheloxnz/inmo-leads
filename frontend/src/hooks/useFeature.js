import { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';

/**
 * Hook para chequear feature flags del tenant actual.
 *
 * Cachea el resultado a nivel modulo para evitar fetch en cada render.
 *
 * Uso:
 *   const { hasFeature, loading } = useFeatures();
 *   {hasFeature('mortgage_calculator') && <MortgageCalculator />}
 *
 * Fuente: GET /api/auth/tenant/branding (campo `features`).
 */

let _cache = null;
let _cachePromise = null;

const fetchFeatures = async () => {
  if (_cache) return _cache;
  if (_cachePromise) return _cachePromise;
  _cachePromise = axios
    .get(`${API}/auth/tenant/branding`)
    .then((r) => {
      _cache = r.data?.features || {};
      _cachePromise = null;
      return _cache;
    })
    .catch(() => {
      _cachePromise = null;
      return {};
    });
  return _cachePromise;
};

export const invalidateFeaturesCache = () => {
  _cache = null;
  _cachePromise = null;
};

export function useFeatures() {
  const [features, setFeatures] = useState(_cache || {});
  const [loading, setLoading] = useState(_cache === null);

  useEffect(() => {
    let alive = true;
    fetchFeatures().then((f) => {
      if (alive) {
        setFeatures(f);
        setLoading(false);
      }
    });
    return () => { alive = false; };
  }, []);

  const hasFeature = (name) => Boolean(features[name]);
  return { features, hasFeature, loading };
}

export function useFeature(name) {
  const { hasFeature, loading } = useFeatures();
  return { enabled: hasFeature(name), loading };
}
