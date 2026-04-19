# Fix Guide — Monitoring + Public Access
## Addresses: Grafana "No data", Prometheus 400/404 errors, cloud deployment

---

## WHY the old config failed (quick explanation)

### Problem 1 — kubernetes-nodes: 400 error
Prometheus was trying to scrape node metrics by hitting each node's IP directly
on port 10250 (kubelet). That requires mTLS auth. The fix is to route all scrapes
through the Kubernetes API server proxy, which handles auth automatically using
the ServiceAccount token Prometheus already has.

### Problem 2 — ollama: 404 on /metrics
Ollama is a plain REST API. It has NO Prometheus /metrics endpoint.
→ Solution: remove that scrape job entirely. To monitor Ollama health,
  use the /api/tags health check instead (shown in the chatbot UI).

### Problem 3 — Grafana "No data"
Caused by both of the above + wrong service name in the datasource URL.
The fixed config uses `http://prometheus:9090` (matching the Service name).

---

## PART 1 — Fix Monitoring

### Step 1 — Tear down the broken setup
```bash
kubectl delete namespace monitoring --ignore-not-found
```

### Step 2 — Apply the fixed config
```bash
kubectl apply -f monitoring-fixed.yaml
```

### Step 3 — Wait for pods
```bash
kubectl get pods -n monitoring -w
# Wait until both prometheus-xxx and grafana-xxx show Running
# Ctrl+C when ready
```

### Step 4 — Port-forward both services
Open two terminals:

**Terminal A — Prometheus:**
```bash
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
```

**Terminal B — Grafana:**
```bash
kubectl port-forward svc/grafana 3000:3000 -n monitoring
```

### Step 5 — Verify Prometheus targets
Open http://localhost:9090/targets

You should see:
- `kubernetes-nodes` → UP (green)
- `kubernetes-cadvisor` → UP (green)
- `prometheus` → UP (green)
- `kubernetes-pods` → 0/0 is fine (only scrapes annotated pods)

If nodes show "connection refused", your cluster may need 1-2 min to settle.

### Step 6 — Set up Grafana
1. Open http://localhost:3000
2. Login: `admin` / `admin123`
3. Go to **Connections → Data Sources** → you should see Prometheus already configured
4. Click it → scroll down → click **Save & Test** → should say "Data source is working"

### Step 7 — Import dashboards

**Option A — Kubernetes cluster overview (recommended):**
- Dashboards → New → Import
- Enter ID: `315` → Load
- Select Prometheus data source → Import
- You'll see: CPU usage, memory, pod counts, network I/O

**Option B — Node exporter full:**
- Same steps, use ID: `1860`

**Option C — K8s pod monitoring:**
- Same steps, use ID: `6417`

---

## PART 2 — Public Access (Hybrid: Local K8s + Cloud UI)

### Architecture
```
Browser (anywhere)
    │
    ▼
Cloud Run (Google Cloud)        ← your public URL
  [Node.js proxy server]
  [chatbot-ui/index.html]
    │
    │  HTTPS (ngrok tunnel)
    ▼
ngrok running on your laptop
    │
    ▼
kubectl port-forward
    │
    ▼
Ollama pod in local K8s         ← stays on your machine
  mistral:7b
```

---

### Step 1 — Install ngrok
```bash
# macOS
brew install ngrok

# Linux
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Sign up free at https://ngrok.com → copy your auth token
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### Step 2 — Port-forward Ollama + start ngrok tunnel
In separate terminals:

**Terminal A:**
```bash
kubectl port-forward svc/ollama-service 11434:11434 -n llm-stack
```

**Terminal B:**
```bash
ngrok http 11434
```

ngrok will show something like:
```
Forwarding  https://abc123.ngrok-free.app → http://localhost:11434
```

Copy that `https://abc123.ngrok-free.app` URL — you'll need it next.

### Step 3 — Deploy to Google Cloud Run

**Prerequisites:**
```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

**Build and deploy:**
```bash
# From the k8s-llm-stack-v2/ directory

# Build and push image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/llm-chatbot:v1

# Deploy to Cloud Run — paste your ngrok URL here
gcloud run deploy llm-chatbot \
  --image gcr.io/YOUR_PROJECT_ID/llm-chatbot:v1 \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars OLLAMA_URL=https://abc123.ngrok-free.app \
  --port 8080
```

Cloud Run will give you a URL like `https://llm-chatbot-xxxx.run.app`

That's your public chatbot. Share it in your video!

---

### Step 4 — Update ngrok URL when it changes (free plan)

Free ngrok URLs reset every time you restart ngrok. Update Cloud Run:
```bash
ngrok http 11434  # get new URL

gcloud run services update llm-chatbot \
  --set-env-vars OLLAMA_URL=https://NEW_URL.ngrok-free.app \
  --region asia-south1
```

**Tip for the video:** Use a paid ngrok plan ($8/month) or ngrok's static domain
feature (1 free static domain per account now) to avoid this.

---

## PART 3 — Test Everything Works

### Verify monitoring
```bash
# Check targets
curl http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'
# Should show "up" for node and cadvisor jobs

# Check a metric exists
curl 'http://localhost:9090/api/v1/query?query=up' | python3 -m json.tool
```

### Verify chatbot locally
```bash
node server.js &  # or just open index.html directly
# Open http://localhost:8080
```

### Verify Cloud Run
```bash
# Get the URL
gcloud run services describe llm-chatbot --region asia-south1 --format='value(status.url)'

# Test the health endpoint
curl https://YOUR_URL.run.app/api/health
```

---

## Folder Structure
```
k8s-llm-stack-v2/
├── monitoring-fixed.yaml   # Fixed Prometheus + Grafana
├── server.js               # Node proxy (no dependencies)
├── Dockerfile              # For Cloud Run
├── chatbot-ui/
│   └── index.html          # URL-aware chatbot frontend
└── README.md               # This file
```

---

## Blog Section — Architecture Explanation

> **"Hybrid cloud"** means your LLM stays private on your local Kubernetes cluster,
> while the public-facing chatbot UI runs on Cloud Run (serverless, scales to zero
> when unused = free when idle). ngrok creates a secure HTTPS tunnel from Cloud Run
> to your local Ollama, so no cloud GPU costs are incurred. The proxy server on
> Cloud Run also avoids CORS issues since the browser never calls Ollama directly.
