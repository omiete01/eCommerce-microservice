FROM node:18-slim

WORKDIR /app
COPY . .

RUN npm install
RUN npm run build

# Serve using serve package
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "dist"]
