# Etapa 1: compilar la app React
FROM node:20-slim AS builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# VITE_API_BASE_URL vacío → el cliente usa la misma origin (nginx),
# que hace de proxy hacia el backend. Sin esto, el cliente intentaría
# conectarse a window.hostname:8000 en lugar de pasar por nginx.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# Etapa 2: servir con nginx
FROM nginx:1.27-alpine

COPY --from=builder /frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
