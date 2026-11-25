# JETT — Disaster Management & Rescue Command Center

A Flask + SQLite command-center dashboard for disaster and rescue dispatch simulation, featuring live GPS team tracking, real road navigation, keyword-based auto-detection, and DSA concepts (Priority Queue and Dijkstra shortest-path).

---

## ✨ Features

- **🛰 Real-time Team GPS Tracking:** Live team markers (`/api/teams`) auto-refresh every 5 seconds on the tactical map.
- **🗺 Live Shortest Road Navigation:** Uses **Mapbox Directions** (when a Mapbox key is configured) or **OSRM** to draw real road routes from Control Room to incidents with distance & ETA.
- **🔑 Map API Key Support:** Supports **Mapbox** (`dark-v11` / `satellite-streets-v12`) and **MapTiler** via `.env` / Vercel Environment Variables or the in-app **🔑 Map Key** button, with automatic fallback to free **CartoDB Dark** tiles.
- **🤖 Automatic Emergency Detection:** Real-time keyword classification (`/api/auto-detect`) auto-fills severity and category as you type an incident report.
- **📊 Incident Analytics & Priority Queue:** Heap-based severity sorting (`Critical → Low`) and interactive Chart.js status/severity breakdowns.

---

## 🔑 Map API Key Setup

The app works **out-of-the-box with zero API keys** (using free CartoDB Dark tiles and OSRM routing). To use **Mapbox** or **MapTiler**:

### Option A: Local `.env` file
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Add your public token in `.env`:
   ```env
   MAP_API_KEY=pk.your_mapbox_or_maptiler_key_here
   MAP_PROVIDER=auto
   ```
   *(Options for `MAP_PROVIDER`: `auto`, `mapbox`, `mapbox-satellite`, `maptiler`, `carto`)*

### Option B: Vercel Environment Variables
1. Open your Vercel project → **Settings → Environment Variables**.
2. Add `MAP_API_KEY` with your Mapbox (`pk....`) or MapTiler key.
3. Redeploy for the environment variable to take effect.

### Option C: In-App UI Switcher
Click **🔑 Map Key** directly inside the **Live Tactical Map** panel header to test or switch providers/keys immediately in the browser.

---

## 🚀 Deploy to Vercel

This project is configured for deployment on [Vercel](https://vercel.com/) with zero extra configuration.

### Option 1: Deploy via GitHub (Recommended)
1. Push this repository to GitHub.
2. Go to [Vercel](https://vercel.com/) and log in.
3. Click **Add New... → Project** and select your GitHub repository.
4. Keep the default settings (Framework Preset: *Other*, Root Directory: `./`).
5. *(Optional)* Add `MAP_API_KEY` under **Environment Variables**.
6. Click **Deploy**. Vercel will install dependencies from `requirements.txt` and host the application serverlessly.

### Option 2: Deploy via Vercel CLI
```bash
npm i -g vercel
vercel
vercel --prod
```

> **Note regarding SQLite on Serverless:**  
> On serverless platforms like Vercel, the filesystem is stateless and read-only except `/tmp`. The application stores its SQLite database in `/tmp/jett.db` (or the OS temp directory), automatically initialized with demo data on cold starts. For persistent multi-user production deployments, connect an external managed database (such as PostgreSQL on Neon or Supabase).

---

## 💻 Run Locally

### Windows
1. Ensure Python 3.10+ is installed.
2. Open terminal in the project directory:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
3. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

---

## 📂 Project Structure

```text
├── api/
│   └── index.py           # Vercel serverless function entrypoint
├── templates/
│   └── index.html         # Command center dashboard template
├── app.py                 # Core Flask application, routes, GPS & AI detect
├── requirements.txt       # Dependencies (Flask)
├── vercel.json            # Vercel routing and rewrite configuration
├── .env.example           # Environment variable template (MAP_API_KEY)
├── .vercelignore          # Files excluded from Vercel deployment bundle
└── .gitignore             # Files excluded from Git version control
```

---

## 🧠 DSA Concepts
- **Priority Queue / Heap:** Automatically orders incidents by severity (`Critical → High → Medium → Low`).
- **Graph & Dijkstra Algorithm:** Calculates shortest illustrative paths between emergency hubs and crisis locations.
- **Database Persistence:** Incident logs, statuses, and team states are managed via SQLite.

---

## ⚠️ Important Limitations
This is an educational simulation and demo dashboard, not a live emergency dispatch system. For real emergencies in India, call **112**.
