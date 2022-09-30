FROM python:3.7.14-alpine3.16

WORKDIR /app

RUN  apk update && apk add docker make curl && \
     pip install pep8 docker deepdiff pylint autopep8

COPY test_containers.py test_containers.py
COPY test_containers_starter.py test_containers_starter.py  

CMD [ "python3", "-m" , "test_containers_starter"]
    
