# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
COPY .env ./
RUN npm config set registry https://registry.npmjs.org/
RUN npm config set fetch-timeout 60000
RUN npm config set fetch-retries 5
RUN npm install --production=false
COPY . .
RUN npm run build

# Production stage using a minimal image
FROM nginx:1.25-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]

RUN sed -i 's/80;/3000;/' /etc/nginx/conf.d/default.conf
