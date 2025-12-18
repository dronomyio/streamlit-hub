Below is a **clean, production-grade `README.md`** you can drop at the root of your repo.
It’s written so that **future-you**, collaborators, or even recruiters can understand and operate this setup without context.

You can copy-paste this verbatim.

---

# Streamlit Hub on Morph.so

A Dockerized **multi-app Streamlit hub** running behind Caddy, designed for:

* zero-maintenance demos
* multiple Streamlit apps under one VM
* clean URLs (`/app/<name>/`)
* easy expansion (drop-in new apps)
* Morph **wake-on-HTTP** friendly

This setup is ideal for research demos, Medium posts, and interactive visualizations.

---

## Architecture Overview

```
Internet
  │
  ▼
Morph Public Endpoint (HTTP :80)
  │
  ▼
Caddy (reverse proxy)
  │
  ├── /app/demo2/      → streamlit-demo2 container (8501)
  ├── /app/uniswapv3/  → streamlit-uniswapv3 container (8501)
  └── /app/<new>/      → streamlit-<new> container (8501)
```

Each Streamlit app runs in its **own container**, sharing a common base image.

---

## Project Structure

```
streamlit-hub/
├── docker-compose.yml        # Orchestrates Caddy + all Streamlit apps
├── Caddyfile                 # URL routing (/app/<name>/)
│
├── base/                     # Shared base image for Streamlit apps
│   ├── Dockerfile
│   └── entrypoint.sh
│
├── apps/                     # DROP NEW STREAMLIT APPS HERE
│   ├── demo2/
│   │   ├── app.py
│   │   └── requirements.txt
│   │
│   ├── uniswapv3/
│   │   ├── app.py
│   │   └── requirements.txt
│   │
│   └── <new_app>/
│       ├── app.py
│       └── requirements.txt
│
└── README.md
```

---

## Requirements (on the VM)

* Linux VM (Morph instance)
* Docker
* Docker Compose v2+
* Port **80 exposed** in Morph UI (TCP 80 → 80)

---

## One-Time Setup (VM)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# logout + login OR: newgrp docker
```

---

## Starting the Application

From the project root:

```bash
docker compose up -d --build
```

Verify:

```bash
docker compose ps
```

Expected containers:

* `streamlit-hub-caddy`
* `streamlit-demo2`
* `streamlit-uniswapv3`

---

## Accessing the Apps

### Local (inside VM)

```bash
curl http://localhost/
curl http://localhost/app/demo2/
curl http://localhost/app/uniswapv3/
```

### Public (from browser)

⚠️ **Do NOT guess the hostname**

1. Open Morph UI → Instance → **NETWORK**
2. Copy the **public URL shown for port 80**
3. Use:

```
http://<PUBLIC_HOST>/
http://<PUBLIC_HOST>/app/demo2/
http://<PUBLIC_HOST>/app/uniswapv3/
```

✔ Always include the **trailing slash**.

---

## Adding a New Streamlit App (Drop-In Workflow)

### 1️⃣ Create the app folder

```bash
mkdir apps/mevshield
```

Add:

* `apps/mevshield/app.py`
* `apps/mevshield/requirements.txt` (must include `streamlit`)

---

### 2️⃣ Add a service to `docker-compose.yml`

```yaml
mevshield:
  build:
    context: ./base
  restart: unless-stopped
  environment:
    - APP_NAME=mevshield
    - APP_FILE=app.py
  volumes:
    - ./apps/mevshield:/app:ro
```

---

### 3️⃣ Add routing to `Caddyfile`

```caddyfile
handle_path /app/mevshield/* {
  reverse_proxy mevshield:8501
}
```

---

### 4️⃣ Rebuild

```bash
docker compose up -d --build mevshield
```

App is now live at:

```
/app/mevshield/
```

---

## Maintenance Commands

### Restart everything

```bash
docker compose restart
```

### Stop everything

```bash
docker compose down
```

### Rebuild a single app

```bash
docker compose up -d --build uniswapv3
```

---

## Troubleshooting

### ❌ Public URL does not resolve

**Cause:** Instance ID ≠ public hostname
**Fix:** Copy the exact URL shown in Morph UI → NETWORK

---

### ❌ App hangs / browser shows “not responding”

**Cause:** Missing trailing slash
**Fix:**

```
/app/demo2/   ✅
/app/demo2    ❌
```

---

### ❌ Container restarting with `Exit 127`

```bash
docker ps
```

You see:

```
Restarting (127)
```

**Cause:** `streamlit` missing in `requirements.txt`

**Fix:**

```txt
# requirements.txt
streamlit
plotly
numpy
matplotlib
```

Rebuild:

```bash
docker compose up -d --build <app>
```

---

### ❌ Works locally but not publicly

Checklist:

1. Port 80 exposed in Morph UI
2. Use HTTP (not HTTPS yet)
3. Correct public hostname
4. Trailing slash used

---

### 🔁 Caddy retry logic hides crashes (important)

Do **NOT** use `lb_try_duration` for Streamlit apps.

❌ Bad (masks failures):

```caddyfile
reverse_proxy app:8501 {
  lb_try_duration 30s
}
```

✅ Correct (fail fast):

```caddyfile
handle_path /app/appname/* {
  reverse_proxy appname:8501
}
```

---

## Logs (first place to look)

```bash
docker logs streamlit-demo2 --tail=200
docker logs streamlit-uniswapv3 --tail=200
docker logs streamlit-hub-caddy --tail=200
```

---

## Design Notes / Intentional Choices

* Each Streamlit app = isolated container
* Shared base image for consistency
* No load-balancer retries → fast failure
* Caddy used for clean paths + future HTTPS
* Designed for **wake-on-HTTP** Morph behavior

---

## Recommended Next Improvements (Optional)

* Add HTTPS via domain + Caddy
* Add basic auth
* Add landing page listing apps
* Add `/health` endpoint
* Add metrics/log aggregation

---

## TL;DR

* Start: `docker compose up -d --build`
* Add apps under `apps/`
* Route via `Caddyfile`
* Use Morph UI public URL
* Always use trailing slashes

---

If you want, I can also:

* generate a **one-command `add_app.sh`**
* create a **landing UI**
* add **auth**
* add **observability**
* harden this for production

Just say the word.

