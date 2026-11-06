# School Bus Tracking – FastAPI Backend

Real-time school bus tracking: ESP32 devices send GPS + heartbeat, an admin manages buses/routes/stops, and parents scan a QR code to track a bus without logging in.

**Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic, SQLite, Uvicorn.
Supporting libraries: `PyJWT` (admin tokens), `bcrypt` (password hashing), `python-dotenv` (.env).

## 1. Install

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example .env            # Windows: copy .env.example .env
```

Edit `.env`:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Signs JWTs. **Required, 32+ chars.** `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Admin token lifetime (default 60) |
| `DATABASE_URL` | Default `sqlite:///./school_bus.db` (created next to where you run the server) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Default admin, created on first start if it doesn't exist. Changing the password here later does **not** update an existing admin. |
| `CORS_ORIGINS` | Comma-separated frontend origins (default: Vite `5173` and `3000`) |

## 3. Run

Run from inside the `backend/` folder:

```bash
uvicorn app.main:app --reload
```

Tables are created automatically on startup. Swagger UI: <http://localhost:8000/docs>

## 4. Test with Swagger UI

1. **Login** – open `POST /api/admin/login` → *Try it out* → send `{"username": "admin", "password": "<your ADMIN_PASSWORD>"}`. Copy `access_token`.
2. **Authorize** – click the green **Authorize** button (top right), paste the token (just the token, no "Bearer"), confirm.
3. **Create a route** – `POST /api/admin/routes` with the example body from the spec (two stops).
4. **Create a bus** – `POST /api/admin/buses`. Copy `device_api_key` from the response now — **it is shown only once** (only its hash is stored). Also note `public_token`.
5. **Assign the route** – `PUT /api/admin/buses/{bus_id}` with `{"route_id": 1}`.
6. **Simulate the ESP32** – on `POST /api/device/heartbeat` and `POST /api/device/location`, fill the `X-API-Key` field with the device key and send the spec's request bodies (use your real device_id).
7. **Check** – `GET /api/admin/dashboard` (bus should be online for 60 s after each heartbeat), then `GET /api/admin/buses/{id}`.
8. **Parent view** (no auth) – `GET /api/parent/track/{public_token}`; use a stop `id` from the response in `GET /api/parent/track/{public_token}/eta/{stop_id}`.

Automated alternative: `pip install httpx && python smoke_test.py` runs every endpoint against a temporary database. Delete that file if you don't want it.

## 5. ESP32 usage

Send the device ID in the body and the key in the header:

```
POST /api/device/heartbeat      X-API-Key: <device_api_key>   {"device_id": "ESP32_001"}
POST /api/device/location       X-API-Key: <device_api_key>   {"device_id": "ESP32_001", "latitude": ..., ...}
```

Send a heartbeat at least every ~30 s; a device is **online** if its last heartbeat was within 60 s.

## 6. QR codes

The backend returns `public_tracking_url` (e.g. `/track/<token>`). The frontend builds the full URL (`https://yourwebsite.com/track/<token>`) and renders the QR. The React page then calls `/api/parent/track/<token>`.

## Behaviour notes

- **Errors:** 401 bad/missing credentials, 403 inactive device, 404 not found, 409 duplicate bus number/device ID, 422 validation (bad coordinates, duplicate `stop_order`, trying to change `device_id`).
- **Timestamps** are UTC, returned with a trailing `Z` (e.g. `2026-11-12T10:00:00Z`) so browsers don't misread them as local time.
- **ETA** = straight-line (haversine) distance ÷ current speed. `eta_minutes` is `null` with an explanatory `message` when there is no location, the bus is offline, or speed is 0.
- **Deleting a bus** also deletes its latest location and its device record (so the device ID can be reused). **Deleting a route** deletes its stops and sets assigned buses' `route_id` to null.
- **Updating a route's stops** replaces the whole list, so stop IDs change.
