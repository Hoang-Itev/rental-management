# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Nginx Gateway
FROM nginx:1.27-alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
COPY infra/nginx/default.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]