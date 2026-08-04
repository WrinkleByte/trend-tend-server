FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Dev-mode container (source bind-mounted by docker-compose.yml, hot reload
# via --host so the Vite dev server is reachable from outside the
# container). There's no production build/nginx image yet — see
# docs/architecture.md Section 5 for the offline/PWA build, which still
# ships via `npm run build` + your own static host or a future prod image.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
