import os
from enum import Enum

import docker
import yaml
from pathlib import Path

from docker.errors import NotFound


class ServiceStatus(Enum):
    NOT_STARTED = 1
    NOT_READY = 2
    READY = 3


class BaseContainerService:

    def get_service_status(self, service_name: str) -> ServiceStatus:
        pass

    def start_service(self, service_name: str) -> None:
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
            return container.status != 'exited'
        except NotFound:
            return ServiceStatus.NOT_STARTED

        pass

    def start_service(self, service_name: str) -> None:
        try:
            container = self.docker_client.containers.run(
                'docker/compose:alpine-1.29.2',
                f'-f /opt/docker-compose.yml up {service_name}',
                volumes={
                    str(self.compose_file_path.absolute()): {
                        'bind': '/opt/docker-compose.yml',
                        'mode': 'ro'
                    },
                    '/var/run/docker.sock': {
                        'bind': '/var/run/docker.sock'
                    }
                },
                environment=self.environment
            )
        except Exception as e:
            print(e)

        print(container)
