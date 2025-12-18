# Streamlit Hub on Morph — Troubleshooting & Operations

This README captures the issues we hit, what they mean, and the exact fixes.

---

## Start / Deploy the application

### 1) SSH into the VM
Use the Morph UI “SSH” button for instance `morphvm_54lyty6g` (or the SSH command Morph provides).

### 2) From your project directory, start the stack
```bash
cd ~/strealitapps/streamlit-hub   # (use your actual path)
docker compose up -d --build
docker compose ps
```

### 3) Verify locally on the VM
```bash
curl -v http://localhost/
curl -v http://localhost/app/demo2/
curl -v http://localhost/app/uniswapv3/
```

### 4) Access from anywhere (public)
Use the **public URL shown in the Morph UI** under **NETWORK → Exposed services** (details below).
Then visit:
- `http://<PUBLIC_HOST>/`  
- `http://<PUBLIC_HOST>/app/demo2/`
- `http://<PUBLIC_HOST>/app/uniswapv3/`

> Important: keep the trailing slash on app paths.

---

## Morph networking: “What is the public IP?”

### Problem
You tried:
```bash
curl http://morphvm_54lyty6g.morph.so/app/demo2/
```
and got:
```
curl: (6) Could not resolve host: morphvm_54lyty6g.morph.so
```

### Root cause
`morphvm_54lyty6g` (the instance ID) is **NOT** automatically a DNS hostname.
Morph creates a **public hostname per exposed service**, and it is **shown in the UI**.

### Fix
1. In Morph UI for your instance, go to **NETWORK**.
2. **Expose a service** (if not already):
   - Protocol: TCP
   - External Port: `80`
   - Internal Port: `80`
   - Enable **Wake on HTTP** (recommended)
3. Copy the exact **URL/hostname** shown for that exposed service.
4. Use that hostname in your browser/curl:
```bash
curl http://<HOST_FROM_UI>/app/demo2/
```

---

## URL issues: trailing slash is required

### Problem
`/app/demo2` may not respond or may redirect weirdly.

### Root cause
Streamlit running under a `baseUrlPath` expects URLs like:
- `/app/demo2/` ✅
- `/app/demo2` ❌ (often fails or behaves inconsistently)

### Fix
Always use a trailing slash:
- `http://<PUBLIC_HOST>/app/demo2/`
- `http://<PUBLIC_HOST>/app/uniswapv3/`

---

## HTTP vs HTTPS

### Problem
You used `https://...` and saw “not responding”.

### Root cause
Unless you’ve configured TLS (domain + reverse proxy TLS) the public endpoint may be HTTP-only.

### Fix
Start with HTTP:
- `http://<PUBLIC_HOST>/app/demo2/`

Later, enable HTTPS via Caddy + a real domain (recommended), then switch to `https://yourdomain/...`.

---

## Caddy is up, but an app path fails

### How to check
On the VM:
```bash
docker ps
curl -v http://localhost/
curl -v http://localhost/app/demo2/
```

If `localhost` works but public does not → Morph service exposure / hostname is wrong.
If `localhost` fails → routing/container issue.

---

## Container restarting with exit code 127 (command not found)

### Symptom
`docker ps` shows:
```
streamlit-uniswapv3   Restarting (127) ...
```

### Root cause
Exit code 127 usually means:
- `streamlit` command not found (Streamlit not installed)
- entrypoint not executable (rare if demo2 works)
- missing/invalid app files that prevent startup

### Fix: check logs, then fix requirements
1. Inspect logs:
```bash
docker logs streamlit-uniswapv3 --tail=200
```

2. The common fix is ensuring the app has Streamlit in its requirements:
`apps/uniswapv3/requirements.txt` must include:
```txt
streamlit
plotly
numpy
matplotlib
```

3. Rebuild only that service:
```bash
docker compose up -d --build uniswapv3
```

4. Verify it’s stable:
```bash
docker ps
docker logs streamlit-uniswapv3 --tail=50
curl -v http://localhost/app/uniswapv3/
```

---

## “No services exposed” in Morph UI

### Problem
Morph UI shows:
> NETWORK → No services exposed

### Root cause
Even if Docker/Caddy is running, **nothing is reachable from outside** until you expose a service/port.

### Fix
Expose port 80 in Morph UI:
- TCP 80 → 80
- Enable Wake on HTTP (recommended)

Then use the generated public hostname shown in the UI.

---

## Caddy routing / baseUrlPath mismatch

### Symptom
App loads partially, but assets fail (JS/CSS), or you see blank pages.

### Root cause
When hosting Streamlit under a subpath like `/app/demo2/`, you must:
1) run Streamlit with `--server.baseUrlPath=app/demo2`
2) use `handle_path` in Caddy to strip the prefix before proxying

### Expected configuration

**entrypoint.sh** should run:
```bash
streamlit run /app/app.py --server.baseUrlPath="app/${APP_NAME}"
```

**Caddyfile** should use:
```caddyfile
handle_path /app/demo2/* {
  reverse_proxy demo2:8501
}
```

After changing Caddyfile:
```bash
docker compose restart caddy
```

---

## Caddy depends_on causing confusion (optional improvement)

### Symptom
Caddy waits for apps; one crashing app can delay startup or confuse readiness.

### Fix
Remove `depends_on` from the Caddy service in `docker-compose.yml`.
Caddy can start independently; routes will work once apps are healthy.

---

## Quick health checklist (copy/paste)

### 1) Containers
```bash
docker ps
```
You want:
- caddy: Up
- demo2: Up
- uniswapv3: Up (not restarting)

### 2) Local routes (on VM)
```bash
curl -I http://localhost/
curl -I http://localhost/app/demo2/
curl -I http://localhost/app/uniswapv3/
```

### 3) Public route (from your laptop)
Use the **public host from Morph UI**:
```bash
curl -I http://<PUBLIC_HOST>/
curl -I http://<PUBLIC_HOST>/app/demo2/
```

---

## Stop / restart

### Stop
```bash
docker compose down
```

### Restart everything
```bash
docker compose restart
```

### Rebuild one app after changes
```bash
docker compose up -d --build demo2
# or
docker compose up -d --build uniswapv3
```

---

## Where to look when something breaks

1) **App logs**
```bash
docker logs streamlit-demo2 --tail=200
docker logs streamlit-uniswapv3 --tail=200
```

2) **Caddy logs**
```bash
docker logs streamlit-hub-caddy --tail=200
```

3) **Local curl**
```bash
curl -v http://localhost/app/demo2/
```

4) **Public hostname correctness**
Confirm the hostname is copied from Morph UI “NETWORK → exposed service”.

Good catch — you’re right, and this is an **important clarification**.
Let me explain **what that block actually does**, **why it is NOT related to pip**, and then give you a **clean, corrected README section** you can paste in.

---

## Key clarification (very important)

```caddyfile
handle /app/uniswapv3/* {
  reverse_proxy streamlit-uniswapv3:8501 {
    lb_try_duration 30s
    lb_try_interval 500ms
  }
}
```

### ❌ What this is **NOT**

* ❌ Not related to `pip`
* ❌ Not related to Python dependencies
* ❌ Not related to `requirements.txt`
* ❌ Not related to Streamlit installation

### ✅ What this **IS**

This is **Caddy load-balancer retry logic**.

It tells Caddy:

> “If the backend container is temporarily unavailable (e.g. restarting), keep retrying for up to 30 seconds, checking every 500ms, before returning an error to the client.”

---

## Why this matters in *your* setup

You had this state:

```
streamlit-uniswapv3   Restarting (127)
```

So what happened was:

1. Browser hits `/app/uniswapv3/`
2. Caddy forwards to `streamlit-uniswapv3:8501`
3. Container is **crashing**
4. Caddy retries for 30s (`lb_try_duration`)
5. Browser appears to “hang” / “not responding”

This made it *look* like:

* a networking issue
* or a pip install issue

But in reality:

* **the retry logic was masking a crashing container**

---

## Why demo2 appeared to work but uniswapv3 didn’t

* `demo2` container was healthy → Caddy routed instantly
* `uniswapv3` container was restarting → Caddy kept retrying silently

This is expected behavior with `lb_try_duration`.

---

## Recommended practice for Streamlit (important)

For **single-backend Streamlit apps**, you should:

### ✅ REMOVE load-balancer retry settings

They are useful only when:

* you have **multiple replicas**
* you expect **temporary backend churn**

For Streamlit demos:

* they **hide errors**
* make debugging harder

---

## Correct Caddy config (recommended)

### Use `handle_path` and **no lb retry**

```caddyfile
handle_path /app/uniswapv3/* {
  reverse_proxy streamlit-uniswapv3:8501
}
```

and

```caddyfile
handle_path /app/demo2/* {
  reverse_proxy streamlit-demo2:8501
}
```

This way:

* if Streamlit is down → you immediately see an error
* no silent hangs
* debugging is obvious

---

## When `lb_try_duration` *is* appropriate

Keep it **only if**:

* you run **multiple replicas**
* or you expect **cold starts** you want to hide

Example (production microservices, not demos):

```caddyfile
reverse_proxy app1:8501 app2:8501 {
  lb_try_duration 10s
}
```

---

## README section you should add (copy-paste)

### 🔁 Caddy `lb_try_duration` clarification

````markdown
### Caddy load-balancer retries (`lb_try_duration`)

We intentionally **do NOT use** `lb_try_duration` for Streamlit apps.

Why:
- Streamlit runs as a single backend container
- If the container is crashing (e.g. missing `streamlit` in requirements),
  Caddy retries silently and the browser appears to “hang”
- This hides the real error and makes debugging harder

Example of what NOT to use for Streamlit demos:

```caddyfile
reverse_proxy streamlit-uniswapv3:8501 {
  lb_try_duration 30s
  lb_try_interval 500ms
}
````

Correct approach:

```caddyfile
handle_path /app/uniswapv3/* {
  reverse_proxy streamlit-uniswapv3:8501
}
```

If the app is down, Caddy fails fast and logs clearly show the problem.

```

---

## Summary (pin this)

| Item | Truth |
|----|----|
`lb_try_duration` | Caddy retry logic |
Pip failures | Cause container exit 127 |
Retry logic | Masks crashes |
Best for Streamlit | ❌ don’t use |
Best behavior | Fail fast |

---

If you want, next I can:
- merge this into a **final polished README**
- produce a **minimal “known-good” Caddyfile**
- add a **debug mode vs prod mode**
- or help you design a **multi-app registry** page

You spotted a *real* production nuance — good instincts.
```


