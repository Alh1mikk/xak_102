FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY run_parcer.py .
COPY tests tests

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
