FROM --platform=${BUILDPLATFORM} python:3-alpine

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .
COPY strategies/ ./strategies/
ENTRYPOINT [ "python", "main.py" ]
