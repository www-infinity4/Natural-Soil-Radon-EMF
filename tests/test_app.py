"""
test_app.py
-----------
Tests for the Flask web application (app.py).
"""

import json
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Root route
# ---------------------------------------------------------------------------

class TestRootRoute:
    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_content_type_is_html(self, client):
        resp = client.get("/")
        assert "text/html" in resp.content_type

    def test_root_contains_site_title(self, client):
        resp = client.get("/")
        assert b"Natural Soil Radon EMF" in resp.data

    def test_root_contains_hero_text(self, client):
        resp = client.get("/")
        assert b"Signal Tractor" in resp.data

    def test_root_contains_run_button(self, client):
        resp = client.get("/")
        assert b"Run Tilling Session" in resp.data

    def test_root_contains_module_overview(self, client):
        resp = client.get("/")
        assert b"Radon Beacon" in resp.data
        assert b"Trepel Resonance" in resp.data
        assert b"Safety Override" in resp.data


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------

class TestStaticAssets:
    def test_stylesheet_served(self, client):
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert b"body" in resp.data


# ---------------------------------------------------------------------------
# /api/run — successful simulation
# ---------------------------------------------------------------------------

class TestApiRunSuccess:
    def _run(self, client, **kwargs):
        payload = {
            "anchor_depth_m": 1.5,
            "soil_column_m": 3.0,
            "radon_bq_m3": 80.0,
        }
        payload.update(kwargs)
        return client.post(
            "/api/run",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_returns_200(self, client):
        resp = self._run(client)
        assert resp.status_code == 200

    def test_response_is_json(self, client):
        resp = self._run(client)
        assert resp.content_type == "application/json"

    def test_succeeded_true(self, client):
        data = self._run(client).get_json()
        assert data["succeeded"] is True

    def test_levitation_achieved(self, client):
        data = self._run(client).get_json()
        assert data["levitation_achieved"] is True

    def test_selected_gas_present(self, client):
        data = self._run(client).get_json()
        assert "selected_gas" in data
        assert isinstance(data["selected_gas"], str)

    def test_phase_log_is_list(self, client):
        data = self._run(client).get_json()
        assert isinstance(data["phase_log"], list)
        assert len(data["phase_log"]) > 0

    def test_phase_log_ends_with_complete(self, client):
        data = self._run(client).get_json()
        assert data["phase_log"][-1] == "COMPLETE"

    def test_resonance_iterations_positive(self, client):
        data = self._run(client).get_json()
        assert data["resonance_iterations"] > 0

    def test_sync_state_present(self, client):
        data = self._run(client).get_json()
        assert data["sync_state"] is not None
        assert "is_synced" in data["sync_state"]
        assert "signal_strength" in data["sync_state"]

    def test_fault_reason_none_on_success(self, client):
        data = self._run(client).get_json()
        assert data["fault_reason"] is None

    def test_override_count_zero_by_default(self, client):
        data = self._run(client).get_json()
        assert data["override_count"] == 0

    def test_override_count_with_monitor_readings(self, client):
        resp = self._run(
            client,
            radon_monitor_readings=[50.0, 60.0, 45.0],
        )
        data = resp.get_json()
        assert data["succeeded"] is True
        assert "override_count" in data

    def test_default_params_succeed(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "succeeded" in data

    def test_empty_body_uses_defaults(self, client):
        resp = client.post("/api/run", data="", content_type="application/json")
        assert resp.status_code == 200

    def test_gas_fallback_to_methane(self, client):
        resp = self._run(client, radon_bq_m3=0.0, methane_ppm=500.0)
        data = resp.get_json()
        assert data["succeeded"] is True
        assert data["selected_gas"] in ("METHANE", "RADON")


# ---------------------------------------------------------------------------
# /api/run — invalid parameters
# ---------------------------------------------------------------------------

class TestApiRunInvalidParams:
    def test_bad_anchor_depth_returns_400(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({"anchor_depth_m": "not-a-number"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_bad_soil_column_returns_400(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({"soil_column_m": "bad"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_bad_radon_value_returns_400(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({"radon_bq_m3": "abc"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_error_key_present_on_400(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({"anchor_depth_m": "bad"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert "error" in data

    def test_bad_monitor_readings_returns_400(self, client):
        resp = client.post(
            "/api/run",
            data=json.dumps({"radon_monitor_readings": ["x", "y"]}),
            content_type="application/json",
        )
        assert resp.status_code == 400
