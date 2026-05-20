import pytest
from fastapi.testclient import TestClient
from server import app
from forecaster import run_least_squares, run_regression_forecasting

client = TestClient(app)

# -------------------------------------------------------------------
# Forecaster Math Engine Tests
# -------------------------------------------------------------------

def test_perfect_positive_slope():
    """y = x should yield slope=1.0, intercept=0.0, r_squared=1.0"""
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 5]
    result = run_least_squares(x, y)
    assert result["slope"] == pytest.approx(1.0)
    assert result["intercept"] == pytest.approx(0.0)
    assert result["r_squared"] == pytest.approx(1.0)

def test_flat_line():
    """y = 5 (constant) should yield slope=0.0, intercept=5.0"""
    x = [1, 2, 3, 4, 5]
    y = [5, 5, 5, 5, 5]
    result = run_least_squares(x, y)
    assert result["slope"] == pytest.approx(0.0)
    assert result["intercept"] == pytest.approx(5.0)
    # r_squared for constant y: ss_tot is 0, so the function returns 1.0
    assert result["r_squared"] == pytest.approx(1.0)

def test_negative_slope():
    """Verify negative slopes are correctly calculated."""
    x = [1, 2, 3, 4, 5]
    y = [10, 8, 6, 4, 2]
    result = run_least_squares(x, y)
    assert result["slope"] == pytest.approx(-2.0)

def test_single_datapoint():
    """Edge case: a single data point should return gracefully."""
    result = run_least_squares([1], [42])
    assert result["slope"] == 0.0
    assert result["intercept"] == 42.0

def test_regression_forecasting_returns_structure():
    """Verify run_regression_forecasting returns the expected dict keys."""
    m_data = [
        {"spend": 100, "revenue": 300},
        {"spend": 120, "revenue": 350},
        {"spend": 140, "revenue": 400},
    ]
    p_data = [
        {"revenue": 1000},
        {"revenue": 1100},
        {"revenue": 1200},
    ]
    result = run_regression_forecasting(m_data, p_data)
    assert result["status"] == "success"
    assert "marketing_metrics" in result
    assert "product_metrics" in result
    assert "projected_30d_spend" in result["marketing_metrics"]
    assert "projected_30d_revenue" in result["product_metrics"]

def test_regression_forecasting_empty_data():
    """Gracefully handle empty input."""
    result = run_regression_forecasting([], [])
    assert result["status"] in ("success", "fallback")

# -------------------------------------------------------------------
# FastAPI Endpoint Tests
# -------------------------------------------------------------------

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_auth_config_endpoint():
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "supabaseUrl" in data
    assert "supabaseKey" in data

def test_styles_css_endpoint():
    response = client.get("/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]

def test_script_js_endpoint():
    response = client.get("/script.js")
    assert response.status_code == 200
