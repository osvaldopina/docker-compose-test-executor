import http
import json
import os
import ssl
from enum import Enum
from typing import Tuple

import deepdiff
import docker
import yaml
from pathlib import Path

from docker.errors import NotFound


class ServiceStatus(Enum):
    INVALID = 1
    NOT_STARTED = 2
    NOT_READY = 3
    READY = 4


class BaseContainerService:

    def get_service_status(self, service_name: str) -> ServiceStatus:
        pass

    def start_service(self, service_name: str) -> None:
        pass


class BaseReadinessCheck:

    def is_ready(self, service_name: str) -> bool:
        pass


class Services:

    def __init__(self, compose_file_path: Path, container_service: BaseContainerService):
        self.compose_file = yaml.safe_load(compose_file_path.read_text())
        self.container_service = container_service

    def get_services_status(self) -> dict:
        result = {}
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if 'x-exec-container' in service:
                break
            service_status = {
                'status': self.container_service.get_service_status(service_name)
            }
            if 'depends_on' in service:
                dependency_status = {}
                for dependency_name in service['depends_on']:
                    dependency_status[dependency_name] = self.container_service.get_service_status(dependency_name)
                service_status['dependencies'] = dependency_status
            result[service_name] = service_status
        return result

    def get_services_without_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if 'x-exec-container' in service:
                break
            if 'depends_on' not in service:
                result.append(service_name)
        return result

    def get_services_with_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if 'x-exec-container' in service:
                break
            if 'depends_on' in service:
                result.append(service_name)
        return result

    def check_all_dependents_ready(self, service_name: str) -> bool:
        service = self.compose_file['services'][service_name]
        if 'x-exec-container' in service:
            raise Exception("trying to check dependencies for a exec container.")
        if 'depends_on' not in service:
            raise Exception("trying to check dependencies service without dependencies.")
        all_true = True
        for dependency_name in service['depends_on']:
            all_true = all_true and (self.container_service.get_service_status(dependency_name) == ServiceStatus.READY)
        return all_true

    def get_services_ready_to_start(self) -> list[str]:
        result = []
        services_status = self.get_services_status()

        all_started = True
        for service_name in services_status:
            all_started = all_started and (services_status[service_name]['status'] == ServiceStatus.READY)

        if all_started:
            return None

        for service_name in self.get_services_with_dependency():
            if self.check_all_dependents_ready(service_name):
                result.append(service_name)

        for service_name in self.get_services_without_dependency():
            if services_status[service_name]['status'] == ServiceStatus.NOT_STARTED:
                result.append(service_name)

        return result

    def start_all_available_services(self) -> bool:

        services = self.get_services_ready_to_start()

        if services is None:
            return False

        for service_name in services:
            self.container_service.start_service(service_name)

        return True


class ContainerService(BaseContainerService):

    def __init__(self, compose_file_path: Path, **kwargs):
        self.docker_client = docker.from_env()
        self.compose_file_path = compose_file_path
        self.environment = kwargs.get('environment', os.environ)

    def get_service_status(self, service_name: str) -> ServiceStatus:
        try:
            container = self.docker_client.containers.get(service_name)
            if container.status in ['created', 'running', 'restarting']:
                return ServiceStatus.NOT_READY
            else:
                return ServiceStatus.INVALID
        except NotFound:
            return ServiceStatus.NOT_STARTED

        pass

    def start_service(self, service_name: str) -> None:
        self.docker_client.containers.run(
            'docker/compose:alpine-1.29.2',
            f'-f /opt/docker-compose.yml up -d {service_name}',
            volumes={
                str(self.compose_file_path.absolute()): {
                    'bind': '/opt/docker-compose.yml',
                    'mode': 'ro'
                },
                '/var/run/docker.sock': {
                    'bind': '/var/run/docker.sock'
                }
            },
            environment=self.environment,
            detach=True
        )


def check(config: dict) -> Tuple[bool, any]:
    connection = None
    not_ready_cause = None
    try:
        if config['protocol'] == 'https':
            connection = http.client.HTTPSConnection(
                host=config['host'],
                port=config['port'],
                context=ssl._create_unverified_context())
        else:
            connection = http.client.HTTPConnection(
                host=config['host'],
                port=config['port'])
        connection.request(  #
            method='GET',  #
            url=config['url'],
            headers=config['headers'] if 'headers' in config else {})
        response = connection.getresponse()
        if response.status == config['response-status']:
            if 'json-body' in config:
                expected_json_body = json.loads(config['json-body'])
                actual_json_body = json.loads(response.read())
                diff = deepdiff.DeepDiff(expected_json_body, actual_json_body)
                if not diff.to_dict():
                    return True, ''
                return False, f'different json body: {diff.to_dict()}'
            return True, ''
        return False, 'different status'
    except Exception as exc:
        return False, exc
    finally:
        if connection is not None:
            connection.close()


class HttpReadinessCheck(BaseReadinessCheck):

    def __init__(self, compose_file: dict):
        self._not_ready_cause = None
        self.compose_file = compose_file

    def is_ready(self, service_name: str) -> bool:

        all_true = True

        for config in self.compose_file['services'][service_name]['x-http-readiness-checks']:
            all_true = all_true and check(config)

        return all_true
