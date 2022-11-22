VERSION=0.0.1
IMAGE_NAME=dc_test_exec

.PHONY: clear_dev_env
clear_dev_env:
		rm -Rf .venv

.PHONY: create_dev_env
create_venv:
		python3 -m venv .venv

create_dev_env:
		pip install pip pep8 docker deepdiff pylint autopep8 deepdiff docker pyyaml click
		cd src && pip install .

.PHONY: lint
lint:
		pylint src/dc_test_exec/docker_compose_test_executor.py

format:
		autopep8 --in-place --aggressive --recursive --max-line-length 120 .

tests:
		python -m unittest src/dc_test_exec/*tests.py

verify:  lint format tests

create_container: verify
		docker build . -t osvaldopina/$(IMAGE_NAME):latest -t osvaldopina/$(IMAGE_NAME):$(VERSION)

create_build_container:
		docker build -f dockerfile-build-container -t local-build-container .

build: create_dev_env verify create_container

login_docker_hub: build_container
	docker login -u $(PT_DOCKER_HUB_USER) -p $(PT_DOCKER_HUB_PASSWD)

push: login_docker_hub build
		docker push --all-tags osvaldopina/$(IMAGE_NAME)

push_inside_container: create_build_container
		docker run -t \
			-v /var/run/docker.sock:/var/run/docker.sock \
			-v $(shell pwd):/opt/build/ \
			-e HOST_PROJECT_HOME=$(shell pwd) \
			-e HTTPSERVERVOLUME=$(shell pwd)/httpservervolume \
			-e PT_DOCKER_HUB_USER=$(PT_DOCKER_HUB_USER) \
			-e PT_DOCKER_HUB_PASSWD=$(PT_DOCKER_HUB_PASSWD) \
			local-build-container \
			sh -c "make push"
