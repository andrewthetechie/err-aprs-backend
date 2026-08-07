ARG ERRBOT_VERSION=6.2.0
FROM python:3.13-slim as builder


COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir uv
RUN rm -rf dist && uv build

FROM python:3.13-slim
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
