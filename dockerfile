FROM python:3.11.0a7-alpine3.15

WORKDIR /app

RUN  apk update && apk add docker && apk add make && \
     pip install pep8 docker deepdiff pylint autopep8

COPY test_containers.py test_containers.py
COPY test_containers_starter.py test_containers_starter.py  

CMD [ "python3", "-m" , "test_containers_starter"]
    