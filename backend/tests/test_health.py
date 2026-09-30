import sys
import os
import unittest

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.api.v1.endpoints.health import health_check

class TestHealthEndpoint(unittest.TestCase):
    def test_app_initialization(self):
        """Verify the FastAPI application starts."""
        self.assertEqual(app.title, "ModelVerse API")

    def test_health_check_function(self):
        """Verify the health endpoint logic directly (without httpx TestClient)."""
        response = health_check()
        self.assertEqual(response["status"], "healthy")
        self.assertEqual(response["service"], "modelverse_api")

if __name__ == '__main__':
    unittest.main()
