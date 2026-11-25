from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime
import heapq
import os
import random
import tempfile

BASE = Path(__file__).resolve().parent


def _load_env_file(env_path: Path):
    """Load key=value pairs from a local .env file without extra dependencies."""
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_env_file(BASE / ".env")

if os.environ.get("VERCEL"):
    DB = Path(tempfile.gettempdir()) / "jett.db"
else:
    DB = BASE / "jett.db"

app = Flask(__name__, template_folder=str(BASE / "templates"))
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret-key")


def get_map_config():
    """Return map provider and client-side public tile API key from environment."""
    mapbox_key = (
        os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()
        or os.environ.get("MAPBOX_API_KEY", "").strip()
    )
    maptiler_key = os.environ.get("MAPTILER_API_KEY", "").strip()
    generic_key = os.environ.get("MAP_API_KEY", "").strip()
    api_key = generic_key or mapbox_key or maptiler_key

    provider = os.environ.get("MAP_PROVIDER", "auto").strip().lower()
    valid = {"mapbox", "mapbox-satellite", "maptiler", "carto"}
    if provider not in valid:
        if api_key and (mapbox_key or api_key.startswith("pk.")):
            provider = "mapbox"
        elif api_key:
            provider = "maptiler"
        else:
            provider = "carto"

    return {
        "provider": provider,
        "apiKey": api_key,
        "hasServerKey": bool(api_key),
    }


class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app
    def __call__(self, environ, start_response):
        matched_path = environ.get("HTTP_X_MATCHED_PATH")
        if matched_path:
            environ["PATH_INFO"] = matched_path.split("?")[0]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

TEAMS = [
    ("Rescue Team Alpha",    "Rescue",  "Available"),
    ("Medical Team Bravo",   "Medical", "Available"),
    ("Fire Response Charlie","Fire",    "Available"),
    ("Relief Team Delta",    "Relief",  "Available"),
]

# Base GPS coordinates per team (Mohali / Chandigarh region, India)
TEAM_BASE_LOCATIONS = {
    "Rescue Team Alpha":     (30.7046, 76.7179),
    "Medical Team Bravo":    (30.7533, 76.7994),
    "Fire Response Charlie": (30.6946, 76.7479),
    "Relief Team Delta":     (30.7233, 76.7594),
}
CTRL_LAT, CTRL_LON = 30.7400, 76.7800   # Control Room

# ── Auto-detect keyword tables ────────────────────────────────────────────────
SEVERITY_KEYWORDS = {
    "Critical": ["explosion", "collapse", "mass casualty", "critical",
                 "fatality", "dead", "tsunami", "nuclear", "major fire",
                 "building collapse", "multiple dead", "people trapped",
                 "trapped", "spreading"],
    "High":     ["fire", "flood", "earthquake", "storm", "trapped",
                 "injured", "urgent", "emergency", "gas leak", "drowning",
                 "rescue needed", "multiple injured"],
    "Medium":   ["waterlogging", "road block", "accident", "damage",
                 "fallen tree", "power outage", "disruption"],
    "Low":      ["minor", "small", "routine", "pothole", "noise", "low"],
}
KIND_KEYWORDS = {
    "Fire":            ["fire", "burning", "flames", "smoke", "blaze", "arson"],
    "Flood":           ["flood", "waterlogging", "water", "submerged",
                        "rain", "drowning", "overflow"],
    "Earthquake":      ["earthquake", "tremor", "seismic", "quake", "aftershock"],
    "Storm":           ["storm", "cyclone", "hurricane", "wind", "tornado"],
    "Road accident":   ["accident", "crash", "collision", "vehicle", "road",
                        "highway", "car"],
    "Building damage": ["building", "collapse", "structure", "wall", "roof", "ceiling"],
}
# ─────────────────────────────────────────────────────────────────────────────


def db():
    if not DB.exists():
        init_db()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS incidents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, kind TEXT NOT NULL, severity TEXT NOT NULL,
            location TEXT NOT NULL, description TEXT,
            latitude REAL, longitude REAL,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_team TEXT, created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS teams(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL, specialty TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )""")
        if con.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO teams(name,specialty,status) VALUES(?,?,?)", TEAMS)
        if con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0:
            demo = [
                ("Waterlogging near market", "Flood", "High",
                 "Mohali, Punjab",
                 "Road submerged, vehicles stuck. Emergency services required.",
                 30.7046, 76.7179, "Open", None,
                 datetime.now().isoformat(timespec="minutes")),
                ("Tree fallen after storm", "Storm", "Medium",
                 "Chandigarh, Punjab region",
                 "Blocking major road, power lines affected.",
                 30.7333, 76.7794, "Assigned", "Rescue Team Alpha",
                 datetime.now().isoformat(timespec="minutes")),
                ("Building fire — residential", "Fire", "Critical",
                 "Sector 22, Chandigarh",
                 "Multi-floor residential building on fire. People trapped reported.",
                 30.7236, 76.7738, "Open", None,
                 datetime.now().isoformat(timespec="minutes")),
            ]
            con.executemany("""
                INSERT INTO incidents
                  (title,kind,severity,location,description,
                   latitude,longitude,status,assigned_team,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", demo)


def priority_order(rows):
    """DSA: heap-based priority queue — Critical first."""
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    heap = []
    for row in rows:
        heapq.heappush(heap, (rank.get(row["severity"], 4), row["id"], dict(row)))
    ordered = []
    while heap:
        ordered.append(heapq.heappop(heap)[2])
    return ordered


def shortest_demo_path(start, goal):
    """DSA: Dijkstra on a small illustrative graph (not live road routing)."""
    graph = {
        "Control Room": {"Mohali": 8,  "Chandigarh": 12},
        "Mohali":        {"Control Room": 8,  "Kharar": 10, "Chandigarh": 7},
        "Chandigarh":    {"Control Room": 12, "Mohali": 7,  "Zirakpur": 9},
        "Kharar":        {"Mohali": 10},
        "Zirakpur":      {"Chandigarh": 9},
    }
    dist = {n: float("inf") for n in graph}
    prev = {}
    dist[start] = 0
    q = [(0, start)]
    while q:
        cost, node = heapq.heappop(q)
        if cost != dist[node]:
            continue
        if node == goal:
            break
        for nb, w in graph[node].items():
            nc = cost + w
            if nc < dist[nb]:
                dist[nb] = nc
                prev[nb] = node
                heapq.heappush(q, (nc, nb))
    if dist[goal] == float("inf"):
        return None, None
    path, n = [], goal
    while n != start:
        path.append(n)
        n = prev[n]
    path.append(start)
    return list(reversed(path)), dist[goal]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    with db() as con:
        incidents = con.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
        teams     = con.execute("SELECT * FROM teams ORDER BY id").fetchall()
    ordered = priority_order(incidents)
    stats = {
        "total":    len(incidents),
        "open":     sum(i["status"] == "Open"     for i in incidents),
        "assigned": sum(i["status"] == "Assigned" for i in incidents),
        "resolved": sum(i["status"] == "Resolved" for i in incidents),
        "critical": sum(i["severity"] == "Critical" for i in incidents),
        "available":sum(t["status"] == "Available" for t in teams),
    }
    return render_template(
        "index.html",
        incidents=ordered,
        teams=teams,
        stats=stats,
        map_config=get_map_config(),
    )


@app.route("/api/map-config")
def api_map_config():
    """Expose public map tile provider and client token configuration."""
    return jsonify(get_map_config())


@app.route("/incidents/new", methods=["POST"])
def new_incident():
    title       = request.form.get("title", "").strip()
    kind        = request.form.get("kind", "Other")
    severity    = request.form.get("severity", "Medium")
    location    = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    if not title or not location:
        flash("Please enter an incident title and location.", "error")
        return redirect(url_for("dashboard"))
    try:
        lat = float(request.form["latitude"])  if request.form.get("latitude")  else None
        lon = float(request.form["longitude"]) if request.form.get("longitude") else None
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except ValueError:
        flash("Coordinates are invalid. Leave blank or enter valid lat/lon.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        con.execute(
            """INSERT INTO incidents
               (title,kind,severity,location,description,latitude,longitude,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (title, kind, severity, location, description, lat, lon,
             datetime.now().strftime("%Y-%m-%d %H:%M")))
    flash(f"Incident '{title}' logged successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/incidents/<int:incident_id>/assign", methods=["POST"])
def assign(incident_id):
    team_id = request.form.get("team_id", type=int)
    with db() as con:
        team     = con.execute("SELECT * FROM teams WHERE id=? AND status='Available'",
                               (team_id,)).fetchone()
        incident = con.execute("SELECT * FROM incidents WHERE id=?",
                               (incident_id,)).fetchone()
        if not incident or not team:
            flash("Incident or available team not found.", "error")
        else:
            con.execute("UPDATE incidents SET status='Assigned', assigned_team=? WHERE id=?",
                        (team["name"], incident_id))
            con.execute("UPDATE teams SET status='On duty' WHERE id=?", (team_id,))
            flash(f"{team['name']} assigned to incident #{incident_id}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/incidents/<int:incident_id>/resolve", methods=["POST"])
def resolve(incident_id):
    with db() as con:
        incident = con.execute("SELECT * FROM incidents WHERE id=?",
                               (incident_id,)).fetchone()
        if incident:
            con.execute("UPDATE incidents SET status='Resolved' WHERE id=?", (incident_id,))
            if incident["assigned_team"]:
                con.execute("UPDATE teams SET status='Available' WHERE name=?",
                            (incident["assigned_team"],))
            flash(f"Incident #{incident_id} resolved. Team released.", "success")
    return redirect(url_for("dashboard"))


@app.route("/teams/<int:team_id>/release", methods=["POST"])
def release(team_id):
    with db() as con:
        con.execute("UPDATE teams SET status='Available' WHERE id=?", (team_id,))
    flash("Team marked available.", "success")
    return redirect(url_for("dashboard"))


@app.route("/api/incidents")
def api_incidents():
    with db() as con:
        rows = con.execute(
            "SELECT id,title,kind,severity,location,latitude,longitude,"
            "status,assigned_team FROM incidents").fetchall()
    return jsonify([dict(r) for r in rows
                    if r["latitude"] is not None and r["longitude"] is not None])


@app.route("/api/teams")
def api_teams():
    """Returns team data with simulated real-time GPS positions."""
    with db() as con:
        rows = con.execute("""
            SELECT t.id, t.name, t.specialty, t.status,
                   i.latitude  AS inc_lat,
                   i.longitude AS inc_lon
            FROM teams t
            LEFT JOIN incidents i
              ON i.assigned_team = t.name AND i.status = 'Assigned'
            ORDER BY t.id
        """).fetchall()
    result = []
    for t in rows:
        base = TEAM_BASE_LOCATIONS.get(t["name"], (CTRL_LAT, CTRL_LON))
        if t["status"] == "On duty" and t["inc_lat"]:
            # On-duty: appear near their assigned incident
            lat = t["inc_lat"] + random.uniform(-0.004, 0.004)
            lon = t["inc_lon"] + random.uniform(-0.004, 0.004)
        else:
            # Available: appear near their home base
            lat = base[0] + random.uniform(-0.006, 0.006)
            lon = base[1] + random.uniform(-0.006, 0.006)
        result.append({
            "id": t["id"], "name": t["name"],
            "specialty": t["specialty"], "status": t["status"],
            "lat": round(lat, 6), "lon": round(lon, 6),
        })
    return jsonify(result)


@app.route("/api/auto-detect", methods=["POST"])
def auto_detect():
    """Keyword-based automatic emergency classification."""
    data = request.get_json(force=True) or {}
    text = (data.get("title", "") + " " + data.get("description", "")).lower()
    severity, kind = "Medium", "Other"
    for sev, words in SEVERITY_KEYWORDS.items():
        if any(w in text for w in words):
            severity = sev
            break
    for k, words in KIND_KEYWORDS.items():
        if any(w in text for w in words):
            kind = k
            break
    return jsonify({"severity": severity, "kind": kind})


@app.route("/route-demo", methods=["POST"])
def route_demo():
    start = request.form.get("start", "Control Room")
    goal  = request.form.get("goal",  "Mohali")
    path, distance = shortest_demo_path(start, goal)
    if path is None:
        flash("No path found in the sample graph.", "error")
    else:
        flash(
            f"Dijkstra route: {' → '.join(path)} | {distance} km "
            "(illustrative — not for real navigation).",
            "success")
    return redirect(url_for("dashboard"))


@app.route("/reset-demo", methods=["POST"])
def reset_demo():
    with db() as con:
        con.execute("DELETE FROM incidents")
        con.execute("UPDATE teams SET status='Available'")
    flash("Demo data cleared and all teams released.", "success")
    return redirect(url_for("dashboard"))


# ── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    app.run(debug=True)
