# Base image
FROM node:20-alpine

# Create app directory
WORKDIR /app

# Copy files
COPY package*.json ./
# COPY .env ./

RUN npm install

COPY . .

# RUN npm run build

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
