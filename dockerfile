FROM python:3.10-alpine3.16

WORKDIR /app

RUN  apk update && apk add docker make curl && mkdir /opt/tmp && mkdir -p /opt/tmp/src/dc_test_exec

COPY pyproject.toml /opt/tmp
COPY setup.py /opt/tmp
COPY src/dc_test_exec/* /opt/tmp/src/dc_test_exec/
RUN cd /opt/tmp && pip install . && rm -rf /opt/tmp

ENTRYPOINT [ "dc-test-exec"]