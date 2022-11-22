import http
import json
import os
import ssl
import time
from enum import Enum
from typing import Tuple, Callable
from pathlib import Path

import deepdiff
import docker
import yaml

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

    def run_exec_container(self, service_name: str) -> int:
        pass


# pylint: disable=too-few-public-methods
class BaseReadinessCheck:

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        pass


class Services:

    def __init__(self, compose_file_path: Path,
                 container_service: BaseContainerService):
        self.compose_file = yaml.safe_load(compose_file_path.read_text())
        self.container_service = container_service

    def get_services_status(self) -> dict:
        result = {}
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if self.is_exec_service(service):
                break
            service_status = {
                'status': self.container_service.get_service_status(service_name)}
            if 'depends_on' in service:
                dependency_status = {}
                for dependency_name in service['depends_on']:
                    dependency_status[dependency_name] = self.container_service.get_service_status(
                        dependency_name)
                service_status['dependencies'] = dependency_status
            result[service_name] = service_status
        return result

    @staticmethod
    def is_exec_service(service_name: str) -> bool:
        return 'x-exec-container' in service_name

    def get_services_without_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if Services.is_exec_service(service):
                break
            if 'depends_on' not in service:
                result.append(service_name)
        return result

    def get_services_with_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if Services.is_exec_service(service):
                break
            if 'depends_on' in service:
                result.append(service_name)
        return result

    def check_all_dependents_ready(self, service_name: str) -> bool:
        service = self.compose_file['services'][service_name]
        if Services.is_exec_service(service):
            raise Exception(
                "trying to check dependencies for a exec container.")
        if 'depends_on' not in service:
            raise Exception(
                "trying to check dependencies service without dependencies.")
        all_true = True
        for dependency_name in service['depends_on']:
            all_true = all_true and (self.container_service.get_service_status(
                dependency_name) == ServiceStatus.READY)
        return all_true

    def get_services_ready_to_start(self) -> list[str] | None:
        result = []
        services_status = self.get_services_status()

        all_started = True
        for service in services_status.values():
            all_started = all_started and (
                    service['status'] == ServiceStatus.READY)

        if all_started:
            return None

        for service_name in self.get_services_with_dependency():
            if self.check_all_dependents_ready(service_name):
                result.append(service_name)

        for service_name in self.get_services_without_dependency():
            if services_status[service_name]['status'] == ServiceStatus.NOT_STARTED:
                result.append(service_name)

        return result

    def start_all_available_services(self, until: str = None) -> bool:

        service_status = self.get_services_status()
        if until is not None and until in service_status and service_status[
            until]['status'] == ServiceStatus.READY:
            return False

        services = self.get_services_ready_to_start()

        if services is None:
            return False

        for service_name in services:
            self.container_service.start_service(service_name)

        return True

    @staticmethod
    def transform_status_to_log(status: dict) -> list[str]:
        result = []

        for service_name in status:
            service_status = status[service_name]
            result.append(f'{service_name} : {service_status["status"].name}')
            if 'dependencies' in service_status:
                deps = service_status['dependencies']
                for dep_name in deps:
                    result.append(f'    -> {dep_name} : {deps[dep_name].name}')

        return result

    def start(self, verification_step_millis: int, presentation_step_millis: int,
              presentation: Callable[[list[str]], None], until: str = None) -> int:

        presentation(
            Services.transform_status_to_log(
                self.get_services_status()))
        last_presentation = time.time()
        while True:
            last_verification = time.time()
            if not self.start_all_available_services(until):
                presentation(
                    Services.transform_status_to_log(
                        self.get_services_status()))
                break
            if (time.time() - last_presentation) * \
                    1_000 > presentation_step_millis:
                presentation(
                    Services.transform_status_to_log(
                        self.get_services_status()))
                last_presentation = time.time()
            if (time.time() - last_verification) * \
                    1_000 < verification_step_millis:
                time.sleep(verification_step_millis // 1_000)

    def show_status(self, presentation: Callable[[list[str]], None]):
        presentation(
            Services.transform_status_to_log(
                self.get_services_status()))

    def run_exec_container(self) -> int:
        return self.container_service.run_exec_container()


class ContainerService(BaseContainerService):

    def __init__(self, compose_file_path: Path, **kwargs):
        self.docker_client = docker.from_env()
        self.compose_file_path = compose_file_path
        self.compose_file = yaml.safe_load(compose_file_path.read_text())
        self.environment = kwargs.get('environment', dict(os.environ))
        self.compose_file_path_host = kwargs.get('compose_file_path_host', compose_file_path)
        if 'readiness_check' in kwargs:
            self.readiness_check = kwargs.get('readiness_check')
        else:
            self.readiness_check = HttpReadinessCheck(self.compose_file)

    def __del__(self):
        self.docker_client.close()

    def _get_container_ip(self, container):
        if 'IPAddress' in container.attrs['NetworkSettings']:
            if container.attrs['NetworkSettings']['IPAddress'].strip():
                return container.attrs['NetworkSettings']['IPAddress']
        if len(container.attrs['NetworkSettings']['Networks'].keys()) > 0:
            first_network = list(
                container.attrs['NetworkSettings']['Networks'].keys())[0]
            return container.attrs['NetworkSettings']['Networks'][first_network]['IPAddress']
        raise Exception(
            f'Could not find Ip for container {container.attrs["Name"]}')

    def get_service_status(self, service_name: str) -> ServiceStatus:
        try:
            container = self.docker_client.containers.get(service_name)
            if container.status == 'exited':
                return ServiceStatus.NOT_STARTED
            if container.status in ['created', 'running', 'restarting']:
                if self.readiness_check.is_ready(
                        service_name, self._get_container_ip(container)):
                    return ServiceStatus.READY
                return ServiceStatus.NOT_READY
            return ServiceStatus.INVALID
        except NotFound:
            return ServiceStatus.NOT_STARTED

    def start_service(self, service_name: str) -> None:
        self.docker_client.containers.run(
            'docker/compose:alpine-1.29.2',
            f'-f /opt/docker-compose.yml up -d {service_name}',
            volumes={
                str(self.compose_file_path_host.absolute()): {
                    'bind': '/opt/docker-compose.yml',
                    'mode': 'ro'
                },
                '/var/run/docker.sock': {
                    'bind': '/var/run/docker.sock'
                }
            },
            remove=True,
            environment=self.environment,
            detach=True
        )

    def _get_exec_container_name(self) -> str | None:
        for service_name in self.compose_file['services']:
            if 'x-exec-container' in self.compose_file['services'][service_name]:
                return service_name
        return None

    def run_exec_container(self, service_name: str):

        self.docker_client.containers.run(
            'docker/compose:alpine-1.29.2',
            f'-f /opt/docker-compose.yml up -d {service_name}',
            volumes={
                str(self.compose_file_path_host.absolute()): {
                    'bind': '/opt/docker-compose.yml',
                    'mode': 'ro'
                },
                '/var/run/docker.sock': {
                    'bind': '/var/run/docker.sock'
                }
            },
            remove=True,
            environment=self.environment
        )
        return self.docker_client.containers.get(
            service_name).attrs['State']['ExitCode']

    def _stop_service(self, service_name: str) -> None:
        try:
            container = self.docker_client.containers.get(service_name)
            container.stop()
        except NotFound:
            pass


def check(config: dict) -> Tuple[bool, any]:
    connection = None
    try:
        if config['protocol'] == 'https':
            connection = http.client.HTTPSConnection(
                host=config['host'] if 'host' in config else config['service-ip'],
                port=config['port'],
                # pylint: disable=protected-access
                context=ssl._create_unverified_context())
        else:
            connection = http.client.HTTPConnection(
                host=config['host'] if 'host' in config else config['service-ip'],
                port=config['port'])
        connection.request(
            method='GET',
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
    # pylint: disable=broad-except
    except Exception as exc:
        return False, exc
    finally:
        if connection is not None:
            connection.close()


class HttpReadinessCheck(BaseReadinessCheck):

    def __init__(self, compose_file: dict, check_function=check):
        self._not_ready_cause = None
        self.compose_file = compose_file
        self.check_function = check_function

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        all_true = True

        for config in self.compose_file['services'][service_name]['x-http-readiness-checks']:
            config['service-ip'] = service_ip
            all_true = all_true and self.check_function(config)

        return all_true


class TestContainer:

    def __init__(self, compose_file_path: str,
                 print_function: Callable[[str], None] = print):
        path = Path(compose_file_path)
        self.services = Services(path, ContainerService(path))
        self.print_function = print_function
        self.last_lines_showed = 0
        self.max_line_size = 0

    def _print(self, line: str):
        self.print_function(line)

    def _present_status(self, lines_to_show: list[str]):
        if self.last_lines_showed > 0:
            self._print("\033[F" * (self.last_lines_showed + 1))
        for line in lines_to_show:
            if len(line) > self.max_line_size:
                self.max_line_size = len(line)
            self._print(line + " " * (self.max_line_size - len(line)))
        self.last_lines_showed = len(lines_to_show)

    def start(self, verification_step_millis: int,
              presentation_step_millis: int, until: str = None):
        self.services.start(
            verification_step_millis,
            presentation_step_millis,
            self._present_status,
            until)

    def show_status(self):
        self.services.show_status(self._present_status)
