FROM python:3.9-alpine

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY *.py /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]