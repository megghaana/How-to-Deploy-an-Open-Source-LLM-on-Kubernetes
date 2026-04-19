# How to Deploy an Open Source LLM on Kubernetes
### Complete setup guide for the DrDroid Developer Advocate assignment

---

## 📁 File Structure

```
k8s-llm-stack/
├── ollama-deployment.yaml    # Ollama LLM + model pull job
├── monitoring.yaml           # Prometheus + Grafana
├── chatbot-deployment.yaml   # Chatbot UI on k8s
├── chatbot-ui/
│   └── index.html            # Polished chat interface
└── compare/
    └── compare_models.py     # Mistral vs Claude analysis script
```

---

## 🚀 Step-by-Step Setup

### Prerequisites
- Docker Desktop (with Kubernetes enabled) **OR** minikube installed
- `kubectl` CLI
- Python 3.9+

---

### Step 1 — Start your cluster

**Option A: Docker Desktop**
> Settings → Kubernetes → Enable Kubernetes → Apply & Restart

**Option B: minikube**
```bash
minikube start --memory=8192 --cpus=4
```

Verify:
```bash
kubectl cluster-info
kubectl get nodes
```

---

### Step 2 — Deploy Ollama (the LLM runtime)

```bash
kubectl apply -f ollama-deployment.yaml
```

Wait for Ollama to be ready and the Mistral model to pull (~5 min):
```bash
kubectl get pods -n llm-stack -w
kubectl logs job/ollama-pull-mistral -n llm-stack -f
```

---

### Step 3 — Deploy Prometheus + Grafana monitoring

```bash
kubectl apply -f monitoring.yaml
```

Access Grafana:
```bash
kubectl port-forward svc/grafana-service 3000:3000 -n monitoring
```
Open http://localhost:3000 — login: `admin` / `admin123`

**Import dashboard:** In Grafana → Dashboards → Import → enter ID `3119`
(Kubernetes cluster monitoring dashboard)

---

### Step 4 — Access the LLM API

```bash
# Port-forward Ollama so the chatbot can reach it
kubectl port-forward svc/ollama-service 11434:11434 -n llm-stack
```

Test it works:
```bash
curl http://localhost:11434/api/tags
curl http://localhost:11434/api/chat \
  -d '{"model":"mistral:7b","messages":[{"role":"user","content":"Hello!"}],"stream":false}'
```

---

### Step 5 — Run the Chatbot UI

Keep the port-forward above running, then open `chatbot-ui/index.html` directly in your browser.

Or serve it locally:
```bash
cd chatbot-ui
python3 -m http.server 8080
# Open http://localhost:8080
```

Suggested questions to ask (good for your video demo!):
- "Which model are you?"
- "What is your knowledge cutoff?"
- "Explain Kubernetes in simple terms"

---

### Step 6 — Run Comparative Analysis (bonus section)

```bash
pip install anthropic requests tabulate
export ANTHROPIC_API_KEY=your_key_here

# Make sure port-forward is still running (step 4)
cd compare
python3 compare_models.py
```

This outputs:
- `comparison_results_TIMESTAMP.json` — full responses
- `comparison_report_TIMESTAMP.md`   — formatted markdown for your blog

---

## 📊 Grafana Dashboard Setup

1. Go to http://localhost:3000
2. Login: `admin` / `admin123`
3. Go to **Connections → Data Sources** → confirm Prometheus is there
4. Go to **Dashboards → Import**
5. Enter dashboard ID: `3119` (Kubernetes cluster monitoring)
6. Select your Prometheus data source → Import

You should now see CPU, memory, pod health, and network metrics.

---

## 🎥 Recording Tips (for your video)

1. Record in this order:
   - Show `kubectl get nodes` (cluster is live)
   - `kubectl apply -f ollama-deployment.yaml` (deploy)
   - Watch pods come up with `kubectl get pods -w`
   - Show Grafana dashboard
   - Open chatbot, ask the 4 suggested questions
   - Show comparison script running
2. Use Loom or OBS for recording
3. Edit with veed.io — add captions, zoom in on terminal text

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| Pods stuck in `Pending` | Not enough RAM — reduce limits in ollama-deployment.yaml or give minikube more memory |
| Model pull times out | Run `kubectl logs job/ollama-pull-mistral -n llm-stack` — try increasing `--max-time` in the curl command |
| Chatbot shows "offline" | Make sure `kubectl port-forward svc/ollama-service 11434:11434 -n llm-stack` is running |
| Grafana shows no data | Check Prometheus pod is healthy: `kubectl get pods -n monitoring` |

---

## 💡 Blog Outline

```
Title: How to Deploy an Open Source LLM Reliably on Kubernetes

1. Introduction — why self-host an LLM?
2. Architecture overview (Ollama + K8s + Grafana diagram)
3. Setting up the cluster
4. Deploying Mistral 7B with Ollama
5. Monitoring with Prometheus + Grafana
6. Building the chatbot UI
7. Comparative analysis: Mistral vs Claude (cost, speed, quality)
8. Conclusion + next steps (autoscaling, GPU nodes, ingress)
```
