"""
Test suite for InmoBot new features:
- Audit Log API
- Broadcast API
- Bulk Actions API
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@inmobot.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@inmobot.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"
        print("✅ Admin login successful")


class TestAuditLog:
    """Audit Log feature tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@inmobot.com",
            "password": "Admin123!"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_audit_log(self, auth_headers):
        """Test GET /api/audit-log returns list"""
        response = requests.get(f"{BASE_URL}/api/audit-log", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Audit log returned {len(data)} entries")
    
    def test_audit_log_requires_auth(self):
        """Test audit-log requires authentication"""
        response = requests.get(f"{BASE_URL}/api/audit-log")
        assert response.status_code == 401
        print("✅ Audit log correctly requires authentication")
    
    def test_audit_log_with_filter(self, auth_headers):
        """Test GET /api/audit-log with action filter"""
        response = requests.get(f"{BASE_URL}/api/audit-log?action=report_generated", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned entries should have the filtered action
        for entry in data:
            assert entry.get("action") == "report_generated"
        print(f"✅ Filtered audit log returned {len(data)} entries")
    
    def test_audit_log_entry_structure(self, auth_headers):
        """Test audit log entry has correct structure"""
        response = requests.get(f"{BASE_URL}/api/audit-log?limit=1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            entry = data[0]
            assert "action" in entry
            assert "user_email" in entry
            assert "timestamp" in entry
            print("✅ Audit log entry has correct structure")
        else:
            print("⚠️ No audit log entries to verify structure")


class TestBroadcast:
    """Broadcast feature tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@inmobot.com",
            "password": "Admin123!"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_broadcast_history(self, auth_headers):
        """Test GET /api/broadcast/history returns list"""
        response = requests.get(f"{BASE_URL}/api/broadcast/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Broadcast history returned {len(data)} entries")
    
    def test_broadcast_history_requires_auth(self):
        """Test broadcast history requires authentication"""
        response = requests.get(f"{BASE_URL}/api/broadcast/history")
        assert response.status_code == 401
        print("✅ Broadcast history correctly requires authentication")
    
    def test_send_broadcast(self, auth_headers):
        """Test POST /api/broadcast"""
        response = requests.post(f"{BASE_URL}/api/broadcast", 
            headers=auth_headers,
            json={
                "message": "Test broadcast message from automated tests",
                "filters": None,
                "scheduled_at": None
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "total_recipients" in data or "sent_count" in data
        print(f"✅ Broadcast sent: {data}")
    
    def test_broadcast_requires_auth(self):
        """Test broadcast requires authentication"""
        response = requests.post(f"{BASE_URL}/api/broadcast", json={
            "message": "Test message",
            "filters": None
        })
        assert response.status_code == 401
        print("✅ Broadcast correctly requires authentication")


class TestBulkActions:
    """Bulk Actions feature tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@inmobot.com",
            "password": "Admin123!"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_bulk_action_tag(self, auth_headers):
        """Test POST /api/leads/bulk-action with tag action"""
        response = requests.post(f"{BASE_URL}/api/leads/bulk-action",
            headers=auth_headers,
            json={
                "lead_phones": ["9999999999"],
                "action": "tag",
                "value": "test-automated-tag"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "updated_count" in data
        assert "total" in data
        print(f"✅ Bulk tag action: {data}")
    
    def test_bulk_action_status(self, auth_headers):
        """Test POST /api/leads/bulk-action with status action"""
        response = requests.post(f"{BASE_URL}/api/leads/bulk-action",
            headers=auth_headers,
            json={
                "lead_phones": ["9999999999"],
                "action": "status",
                "value": "warm"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "updated_count" in data
        print(f"✅ Bulk status action: {data}")
    
    def test_bulk_action_requires_auth(self):
        """Test bulk action requires authentication"""
        response = requests.post(f"{BASE_URL}/api/leads/bulk-action", json={
            "lead_phones": ["1234567890"],
            "action": "tag",
            "value": "test"
        })
        assert response.status_code == 401
        print("✅ Bulk action correctly requires authentication")
    
    def test_bulk_action_logs_audit(self, auth_headers):
        """Test that bulk action creates audit log entry"""
        # Execute a bulk action
        requests.post(f"{BASE_URL}/api/leads/bulk-action",
            headers=auth_headers,
            json={
                "lead_phones": ["8888888888"],
                "action": "tag",
                "value": "audit-test-tag"
            }
        )
        
        # Check audit log for the action
        response = requests.get(f"{BASE_URL}/api/audit-log?action=bulk_tag", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        print(f"✅ Bulk action created audit log entry")


class TestNavigation:
    """Test navigation links exist"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✅ API root working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
