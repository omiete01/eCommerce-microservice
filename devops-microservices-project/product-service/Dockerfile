FROM python:3.10-slim-bullseye
WORKDIR /app
COPY . .
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends gcc libpq-dev && \
	pip install --upgrade pip && \
	pip install --no-cache-dir -r requirements.txt && \
	apt-get purge -y --auto-remove gcc libpq-dev && \
	rm -rf /var/lib/apt/lists/*
EXPOSE 5002
CMD ["python", "app.py"]
