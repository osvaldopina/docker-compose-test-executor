from enum import Enum

import yaml
from pathlib import Path


class ServiceStatus(Enum):
    NOT_STARTED = 1
    NOT_READY = 2
    READY = 3


class BaseContainerService:

    def get_service_status(self, service_name: str) -> ServiceStatus:
        pass

    def start_service(self, servive_name: str) -> None:
        pass


class Services:

    def __init__(self, path: Path, container_service: BaseContainerService):
        self.compose_file = yaml.safe_load(path.read_text())
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

        for service_name in self.get_services_with_dependency():
            if self.check_all_dependents_ready(service_name):
                result.append(service_name)

        for service_name in self.get_services_without_dependency():
            if services_status[service_name]['status'] == ServiceStatus.NOT_STARTED:
                result.append(service_name)

        return result

    def start_all_availabe_serverice(self) -> bool:
        pass
