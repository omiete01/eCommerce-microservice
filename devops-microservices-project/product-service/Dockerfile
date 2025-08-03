FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask flask_sqlalchemy psycopg2-binary
EXPOSE 5002
CMD ["python", "app.py"]
