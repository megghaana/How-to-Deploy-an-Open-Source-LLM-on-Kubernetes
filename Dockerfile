FROM node:20-alpine
WORKDIR /app

# Copy server and UI
COPY server.js .
COPY chatbot-ui/ ./chatbot-ui/

# No npm install needed — server.js uses only Node built-ins

EXPOSE 8080

# OLLAMA_URL is injected at deploy time via --set-env-vars
ENV OLLAMA_URL=""
ENV PORT=8080

CMD ["node", "server.js"]
