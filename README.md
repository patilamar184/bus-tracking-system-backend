# School Bus Tracking System – Backend

FastAPI backend for the IoT-Based School Bus Tracking and Management System.

This service receives GPS location and heartbeat data from ESP32 devices, manages buses, routes and stops, and provides APIs for the React admin dashboard and parent tracking page.

## Related Repositories

This backend works together with:

- [Frontend – React Dashboard](https://github.com/patilamar184/bus-tracking-system-frontend)
- [HTTP Relay – SIM800L Communication](https://github.com/patilamar184/bus-tracking-http-relay)

## Technology Stack

- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- Pydantic
- SQLite
- Uvicorn
- PyJWT
- bcrypt
- python-dotenv

## 1. Prerequisites

Install the following on your Windows machine:

- Git
- Python 3.10 or newer

Verify installation:

```bash
git --version
python --version
pip --version
```

## 2. Clone the Repository

```bash
git clone https://github.com/patilamar184/bus-tracking-system-backend.git

cd bus-tracking-system-backend
```

## 3. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it:

**Windows CMD:**

```cmd
.venv\Scripts\activate
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure Environment Variables

The repository contains an environment template named `_.env.example`.

Create your local `.env` file:

**Windows CMD:**

```cmd
copy _.env.example .env
```

**PowerShell:**

```powershell
Copy-Item _.env.example .env
```

Open `.env` and configure the values.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Secret used for signing JWT tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Admin login token expiration |
| `DATABASE_URL` | SQLite database connection |
| `ADMIN_USERNAME` | Initial administrator username |
| `ADMIN_PASSWORD` | Initial administrator password |
| `CORS_ORIGINS` | Allowed frontend origins, comma-separated |

Generate a secure secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated value into `SECRET_KEY`.

For local frontend development, ensure `CORS_ORIGINS` includes:

```env
CORS_ORIGINS=http://localhost:5173
```

Use your own strong administrator password.

**Important:** The initial admin account is created on first startup if it does not already exist. Changing `ADMIN_PASSWORD` later does not automatically change an existing administrator's password.

## 6. Start the Backend

Run from the repository root directory:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend address:

```text
http://localhost:8000
```

Swagger API documentation:

```text
http://localhost:8000/docs
```

Database tables are created automatically during application startup.

The SQLite database is stored according to the configured `DATABASE_URL`.

## 7. Configure Cloudflare Quick Tunnel

The Cloudflare tunnel exposes your local backend through a public HTTPS URL.

Install `cloudflared` for Windows:

https://developers.cloudflare.com/tunnel/downloads/

Verify installation:

```bash
cloudflared --version
```

Keep the backend running. Open a second terminal and execute:

```bash
cloudflared tunnel --url http://localhost:8000
```

Cloudflare will generate a URL similar to:

```text
https://example-name.trycloudflare.com
```

Copy the generated URL.

**Important:**
- Keep the Cloudflare terminal running.
- The Quick Tunnel URL may change when restarted.
- Update the relay and frontend configuration whenever the URL changes.

## 8. Test the Backend

Open:

```text
http://localhost:8000/docs
```

Recommended initial setup:

1. Use `POST /api/admin/login` to log in with your configured administrator credentials.
2. Authorize Swagger using the returned access token.
3. Create a route using `POST /api/admin/routes`.
4. Create a bus using `POST /api/admin/buses`.
5. Save the returned `device_api_key` securely. It is displayed only once.
6. Note the bus `device_id` and public tracking token.
7. Assign a route to the bus using the appropriate bus update endpoint.
8. Test the device heartbeat and location endpoints.

Device endpoints:

```text
POST /api/device/heartbeat
POST /api/device/location
```

Both device requests require the `X-API-Key` header.

Example heartbeat body:

```json
{
  "device_id": "BUS-2"
}
```

Example location body:

```json
{
  "device_id": "BUS-2",
  "latitude": 16.8524,
  "longitude": 74.5815,
  "speed_kmph": 25.4,
  "altitude_m": 560.2,
  "satellites": 8
}
```

Use the actual device ID and API key created for your bus.

## 9. Connect the Frontend

Repository:

https://github.com/patilamar184/bus-tracking-system-frontend

Configure its `.env` file:

```env
VITE_API_URL=https://YOUR-CLOUDFLARE-URL.trycloudflare.com
VITE_PUBLIC_URL=
```

For local development, the frontend is normally available at:

```text
http://localhost:5173
```

Ensure the backend's `CORS_ORIGINS` includes the frontend origin.

## 10. Connect the ESP32 Through HTTP Relay

Repository:

https://github.com/patilamar184/bus-tracking-http-relay

The SIM800L sends HTTP requests to the ngrok URL. The local HTTP relay forwards them to this backend through the Cloudflare HTTPS URL.

The communication path is:

```text
ESP32 + SIM800L
       |
       | HTTP
       v
ngrok Public URL
       |
       v
Local HTTP Relay :8080
       |
       | HTTPS
       v
Cloudflare Tunnel
       |
       v
FastAPI Backend :8000
       |
       v
SQLite Database
```

Follow the HTTP Relay repository README for complete setup.

## 11. Important Notes

- Keep the backend, Cloudflare tunnel and relay running.
- SQLite data is stored locally on the machine running the backend.
- Back up the SQLite database regularly.
- Never commit `.env` or expose secret keys.
- Changing the Cloudflare URL requires updating the relay and frontend environment configuration.
- The development Quick Tunnel URL is temporary and is not a permanent production deployment.

## Repository Links

- Backend: https://github.com/patilamar184/bus-tracking-system-backend
- Frontend: https://github.com/patilamar184/bus-tracking-system-frontend
- HTTP Relay: https://github.com/patilamar184/bus-tracking-http-relay
