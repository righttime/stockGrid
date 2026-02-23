# Frontend Dockerfile - Multi-stage Build
# Step 1: Build
FROM node:20-slim AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Step 2: Serve with Nginx
FROM nginx:stable-alpine as production-stage

# [Decision] 커스텀 Nginx 설정 파일 복사 (API/WS 프록시 포함)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
