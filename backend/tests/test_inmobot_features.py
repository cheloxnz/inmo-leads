"""
InmoBot Feature Tests - Testing Kanban, Dashboard, Reports, ROI Calculator
Tests admin login, Kanban API, reports PDF, ROI calculator, navigation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@inmobot.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthCheck:
    """Health check tests"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"API root response: {data}")


class TestAdminAuthentication:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"Admin login successful: {data['user']['name']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpass"}
        )
        assert response.status_code == 401
        print("Invalid credentials correctly rejected")
    
    def test_auth_me_with_token(self):
        """Test /auth/me endpoint with valid token"""
        # First login
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        token = login_resp.json()["access_token"]
        
        # Test /auth/me
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"Auth/me returned user: {data['name']}")


class TestKanbanAPI:
    """Kanban endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_kanban_endpoint_returns_structured_data(self, admin_token):
        """Test /api/leads/kanban returns correct structure with 8 columns"""
        response = requests.get(
            f"{BASE_URL}/api/leads/kanban",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Kanban failed: {response.text}"
        data = response.json()
        
        # Expected column keys
        expected_columns = ["new", "contacted", "qualified", "appointment", "hot", "warm", "cold", "completed"]
        
        for col in expected_columns:
            assert col in data, f"Missing column: {col}"
            assert "title" in data[col], f"Column {col} missing title"
            assert "leads" in data[col], f"Column {col} missing leads array"
            assert "count" in data[col], f"Column {col} missing count"
            assert isinstance(data[col]["leads"], list), f"Column {col} leads should be a list"
        
        print(f"Kanban returned {len(data)} columns correctly")
        print(f"Column titles: {[data[col]['title'] for col in expected_columns]}")
    
    def test_kanban_requires_authentication(self):
        """Test that Kanban endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/leads/kanban")
        assert response.status_code == 401 or response.status_code == 403
        print("Kanban correctly requires authentication")


class TestDashboardMetrics:
    """Dashboard metrics tests"""
    
    def test_leads_stats_summary(self):
        """Test /api/leads/stats/summary endpoint"""
        response = requests.get(f"{BASE_URL}/api/leads/stats/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        required_fields = ["total", "hot", "warm", "cold", "with_appointment", "today", "this_week", "avg_score", "conversion_rate"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"Stats summary: Total leads={data['total']}, Hot={data['hot']}")
    
    def test_leads_by_day(self):
        """Test /api/metrics/leads-by-day endpoint"""
        response = requests.get(f"{BASE_URL}/api/metrics/leads-by-day")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Leads by day returned {len(data)} entries")
    
    def test_leads_by_status(self):
        """Test /api/metrics/leads-by-status endpoint"""
        response = requests.get(f"{BASE_URL}/api/metrics/leads-by-status")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Leads by status returned {len(data)} entries")
    
    def test_conversion_funnel(self):
        """Test /api/metrics/conversion-funnel endpoint"""
        response = requests.get(f"{BASE_URL}/api/metrics/conversion-funnel")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["total_leads", "qualified", "with_appointment", "hot_leads"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"Conversion funnel: Total={data['total_leads']}, Hot={data['hot_leads']}")


class TestPDFReports:
    """PDF reports tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_pdf_report_generation(self, admin_token):
        """Test /api/reports/pdf generates valid PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/pdf",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        
        # Check content type
        assert "application/pdf" in response.headers.get("content-type", "")
        
        # Check PDF magic bytes (PDF files start with %PDF)
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print(f"PDF generated successfully, size: {len(response.content)} bytes")
    
    def test_pdf_report_requires_admin(self):
        """Test that PDF report requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/reports/pdf")
        assert response.status_code == 401 or response.status_code == 403
        print("PDF report correctly requires authentication")


class TestROICalculator:
    """ROI calculator tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_roi_calculator_default_values(self, admin_token):
        """Test /api/calculator/roi with default values"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/roi",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"ROI calculator failed: {response.text}"
        data = response.json()
        
        # Check required sections
        assert "monthly_leads" in data
        assert "without_inmobot" in data
        assert "with_inmobot" in data
        assert "comparison" in data
        
        # Check comparison data
        assert "additional_revenue" in data["comparison"]
        assert "roi_percentage" in data["comparison"]
        
        print(f"ROI calculation: +${data['comparison']['additional_revenue']} additional revenue")
        print(f"ROI percentage: {data['comparison']['roi_percentage']}%")
    
    def test_roi_calculator_custom_values(self, admin_token):
        """Test /api/calculator/roi with custom values"""
        response = requests.get(
            f"{BASE_URL}/api/calculator/roi",
            params={
                "monthly_leads": 200,
                "conversion_rate": 0.10,
                "avg_commission": 10000,
                "plan_cost": 299
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["monthly_leads"] == 200
        assert data["comparison"]["plan_cost"] == 299
        
        print(f"Custom ROI: {data['comparison']['roi_percentage']}% with 200 leads")
    
    def test_roi_calculator_requires_admin(self):
        """Test that ROI calculator requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/calculator/roi")
        assert response.status_code == 401 or response.status_code == 403
        print("ROI calculator correctly requires authentication")


class TestLeadsEndpoints:
    """Leads endpoint tests"""
    
    def test_get_all_leads(self):
        """Test /api/leads endpoint"""
        response = requests.get(f"{BASE_URL}/api/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Leads returned {len(data)} entries")
    
    def test_leads_by_intent(self):
        """Test /api/metrics/leads-by-intent endpoint"""
        response = requests.get(f"{BASE_URL}/api/metrics/leads-by-intent")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Leads by intent returned {len(data)} entries")


class TestLeadStatusUpdate:
    """Lead status update tests for Kanban drag & drop"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    def test_update_lead_status_endpoint_exists(self, admin_token):
        """Test /api/leads/{phone}/status endpoint exists"""
        # Test with a non-existent phone (should return 404, not 405)
        response = requests.put(
            f"{BASE_URL}/api/leads/test_phone_12345/status",
            params={"new_status": "hot"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should be 404 (not found) not 405 (method not allowed)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Status update endpoint exists (returns 404 for non-existent lead)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
