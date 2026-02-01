FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV SQLITE_FILE_PATH=/data/restaurants.db

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "app.py"]
