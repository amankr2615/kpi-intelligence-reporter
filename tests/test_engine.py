import pytest
from fastapi.testclient import TestClient
from server import app
from forecaster import _linear_regression, run_regression_forecasting

client = TestClient(app)

def test_linear_regression():
    # Test a perfect positive slope y = x
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 5]
    slope, intercept, r_squared = _linear_regression(x, y)
    assert slope == 1.0
    assert intercept == 0.0
    assert r_squared == 1.0

    # Test flat line y = 5
    x2 = [1, 2, 3, 4, 5]
    y2 = [5, 5, 5, 5, 5]
    slope2, intercept2, r2 = _linear_regression(x2, y2)
    assert slope2 == 0.0
    assert intercept2 == 5.0
    # r_squared for flat line might be 0.0 depending on implementation
    assert r2 == 0.0

def test_auth_config_endpoint():
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "supabaseUrl" in data
    assert "supabaseKey" in data

def test_health_check_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
