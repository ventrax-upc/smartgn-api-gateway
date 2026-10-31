FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund

FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY --from=dependencies --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node package.json ./
COPY --chown=node:node src ./src
COPY --chown=node:node docs/openapi.json ./docs/openapi.json
USER node
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s CMD wget -qO- http://127.0.0.1:${API_PORT:-8000}/health || exit 1
CMD ["node", "src/server.js"]
