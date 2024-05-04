ARG ERRBOT_VERSION=6.2.0
from python:3.11-slim as builder


COPY .github/workflows/constraints.txt /constraints.txt
RUN pip install --upgrade --constraint /constraints.txt pip poetry
COPY ./ /app
WORKDIR /app
RUN rm -rf dist && poetry build

from python:3.11-slim
ARG ERRBOT_VERSION=6.2.0

COPY --from=builder /app/dist/*.whl /

RUN pip install --no-cache-dir errbot==$ERRBOT_VERSION err_aprs_backend-*-py3-none-any.whl --force-reinstall && \
    rm -rf /err_aprs_backend-*-py3-none-any.whl && \
    mkdir /errbot && cd /errbot && \
    errbot --init && \
    rm -rf /errbot/plugins/err-example/
COPY --from=builder /app/docker/config.py /errbot/config.py

WORKDIR /errbot
ENTRYPOINT [ "errbot" ]
