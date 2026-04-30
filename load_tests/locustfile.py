"""Locust stress test para InmoBot SaaS.

Simula tráfico realista contra los endpoints públicos y autenticados más
expuestos al riesgo de carga (health, login, branding, ai-summary).

Uso:
    pip install locust
    cd /app/load_tests
    locust -f locustfile.py --host=https://inmobot-preview.preview.emergentagent.com

Luego abrir http://localhost:8089 y configurar:
    - Number of users: 50 (ramp up gradual a 100)
    - Spawn rate: 5 users/sec
    - Run time: 5m

Métricas a observar:
    - p95 < 800ms para /api/health/ping
    - p95 < 1500ms para /api/auth/login
    - 0 errores 5xx (los 401/429 son esperados en algunos endpoints)
    - Throughput estable sin degradación a partir de ~50 RPS

Para correr en modo CLI sin web UI:
    locust -f locustfile.py --host=https://inmobot-preview.preview.emergentagent.com \\
           --headless -u 50 -r 5 -t 5m --print-stats
"""
import os
import random
from locust import HttpUser, task, between, events

DEMO_EMAIL = os.environ.get("LOAD_TEST_EMAIL", "demo@inmobot.com")
DEMO_PASSWORD = os.environ.get("LOAD_TEST_PASSWORD", "Demo123!")


class PublicVisitor(HttpUser):
    """Visitante público que pingea endpoints sin auth.

    Simula carga de UptimeRobot, embedders del widget, crawlers que vean meta
    tags de share pages, y usuarios que visiten landing pages dinámicas.
    """
    weight = 5  # 5x más visitantes que usuarios autenticados (típico)
    wait_time = between(1, 4)

    @task(20)
    def health_ping(self):
        """UptimeRobot-style ping. Debe ser SUPER rápido y nunca fallar."""
        with self.client.get("/api/health/ping", name="/api/health/ping",
                             catch_response=True) as r:
            if r.status_code == 200 and r.json().get("status") == "ok":
                r.success()
            else:
                r.failure(f"ping fail: {r.status_code} {r.text[:80]}")

    @task(5)
    def health_full(self):
        """Health con DB ping. Más pesado, menor frecuencia."""
        with self.client.get("/api/health", name="/api/health",
                             catch_response=True) as r:
            if r.status_code in (200, 503):
                r.success()  # 503 es válido si Mongo está degradado
            else:
                r.failure(f"health fail: {r.status_code}")

    @task(3)
    def public_landing(self):
        """Landing pública genérica (HTML root)."""
        self.client.get("/inicio", name="/inicio")

    @task(2)
    def public_changelog(self):
        """Changelog público."""
        self.client.get("/changelog", name="/changelog")

    @task(1)
    def public_catalog_unknown(self):
        """Catálogo de tenant inexistente — esperamos 404 controlado."""
        with self.client.get("/api/public/catalog/inexistente-tenant-xyz",
                             name="/api/public/catalog/[unknown]",
                             catch_response=True) as r:
            if r.status_code in (404, 400):
                r.success()
            else:
                r.failure(f"unexpected: {r.status_code}")


class AuthenticatedTenant(HttpUser):
    """Cliente autenticado simulando uso real del dashboard.

    Hace login una vez, luego cicla por endpoints típicos de un admin viendo
    su dashboard, leads y configuración.
    """
    weight = 1
    wait_time = between(2, 6)

    def on_start(self):
        """Login una sola vez por usuario virtual."""
        r = self.client.post(
            "/api/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            name="/api/auth/login",
        )
        if r.status_code == 200:
            self.token = r.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}

    @task(10)
    def get_branding(self):
        if not self.token:
            return
        self.client.get("/api/auth/tenant/branding", headers=self.headers,
                        name="/api/auth/tenant/branding")

    @task(8)
    def get_features_showcase(self):
        if not self.token:
            return
        self.client.get("/api/tenant/features-showcase", headers=self.headers,
                        name="/api/tenant/features-showcase")

    @task(5)
    def get_leads_summary(self):
        if not self.token:
            return
        self.client.get("/api/leads/stats/summary", headers=self.headers,
                        name="/api/leads/stats/summary")

    @task(3)
    def get_metrics_funnel(self):
        if not self.token:
            return
        self.client.get("/api/metrics/conversion-funnel", headers=self.headers,
                        name="/api/metrics/conversion-funnel")

    @task(2)
    def get_commissions_summary(self):
        if not self.token:
            return
        self.client.get("/api/commissions/summary", headers=self.headers,
                        name="/api/commissions/summary")

    @task(1)
    def get_coach_nudges(self):
        if not self.token:
            return
        self.client.get("/api/coach/nudges", headers=self.headers,
                        name="/api/coach/nudges")


@events.test_start.add_listener
def _on_start(environment, **_):
    print("=" * 60)
    print(f"InmoBot load test starting against: {environment.host}")
    print(f"Demo user: {DEMO_EMAIL}")
    print("Targets: p95<800ms ping, p95<1500ms login, 0 5xx errors")
    print("=" * 60)


@events.test_stop.add_listener
def _on_stop(environment, **_):
    stats = environment.runner.stats.total
    print("=" * 60)
    print(f"Total requests: {stats.num_requests}")
    print(f"Failures: {stats.num_failures} ({stats.fail_ratio * 100:.2f}%)")
    print(f"Median: {stats.median_response_time}ms | p95: {stats.get_response_time_percentile(0.95)}ms")
    print(f"RPS: {stats.total_rps:.2f}")
    print("=" * 60)
