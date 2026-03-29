"""
app.py
------
Flask web application for the Natural Soil Radon EMF Signal Tractor System.

Serves the full website at the main root ("/") and exposes a REST API
endpoint that runs a complete tilling simulation and returns the results
as JSON.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, render_template, request

from src.gas_fallback import SoilGasReading
from src.soil_tiller import SoilTiller

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Main route — full website at root
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the full website landing page."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# REST API — run a tilling simulation
# ---------------------------------------------------------------------------

@app.route("/api/run", methods=["POST"])
def api_run():
    """
    Run a complete tilling simulation.

    Accepts JSON body with optional fields:
        anchor_depth_m         float  (default 1.5)
        soil_column_m          float  (default 3.0)
        radon_bq_m3            float  (default 40.0)
        methane_ppm            float  (default 0.0)
        co2_ppm                float  (default 0.0)
        helium_ppm             float  (default 0.0)
        radon_monitor_readings list[float]  (default [])
        soil_resistance        float  (default 1.0)
        max_resonance_iterations int  (default 40)

    Returns JSON with session results.
    """
    data = request.get_json(silent=True) or {}

    try:
        anchor_depth_m = float(data.get("anchor_depth_m", 1.5))
        soil_column_m = float(data.get("soil_column_m", 3.0))
        radon_bq_m3 = float(data.get("radon_bq_m3", 40.0))
        methane_ppm = float(data.get("methane_ppm", 0.0))
        co2_ppm = float(data.get("co2_ppm", 0.0))
        helium_ppm = float(data.get("helium_ppm", 0.0))
        radon_monitor_readings = [
            float(v) for v in data.get("radon_monitor_readings", [])
        ]
        soil_resistance = float(data.get("soil_resistance", 1.0))
        max_resonance_iterations = int(data.get("max_resonance_iterations", 40))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid parameter: {exc}"}), 400

    gas_reading = SoilGasReading(
        radon_bq_m3=radon_bq_m3,
        methane_ppm=methane_ppm,
        co2_ppm=co2_ppm,
        helium_ppm=helium_ppm,
    )

    tiller = SoilTiller(
        anchor_depth_m=anchor_depth_m,
        soil_column_m=soil_column_m,
        gas_reading=gas_reading,
        radon_monitor_readings=radon_monitor_readings,
        soil_resistance=soil_resistance,
        max_resonance_iterations=max_resonance_iterations,
    )

    session = tiller.run()

    return jsonify({
        "succeeded": session.succeeded,
        "selected_gas": session.selected_gas.name,
        "levitation_achieved": session.levitation_achieved,
        "fault_reason": session.fault_reason,
        "phase_log": [p.name for p in session.phase_log],
        "override_count": len(session.override_actions),
        "resonance_iterations": len(session.resonance_snapshots),
        "sync_state": {
            "is_synced": session.sync_state.is_synced,
            "signal_strength": session.sync_state.signal_strength,
        } if session.sync_state else None,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os as _os
    debug = _os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug)
