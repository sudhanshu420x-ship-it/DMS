# JETT — Disaster Management & Rescue Command Center

A Flask + SQLite command-center dashboard for disaster and rescue dispatch simulation, built with DSA concepts (Priority Queue and Dijkstra shortest-path).

---

## 🚀 Deploy to Vercel

This project is fully configured for deployment on [Vercel](https://vercel.com/) with zero extra configuration.

### Option 1: Deploy via GitHub (Recommended)
1. Push this repository to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. Go to [Vercel](https://vercel.com/) and log in.
3. Click **Add New... → Project** and select your GitHub repository.
4. Keep the default settings (Framework Preset: *Other*, Root Directory: `./`).
5. Click **Deploy**. Vercel will install dependencies from `requirements.txt` and host the application serverlessly.

### Option 2: Deploy via Vercel CLI
1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```
2. Run deployment from the project root:
   ```bash
   vercel
   ```
3. For production deployment:
   ```bash
   vercel --prod
   ```

> **Note regarding SQLite on Serverless:**  
> On serverless platforms like Vercel, the filesystem is stateless and read-only except `/tmp`. The application stores its SQLite database in `/tmp/jett.db`, automatically initialized with demo data on cold starts. For persistent multi-user production deployments, connect an external managed database (such as PostgreSQL on Neon or Supabase).

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
├── app.py                 # Core Flask application, routes & logic
├── requirements.txt       # Dependencies (Flask)
├── vercel.json            # Vercel routing and rewrite configuration
├── .vercelignore          # Files excluded from Vercel deployment bundle
└── .gitignore             # Files excluded from Git version control
```

---

## 🧠 DSA Concepts
- **Priority Queue / Heap:** Automatically orders incidents by severity (Critical → High → Medium → Low).
- **Graph & Dijkstra Algorithm:** Calculates shortest illustrative paths between emergency hubs and crisis locations.
- **Database Persistence:** Incident logs, statuses, and team states are managed via SQLite.

---

## ⚠️ Important Limitations
This is an educational simulation and demo dashboard, not a live emergency dispatch system. For real emergencies in India, call **112**.
