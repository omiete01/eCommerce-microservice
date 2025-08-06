FROM python:3.10-slim-bullseye
WORKDIR /app
COPY . .
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 5001
CMD ["python", "app.py"]
