# # Base image
# FROM node:20-alpine AS builder
# WORKDIR /app
# COPY package*.json ./
# COPY .env ./
# RUN npm install
# COPY . .
# RUN npm run build

# # Serve with lightweight web server
# FROM node:20-alpine AS runtime
# WORKDIR /app
# COPY --from=builder /app/dist ./dist
# RUN npm install -g serve
# EXPOSE 3000
# CMD ["serve", "-s", "dist", "-l", "3000"]


# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
COPY .env ./
RUN npm install --production=false
COPY . .
RUN npm run build

# Production stage using a minimal image
FROM nginx:1.25-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]

RUN sed -i 's/80;/3000;/' /etc/nginx/conf.d/default.conf
