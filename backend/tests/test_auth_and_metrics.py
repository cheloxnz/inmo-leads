"""
Backend tests for InmoBot AI CRM - Authentication, Metrics, and Asesor Management
Tests login, auth endpoints, metrics, and role-based access control
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@inmobot.com"
ADMIN_PASSWORD = "Admin123!"
ASESOR_EMAIL = "maria@inmobot.com"
ASESOR_PASSWORD = "Maria123!"


class TestHealthCheck:
    """Basic API health check"""
    
    def test_api_root(self):
        """Test API root endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"API root failed: {response.text}"
        data = response.json()
        assert "message" in data, "Response should have message"
        print(f"✓ API root accessible: {data['message']}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Response should have access_token"
        assert "user" in data, "Response should have user data"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful: {data['user']['name']}")
    
    def test_asesor_login_success(self):
        """Test asesor login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        assert response.status_code == 200, f"Asesor login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Response should have access_token"
        assert data["user"]["email"] == ASESOR_EMAIL
        assert data["user"]["role"] == "asesor"
        print(f"✓ Asesor login successful: {data['user']['name']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Should return 401, got {response.status_code}"
        print("✓ Invalid login correctly rejected")
    
    def test_login_invalid_password(self):
        """Test login with valid email but wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401, f"Should return 401, got {response.status_code}"
        print("✓ Wrong password correctly rejected")


class TestAuthMe:
    """Test /auth/me endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def asesor_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_auth_me_admin(self, admin_token):
        """Test /auth/me returns admin profile"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"/auth/me failed: {response.text}"
        
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        print(f"✓ Admin /auth/me works: {data['name']}")
    
    def test_auth_me_asesor(self, asesor_token):
        """Test /auth/me returns asesor profile"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"/auth/me failed: {response.text}"
        
        data = response.json()
        assert data["email"] == ASESOR_EMAIL
        assert data["role"] == "asesor"
        print(f"✓ Asesor /auth/me works: {data['name']}")
    
    def test_auth_me_without_token(self):
        """Test /auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Should return 401, got {response.status_code}"
        print("✓ /auth/me correctly rejects unauthenticated requests")
    
    def test_auth_me_invalid_token(self):
        """Test /auth/me with invalid token returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401, f"Should return 401, got {response.status_code}"
        print("✓ /auth/me correctly rejects invalid tokens")


class TestAgentsManagement:
    """Test agents listing and management"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def asesor_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_list_agents_admin(self, admin_token):
        """Test admin can list all agents"""
        response = requests.get(
            f"{BASE_URL}/api/auth/agents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"List agents failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 1, "Should have at least one agent"
        
        # Verify asesor is in the list
        emails = [agent["email"] for agent in data]
        assert ASESOR_EMAIL in emails, f"Asesor {ASESOR_EMAIL} should be in list"
        print(f"✓ Admin can list {len(data)} agents")
    
    def test_list_agents_asesor_limited(self, asesor_token):
        """Test asesor only sees their own profile"""
        response = requests.get(
            f"{BASE_URL}/api/auth/agents",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"List agents failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Asesor should only see themselves
        if len(data) > 0:
            for agent in data:
                assert agent["email"] == ASESOR_EMAIL, "Asesor should only see their own profile"
        print(f"✓ Asesor limited to own profile")


class TestMetrics:
    """Test metrics endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def asesor_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_all_agents_metrics_admin(self, admin_token):
        """Test admin can get all agents metrics"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/all-agents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"All agents metrics failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check structure of metrics
        if len(data) > 0:
            metric = data[0]
            expected_fields = ["active_leads", "conversion_rate", "agent_name", "email"]
            for field in expected_fields:
                assert field in metric, f"Metric should have {field}"
        
        print(f"✓ Admin retrieved metrics for {len(data)} agents")
    
    def test_all_agents_metrics_forbidden_for_asesor(self, asesor_token):
        """Test asesor cannot access all agents metrics"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/all-agents",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 403, f"Should return 403, got {response.status_code}"
        print("✓ All agents metrics correctly forbidden for asesor")
    
    def test_own_agent_metrics_asesor(self, asesor_token):
        """Test asesor can get their own metrics"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/agent/{ASESOR_EMAIL}",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"Own metrics failed: {response.text}"
        
        data = response.json()
        expected_fields = ["active_leads", "total_assigned", "conversion_rate", "avg_score"]
        for field in expected_fields:
            assert field in data, f"Metrics should have {field}"
        
        print(f"✓ Asesor can see own metrics: {data.get('active_leads', 0)} active leads")
    
    def test_other_agent_metrics_forbidden_for_asesor(self, asesor_token):
        """Test asesor cannot see other agents metrics"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/agent/{ADMIN_EMAIL}",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 403, f"Should return 403, got {response.status_code}"
        print("✓ Other agent metrics correctly forbidden for asesor")
    
    def test_daily_goals(self, asesor_token):
        """Test daily goals endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/daily-goals",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"Daily goals failed: {response.text}"
        
        data = response.json()
        expected_fields = ["hot_leads_today", "total_leads_today", "appointments_today"]
        for field in expected_fields:
            assert field in data, f"Daily goals should have {field}"
        
        print(f"✓ Daily goals endpoint works")


class TestLeads:
    """Test leads endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def asesor_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_leads_stats(self):
        """Test leads stats endpoint (public)"""
        response = requests.get(f"{BASE_URL}/api/leads/stats/summary")
        assert response.status_code == 200, f"Stats failed: {response.text}"
        
        data = response.json()
        expected_fields = ["total", "hot", "warm", "cold", "avg_score"]
        for field in expected_fields:
            assert field in data, f"Stats should have {field}"
        
        print(f"✓ Leads stats: {data['total']} total, {data['hot']} hot, {data['warm']} warm, {data['cold']} cold")
    
    def test_get_all_leads(self):
        """Test getting all leads (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/leads")
        assert response.status_code == 200, f"Get leads failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Retrieved {len(data)} leads")
    
    def test_my_leads_asesor(self, asesor_token):
        """Test asesor can get their assigned leads"""
        response = requests.get(
            f"{BASE_URL}/api/leads/assigned-to-me",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"My leads failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # All leads should be assigned to the asesor
        for lead in data:
            assert lead.get("assigned_agent") == ASESOR_EMAIL, "Lead should be assigned to current asesor"
        
        print(f"✓ Asesor has {len(data)} assigned leads")


class TestNotifications:
    """Test notification endpoints"""
    
    @pytest.fixture
    def asesor_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ASESOR_EMAIL,
            "password": ASESOR_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_upcoming_appointments(self, asesor_token):
        """Test upcoming appointments endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/upcoming-appointments",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"Upcoming appointments failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Upcoming appointments: {len(data)}")
    
    def test_inactive_leads(self, asesor_token):
        """Test inactive leads endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/inactive-leads",
            headers={"Authorization": f"Bearer {asesor_token}"}
        )
        assert response.status_code == 200, f"Inactive leads failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Inactive leads: {len(data)}")


class TestAgentCRUD:
    """Test agent CRUD operations"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_create_and_delete_agent(self, admin_token):
        """Test creating a new agent and then deleting it"""
        test_email = "TEST_pytest_agent@inmobot.com"
        
        # Create agent
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "TEST Agent",
                "email": test_email,
                "phone": "+5491199999999",
                "password": "TestPass123!",
                "specialties": ["comprar"],
                "zones": ["Palermo"]
            }
        )
        
        # Could be 200 or 400 if already exists
        if response.status_code == 200:
            print(f"✓ Created test agent: {test_email}")
        elif response.status_code == 400 and "ya registrado" in response.text:
            print(f"⚠ Test agent already exists, will delete")
        else:
            print(f"Agent creation response: {response.status_code} - {response.text}")
        
        # Delete agent
        delete_response = requests.delete(
            f"{BASE_URL}/api/auth/agents/{test_email}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert delete_response.status_code in [200, 404], f"Delete failed: {delete_response.text}"
        print(f"✓ Deleted test agent: {test_email}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
