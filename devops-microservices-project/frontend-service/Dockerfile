# Base image
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
COPY .env ./
RUN npm install
COPY . .
RUN npm run build

# Serve with lightweight web server
FROM node:20-alpine AS runtime
WORKDIR /app
COPY --from=builder /app/dist ./dist
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
