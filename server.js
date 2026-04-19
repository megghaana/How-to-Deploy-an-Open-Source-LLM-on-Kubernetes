// server.js — lightweight proxy for Cloud Run
// Receives chat requests from the browser, forwards them to Ollama (via ngrok)
// Run locally: node server.js
// Deploy to Cloud Run: see Dockerfile + deploy commands in README

const http  = require('http');
const https = require('https');
const fs    = require('fs');
const path  = require('path');
const url   = require('url');

// ── Config ─────────────────────────────────────────────────
// Set OLLAMA_URL env var to your ngrok URL, e.g.:
//   export OLLAMA_URL=https://abc123.ngrok-free.app
const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const PORT       = process.env.PORT || 8080;

console.log(`[proxy] OLLAMA_URL = ${OLLAMA_URL}`);
console.log(`[proxy] Listening on port ${PORT}`);

// ── Helpers ─────────────────────────────────────────────────
function serveStatic(res, filePath, contentType) {
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
}

function setCORS(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}

// ── Server ───────────────────────────────────────────────────
const server = http.createServer((req, res) => {
  setCORS(res);
  const parsed = url.parse(req.url);

  // Preflight
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // Health check (used by chatbot status indicator)
  if (req.method === 'GET' && parsed.pathname === '/api/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', ollama: OLLAMA_URL }));
    return;
  }

  // Proxy /api/chat → Ollama
  if (req.method === 'POST' && parsed.pathname === '/api/chat') {
    proxyToOllama(req, res);
    return;
  }

  // Proxy /api/tags → Ollama (for model listing)
  if (req.method === 'GET' && parsed.pathname === '/api/tags') {
    const ollamaUrl = new URL('/api/tags', OLLAMA_URL);
    const mod = ollamaUrl.protocol === 'https:' ? https : http;
    const proxyReq = mod.request(ollamaUrl, proxyRes => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    });
    proxyReq.on('error', e => {
      console.error('[proxy] tags error:', e.message);
      res.writeHead(502); res.end('Ollama unreachable');
    });
    proxyReq.end();
    return;
  }

  // Serve static files
  if (req.method === 'GET') {
    const staticDir = path.join(__dirname, 'chatbot-ui');
    let filePath = parsed.pathname === '/' ? '/index.html' : parsed.pathname;
    const ext = path.extname(filePath);
    const mime = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css' };
    serveStatic(res, path.join(staticDir, filePath), mime[ext] || 'text/plain');
    return;
  }

  res.writeHead(404); res.end();
});

function proxyToOllama(req, res) {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    const ollamaUrl = new URL('/api/chat', OLLAMA_URL);
    const mod = ollamaUrl.protocol === 'https:' ? https : http;

    const options = {
      hostname: ollamaUrl.hostname,
      port:     ollamaUrl.port || (ollamaUrl.protocol === 'https:' ? 443 : 80),
      path:     '/api/chat',
      method:   'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        // ngrok requires this header
        'ngrok-skip-browser-warning': 'true'
      }
    };

    const proxyReq = mod.request(options, proxyRes => {
      // Stream the response straight back — important for SSE/streaming
      res.writeHead(proxyRes.statusCode, {
        'Content-Type': 'application/x-ndjson',
        'Transfer-Encoding': 'chunked',
        'Access-Control-Allow-Origin': '*'
      });
      proxyRes.pipe(res);
    });

    proxyReq.on('error', e => {
      console.error('[proxy] chat error:', e.message);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Cannot reach Ollama at ${OLLAMA_URL}: ${e.message}` }));
    });

    proxyReq.write(body);
    proxyReq.end();
  });
}

server.listen(PORT);
