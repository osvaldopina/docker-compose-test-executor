
 .PHONY: verify lint format tests

VERSION=0.0.1
IMAGE_NAME=test_containers

clear_dev_env:
		rm -Rf .venv

create_dev_env:
		python3 -m venv .venv
		.venv/bin/pip install pip pep8 docker deepdiff pylint autopep8

lint:
		pylint test_containers.py

format:
		autopep8 --in-place --aggressive --recursive .

tests:
		python -m unittest discover  -p '*_test.py'

verify:  lint format tests

create_container:
		docker build . -t $(IMAGE_NAME):current -t $(IMAGE_NAME):latest -t $(IMAGE_NAME):$(VERSION)

verify_inside_container:
		docker run -it \
			-v /var/run/docker.sock:/var/run/docker.sock \
			-v $(shell pwd):/opt/build/ \
			-e HTTPSERVERVOLUME=$(shell pwd)/httpservervolume \
			$(IMAGE_NAME):latest \
			sh -c "cd /opt/build && make verify"

exec_test_inside_container_script:
		docker run \
			-v $(shell pwd)/testsConfig/test_execScript_config.json:/app/config.json \
			-v $(shell pwd)/testsConfig/execScriptTest.py:/app/execScriptTest.py \
			-v /var/run/docker.sock:/var/run/docker.sock \
		    -e HTTPSERVERVOLUME=$(shell pwd)/httpservervolume \
			-it $(IMAGE_NAME):latest

exec_test_inside_container_container:
		docker run \
			-v $(shell pwd)/testsConfig/test_execContainer_config.json:/app/config.json \
			-v /var/run/docker.sock:/var/run/docker.sock \
		    -e HTTPSERVERVOLUME=$(shell pwd)/httpservervolume \
			-it $(IMAGE_NAME):latest

createRequirements:
		pip freeze > requirements.txt

build: format lint tests create_container verify_inside_container exec_test_inside_container_script exec_test_inside_container_container
  