# Safety-Aware Route Planner

A Flask web application that finds the safest walking route between two points using
OpenStreetMap data, community incident reports, and AI risk prediction.

---

## Features

| Feature | Detail |
|---|---|
| 🗺️ Safe routing | Dijkstra shortest-path weighted by pedestrian safety scores |
| 📊 Community reports | Incident reports decay edge safety within 300 m / 7 days |
| 🤖 AI risk prediction | Random Forest trained on synthetic + domain-knowledge data |
| 👥 Safety twins | Detects other active travellers on overlapping routes |
| 🆘 SOS alerts | One-tap emergency alert to configured guardian contacts |
| 🌡️ Heatmap | Leaflet.heat visualisation of all unresolved incidents |
| 🔒 Auth | Flask-Login with bcrypt password hashing |

---

## Quick Start (Development)

```bash
# 1. Clone & create virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set SECRET_KEY at minimum

# 4. Run
python app.py
```

The app starts at **http://localhost:5000**.

On first run it will:
1. Download the OSM walk graph for the configured `PLACE_NAME` (~30 s)
2. Compute initial edge safety scores and persist to SQLite
3. Train the ML risk model and save to `data/risk_model.joblib`

---

## Production Deployment

```bash
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Create tables
flask shell -c "from models import db; db.create_all()"

# Start with Gunicorn
gunicorn -c gunicorn.conf.py "app:app"
```

### Nginx reverse proxy (recommended)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
```

---

## Project Structure

```
safety_route_planner/
├── app.py              # Flask app, all routes, error handlers
├── config.py           # Dev/Prod config classes
├── models.py           # SQLAlchemy models (User, Guardian, IncidentReport, …)
├── safety_scoring.py   # OSM edge safety computation
├── routing.py          # Dijkstra safest-path algorithm
├── ml_model.py         # Random Forest risk prediction
├── utils.py            # Confidence scoring, safety twins, rate limiting
├── gunicorn.conf.py    # Production server config
├── requirements.txt
├── .env.example
├── data/               # Cached graph + trained model (auto-created)
├── instance/           # SQLite DB (auto-created)
├── logs/               # Rotating log files (auto-created)
├── templates/
│   ├── base.html
│   ├── index.html      login.html  register.html
│   ├── dashboard.html  plan_route.html
│   ├── heatmap.html    report.html  guardians.html
│   └── errors/         400.html  403.html  404.html  500.html
└── static/
    ├── css/style.css
    └── js/  main.js  route.js  heatmap.js  report.js
```

---

## Configuration

All settings can be set via environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | dev string | **Change in production** |
| `DATABASE_URL` | SQLite | PostgreSQL URL for production |
| `PLACE_NAME` | Connaught Place, New Delhi | OSM place for graph download |
| `FLASK_ENV` | development | `production` disables debug mode |
| `MAIL_SERVER` | smtp.gmail.com | SMTP server for SOS emails |
| `LOG_LEVEL` | INFO | Python logging level |

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/route` | ✅ | Find safest route (JSON) |
| POST | `/api/report` | ✅ | Submit incident report |
| GET  | `/api/heatmap_data` | — | All incident points for heatmap |
| POST | `/api/update_location` | ✅ | Update active traveller position |
| POST | `/api/sos` | ✅ | Send SOS to guardians |
| POST | `/api/predict_risk` | ✅ | ML risk score for given features |
| GET  | `/api/reports` | ✅ | Paginated report list |

---

## Known Limitations & Future Work

- **Email delivery**: SOS currently logs to console. Integrate Flask-Mail or SendGrid.
- **Graph area**: Changing `PLACE_NAME` requires deleting `data/graph.graphml` to re-download.
- **Safety data**: Scores improve with more community reports. Initial scores are OSM-only.
- **Real-time crowd data**: Currently simulated; could integrate Google Popular Times API.
- **CSRF protection**: Add `Flask-WTF` for full CSRF on all forms.
- **PostgreSQL**: Recommended over SQLite for concurrent users in production.
