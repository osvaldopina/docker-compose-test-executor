FROM python:3.10-alpine3.16

WORKDIR /app

RUN  apk update && apk add docker make curl

COPY src /opt/src
RUN cd /opt/src && pip install . && rm -rf /opt/src

ENTRYPOINT [ "dc-test-exec"]