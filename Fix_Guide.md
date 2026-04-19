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
