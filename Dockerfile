FROM python:3-alpine

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .
ENTRYPOINT [ "python", "main.py" ]
