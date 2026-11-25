from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime
import heapq
import os

import tempfile

BASE = Path(__file__).resolve().parent

# On Vercel / Serverless, the root directory is read-only. We store SQLite in the system temp directory (/tmp on Linux).
if os.environ.get("VERCEL"):
    DB = Path(tempfile.gettempdir()) / "jett.db"
else:
    DB = BASE / "jett.db"

app = Flask(__name__, template_folder=str(BASE / "templates"))
app.secret_key = os.environ.get("SECRET_KEY", "change-this-demo-secret-key")


class VercelPathFixMiddleware:
    """WSGI middleware ensuring PATH_INFO matches original request URL when rewritten by Vercel."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched_path = environ.get("HTTP_X_MATCHED_PATH")
        if matched_path:
            environ["PATH_INFO"] = matched_path.split("?")[0]
        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

TEAMS = [
    ("Rescue Team Alpha", "Rescue", "Available"),
    ("Medical Team Bravo", "Medical", "Available"),
    ("Fire Response Charlie", "Fire", "Available"),
    ("Relief Team Delta", "Relief", "Available"),
]

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
            location TEXT NOT NULL, description TEXT, latitude REAL, longitude REAL,
            status TEXT NOT NULL DEFAULT 'Open', assigned_team TEXT,
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS teams(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL, specialty TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available'
        )""")
        count = con.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        if count == 0:
            con.executemany("INSERT INTO teams(name,specialty,status) VALUES(?,?,?)", TEAMS)
        count = con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        if count == 0:
            demo = [
                ("Waterlogging near market", "Flood", "High", "Mohali, Punjab", "Demo incident for testing the dashboard.", 30.7046, 76.7179, "Open", None, datetime.now().isoformat(timespec="minutes")),
                ("Tree fallen after storm", "Storm", "Medium", "Chandigarh, Punjab region", "Demo incident. Verify details before taking action.", 30.7333, 76.7794, "Assigned", "Rescue Team Alpha", datetime.now().isoformat(timespec="minutes")),
            ]
            con.executemany("""INSERT INTO incidents(title,kind,severity,location,description,latitude,longitude,status,assigned_team,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", demo)

def priority_order(rows):
    # DSA: heap-based priority queue. Critical incidents are shown first.
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    heap = []
    for row in rows:
        heapq.heappush(heap, (rank.get(row["severity"], 4), row["id"], dict(row)))
    ordered = []
    while heap:
        ordered.append(heapq.heappop(heap)[2])
    return ordered

def shortest_demo_path(start, goal):
    # DSA: Dijkstra on a tiny illustrative graph, not a live road-routing service.
    graph = {
        "Control Room": {"Mohali": 8, "Chandigarh": 12},
        "Mohali": {"Control Room": 8, "Kharar": 10, "Chandigarh": 7},
        "Chandigarh": {"Control Room": 12, "Mohali": 7, "Zirakpur": 9},
        "Kharar": {"Mohali": 10},
        "Zirakpur": {"Chandigarh": 9},
    }
    distances = {node: float("inf") for node in graph}
    previous = {}
    distances[start] = 0
    queue = [(0, start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distances[node]:
            continue
        if node == goal:
            break
        for neighbour, weight in graph[node].items():
            new_cost = cost + weight
            if new_cost < distances[neighbour]:
                distances[neighbour] = new_cost
                previous[neighbour] = node
                heapq.heappush(queue, (new_cost, neighbour))
    if distances[goal] == float("inf"):
        return None, None
    path, node = [], goal
    while node != start:
        path.append(node)
        node = previous[node]
    path.append(start)
    return list(reversed(path)), distances[goal]

@app.route("/")
def dashboard():
    with db() as con:
        incidents = con.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
        teams = con.execute("SELECT * FROM teams ORDER BY id").fetchall()
    ordered = priority_order(incidents)
    stats = {
        "total": len(incidents),
        "open": sum(i["status"] == "Open" for i in incidents),
        "assigned": sum(i["status"] == "Assigned" for i in incidents),
        "resolved": sum(i["status"] == "Resolved" for i in incidents),
        "critical": sum(i["severity"] == "Critical" for i in incidents),
        "available": sum(t["status"] == "Available" for t in teams),
    }
    return render_template("index.html", incidents=ordered, teams=teams, stats=stats)

@app.route("/incidents/new", methods=["POST"])
def new_incident():
    title = request.form.get("title", "").strip()
    kind = request.form.get("kind", "Other")
    severity = request.form.get("severity", "Medium")
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    if not title or not location:
        flash("Please enter an incident title and location.", "error")
        return redirect(url_for("dashboard"))
    try:
        lat = float(request.form["latitude"]) if request.form.get("latitude") else None
        lon = float(request.form["longitude"]) if request.form.get("longitude") else None
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except ValueError:
        flash("Coordinates are invalid. Leave them blank or enter valid latitude/longitude.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        con.execute("""INSERT INTO incidents(title,kind,severity,location,description,latitude,longitude,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (title, kind, severity, location, description, lat, lon, datetime.now().strftime("%Y-%m-%d %H:%M")))
    flash("Incident report saved.", "success")
    return redirect(url_for("dashboard"))

@app.route("/incidents/<int:incident_id>/assign", methods=["POST"])
def assign(incident_id):
    team_id = request.form.get("team_id", type=int)
    with db() as con:
        team = con.execute("SELECT * FROM teams WHERE id=? AND status='Available'", (team_id,)).fetchone()
        incident = con.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if not incident or not team:
            flash("That incident or available team could not be found.", "error")
        else:
            con.execute("UPDATE incidents SET status='Assigned', assigned_team=? WHERE id=?", (team["name"], incident_id))
            con.execute("UPDATE teams SET status='On duty' WHERE id=?", (team_id,))
            flash(f"{team['name']} assigned to incident #{incident_id}.", "success")
    return redirect(url_for("dashboard"))

@app.route("/incidents/<int:incident_id>/resolve", methods=["POST"])
def resolve(incident_id):
    with db() as con:
        incident = con.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if incident:
            con.execute("UPDATE incidents SET status='Resolved' WHERE id=?", (incident_id,))
            if incident["assigned_team"]:
                con.execute("UPDATE teams SET status='Available' WHERE name=?", (incident["assigned_team"],))
            flash(f"Incident #{incident_id} marked resolved.", "success")
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
        rows = con.execute("SELECT id,title,kind,severity,location,latitude,longitude,status,assigned_team FROM incidents").fetchall()
    return jsonify([dict(r) for r in rows if r["latitude"] is not None and r["longitude"] is not None])

@app.route("/route-demo", methods=["POST"])
def route_demo():
    start = request.form.get("start", "Control Room")
    goal = request.form.get("goal", "Mohali")
    path, distance = shortest_demo_path(start, goal)
    if path is None:
        flash("No path found in the sample graph.", "error")
    else:
        flash(f"Sample Dijkstra route: {' → '.join(path)} ({distance} km in illustrative data). Not for real emergency navigation.", "success")
    return redirect(url_for("dashboard"))

@app.route("/reset-demo", methods=["POST"])
def reset_demo():
    with db() as con:
        con.execute("DELETE FROM incidents")
        con.execute("UPDATE teams SET status='Available'")
    flash("Incident list cleared and all teams released. The sample incidents will not be re-added automatically.", "success")
    return redirect(url_for("dashboard"))

# Auto-initialize database on startup so cold containers are seeded immediately
init_db()

if __name__ == "__main__":
    app.run(debug=True)
