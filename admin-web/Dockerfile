FROM node:22-alpine AS build

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app

COPY package*.json ./
RUN npm config set registry "$NPM_REGISTRY" && npm ci

COPY . .
# Docker 中由 Nginx 在根路径提供，因此构建基准路径为 /
ENV ADMIN_BASE=/
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
