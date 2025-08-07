# Stage 1: Builder
FROM python:3.10-slim-bullseye AS builder
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Stage 2: Runtime
FROM python:3.10-slim-bullseye
WORKDIR /app
COPY --from=builder /app .
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
EXPOSE 5002
CMD ["python", "app.py"]
