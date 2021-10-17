FROM python:3.8.5-buster

ARG CONTAINER_ENV=production

ENV CONTAINER_ENV=${CONTAINER_ENV} PYTHONUNBUFFERED=1
ENV BUILD_REF=${BUILD_REF} BUILD_COMMIT=${BUILD_COMMIT} BUILD_DATE=${BUILD_DATE}

WORKDIR /app
COPY requirements.txt  /app/requirements.txt

RUN  pip install -r requirements.txt
RUN  opentelemetry-bootstrap --action=install
ARG CACHEBUST=1

COPY . /app
CMD ["opentelemetry-instrument","python","-m", "uvicorn", "app:app", "--host","0.0.0.0","--port","80"]

