"""
End-to-end smoke test for every endpoint. Optional: delete this file if you don't need it.

    pip install httpx
    python smoke_test.py

Uses a temporary SQLite file and temporary settings; your real database and .env are not touched.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-1234"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BusLocation, Device  # noqa: E402

passed = 0


def check(label, condition):
    global passed
    assert condition, f"FAILED: {label}"
    passed += 1
    print(f"  ok  {label}")


with TestClient(app) as c:
    # ---- Admin auth ----
    check("login with wrong password -> 401",
          c.post("/api/admin/login", json={"username": "admin", "password": "nope"}).status_code == 401)
    r = c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    check("login ok -> 200 + bearer token", r.status_code == 200 and r.json()["token_type"] == "bearer")
    H = {"Authorization": f"Bearer {r.json()['access_token']}"}
    for path in ["/api/admin/dashboard", "/api/admin/buses", "/api/admin/routes"]:
        check(f"GET {path} without token -> 401", c.get(path).status_code == 401)
    check("garbage token -> 401",
          c.get("/api/admin/buses", headers={"Authorization": "Bearer abc"}).status_code == 401)

    d = c.get("/api/admin/dashboard", headers=H).json()
    check("dashboard empty", d == {"total_buses": 0, "online_buses": 0, "offline_buses": 0, "total_routes": 0})

    # ---- Routes ----
    stops = [
        {"stop_name": "Station A", "latitude": 18.5204, "longitude": 73.8567, "stop_order": 1},
        {"stop_name": "Station B", "latitude": 18.5304, "longitude": 73.8667, "stop_order": 2},
    ]
    check("route with duplicate stop_order -> 422",
          c.post("/api/admin/routes", headers=H, json={"route_name": "X", "stops": [stops[0], stops[0]]}).status_code == 422)
    check("route with bad latitude -> 422",
          c.post("/api/admin/routes", headers=H,
                 json={"route_name": "X", "stops": [{**stops[0], "latitude": 123}]}).status_code == 422)
    r = c.post("/api/admin/routes", headers=H,
               json={"route_name": "Pune Route 01", "description": "Main school route", "stops": stops})
    check("create route -> 201 with 2 stops", r.status_code == 201 and len(r.json()["stops"]) == 2)
    route_id = r.json()["id"]

    # ---- Buses ----
    bus_body = {"bus_number": "MH12AB1234", "bus_name": "School Bus 01", "device_id": "ESP32_001"}
    r = c.post("/api/admin/buses", headers=H, json=bus_body)
    check("create bus -> 201", r.status_code == 201)
    bus = r.json()
    bus_id, token, api_key = bus["id"], bus["public_token"], bus["device_api_key"]
    check("public url is /track/<token>", bus["public_tracking_url"] == f"/track/{token}")
    check("duplicate bus_number -> 409", c.post("/api/admin/buses", headers=H, json={**bus_body, "device_id": "ESP32_002"}).status_code == 409)
    check("duplicate device_id -> 409", c.post("/api/admin/buses", headers=H, json={**bus_body, "bus_number": "OTHER"}).status_code == 409)

    r = c.get("/api/admin/buses", headers=H)
    check("list buses: 1 bus, offline, no secrets",
          len(r.json()) == 1 and r.json()[0]["device_status"] == "offline"
          and "api_key" not in r.text and "hashed" not in r.text)

    check("PUT bus with device_id -> 422",
          c.put(f"/api/admin/buses/{bus_id}", headers=H, json={"device_id": "HACK"}).status_code == 422)
    check("PUT bus with unknown route -> 404",
          c.put(f"/api/admin/buses/{bus_id}", headers=H, json={"route_id": 999}).status_code == 404)
    r = c.put(f"/api/admin/buses/{bus_id}", headers=H, json={"bus_name": "School Bus 02", "route_id": route_id})
    check("PUT bus name + route", r.status_code == 200 and r.json()["bus_name"] == "School Bus 02"
          and r.json()["route"]["id"] == route_id and r.json()["device_id"] == "ESP32_001")
    check("GET bus detail (no location yet)",
          c.get(f"/api/admin/buses/{bus_id}", headers=H).json()["location"] is None)
    check("GET unknown bus -> 404", c.get("/api/admin/buses/999", headers=H).status_code == 404)
    check("route list shows bus_count 1", c.get("/api/admin/routes", headers=H).json()[0]["bus_count"] == 1)

    # ---- Device API ----
    hb = {"device_id": "ESP32_001"}
    check("heartbeat without key -> 401", c.post("/api/device/heartbeat", json=hb).status_code == 401)
    check("heartbeat wrong key -> 401",
          c.post("/api/device/heartbeat", json=hb, headers={"X-API-Key": "wrong"}).status_code == 401)
    r = c.post("/api/device/heartbeat", json=hb, headers={"X-API-Key": api_key})
    check("heartbeat ok", r.status_code == 200 and r.json() == {"message": "Heartbeat received", "device_status": "online"})
    d = c.get("/api/admin/dashboard", headers=H).json()
    check("dashboard: 1 online, 0 offline", d["online_buses"] == 1 and d["offline_buses"] == 0 and d["total_routes"] == 1)

    KEY = {"X-API-Key": api_key}
    loc = {"device_id": "ESP32_001", "latitude": 18.5204, "longitude": 73.8567,
           "speed_kmph": 35.5, "altitude_m": 560, "satellites": 8}
    check("location latitude 95 -> 422", c.post("/api/device/location", json={**loc, "latitude": 95}, headers=KEY).status_code == 422)
    check("location longitude 200 -> 422", c.post("/api/device/location", json={**loc, "longitude": 200}, headers=KEY).status_code == 422)
    check("location wrong key -> 401", c.post("/api/device/location", json=loc, headers={"X-API-Key": "x"}).status_code == 401)
    r = c.post("/api/device/location", json=loc, headers=KEY)
    check("location ok", r.status_code == 200 and r.json() == {"message": "Location updated successfully"})
    c.post("/api/device/location", json={**loc, "latitude": 18.5210}, headers=KEY)
    with SessionLocal() as db:
        check("location updated in place (1 row)", db.scalar(select(func.count(BusLocation.id))) == 1)
    check("latest location stored",
          c.get(f"/api/admin/buses/{bus_id}", headers=H).json()["location"]["latitude"] == 18.5210)

    # ---- Parent API ----
    check("track with bad token -> 404", c.get("/api/parent/track/nope").status_code == 404)
    r = c.get(f"/api/parent/track/{token}")
    t = r.json()
    check("track ok", r.status_code == 200 and t["bus_number"] == "MH12AB1234"
          and t["device_status"] == "online" and t["location"]["speed_kmph"] == 35.5
          and len(t["route"]["stops"]) == 2 and "id" in t["route"]["stops"][0])
    check("track hides token/device info", "public_token" not in r.text and "device_id" not in r.text)
    stop_b = t["route"]["stops"][1]["id"]
    r = c.get(f"/api/parent/track/{token}/eta/{stop_b}")
    e = r.json()
    check("ETA ok", r.status_code == 200 and e["stop_name"] == "Station B"
          and isinstance(e["eta_minutes"], int) and e["distance_km"] > 0)
    check("ETA unknown stop -> 404", c.get(f"/api/parent/track/{token}/eta/9999").status_code == 404)
    c.post("/api/device/location", json={**loc, "speed_kmph": 0}, headers=KEY)
    e = c.get(f"/api/parent/track/{token}/eta/{stop_b}").json()
    check("ETA unavailable when speed is 0", e["eta_minutes"] is None and "unavailable" in e["message"])

    # ---- Route update / delete ----
    r = c.put(f"/api/admin/routes/{route_id}", headers=H,
              json={"route_name": "Renamed", "stops": [stops[1]]})
    check("PUT route replaces stops", r.status_code == 200 and r.json()["route_name"] == "Renamed"
          and len(r.json()["stops"]) == 1 and r.json()["description"] == "Main school route")
    check("DELETE route -> 204", c.delete(f"/api/admin/routes/{route_id}", headers=H).status_code == 204)
    check("bus kept, route_id now null",
          c.get(f"/api/admin/buses/{bus_id}", headers=H).json()["route"] is None)

    # ---- Inactive device ----
    with SessionLocal() as db:
        dev = db.scalar(select(Device).where(Device.device_id == "ESP32_001"))
        dev.is_active = False
        db.commit()
    check("inactive device heartbeat -> 403", c.post("/api/device/heartbeat", json=hb, headers=KEY).status_code == 403)
    check("inactive device location -> 403", c.post("/api/device/location", json=loc, headers=KEY).status_code == 403)

    # ---- Delete bus ----
    check("DELETE bus -> 204", c.delete(f"/api/admin/buses/{bus_id}", headers=H).status_code == 204)
    check("deleted bus -> 404", c.get(f"/api/admin/buses/{bus_id}", headers=H).status_code == 404)
    with SessionLocal() as db:
        check("location + device removed with bus",
              db.scalar(select(func.count(BusLocation.id))) == 0 and db.scalar(select(func.count(Device.id))) == 0)
    check("device_id reusable after delete", c.post("/api/admin/buses", headers=H, json=bus_body).status_code == 201)

print(f"\nAll {passed} checks passed.")
