import http
import json
import os
import ssl
import sys
import time
from enum import Enum
from typing import Tuple, Callable
from pathlib import Path
from os.path import exists

import deepdiff
import docker
import yaml

from docker.errors import NotFound


class ServiceStatus(Enum):
    INVALID = 1
    NOT_STARTED = 2
    NOT_READY = 3
    READY = 4
    EXECUTED_SUCCESSFULLY = 5
    EXECUTED_ERROR = 6


class BaseContainerService:

    def get_service_status(self, service_name: str) -> ServiceStatus:
        pass

    def start_service(self, service_name: str) -> None:
        pass

    def run_exec_container(self) -> int:
        pass

    def restart(self, service_name: str) -> None:
        pass

    def run_one_shot_service(self, one_shot_service_name):
        pass


# pylint: disable=too-few-public-methods
class BaseReadinessCheck:

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        pass


class ComposeReadinessCheck:

    def __init__(self, health_checks: list[BaseReadinessCheck]):
        self._health_checks = health_checks

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        for health_check in self._health_checks:
            if not health_check.is_ready(service_name, service_ip):
                return False
        return True


class Services:

    def __init__(self, compose_file_path: Path,
                 container_service: BaseContainerService):
        self.compose_file = yaml.safe_load(compose_file_path.read_text())
        self.container_service = container_service

    def get_services_status(self) -> dict:
        result = {}
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if self.is_exec_service(service_name):
                continue
            service_status = {
                'status': self.container_service.get_service_status(service_name)}
            if 'depends_on' in service:
                dependency_status = {}
                for dependency_name in service['depends_on']:
                    dependency_status[dependency_name] = self.container_service.get_service_status(dependency_name)
                service_status['dependencies'] = dependency_status
            result[service_name] = service_status
        return result

    def is_exec_service(self, service_name: str) -> bool:
        return 'x-exec-container' in self.compose_file['services'][service_name]

    def get_services_without_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if self.is_exec_service(service_name):
                continue
            if 'depends_on' not in service:
                result.append(service_name)
        return result

    def get_services_with_dependency(self) -> list[str]:
        result = []
        for service_name in self.compose_file['services']:
            service = self.compose_file['services'][service_name]
            if self.is_exec_service(service_name):
                continue
            if 'depends_on' in service:
                result.append(service_name)
        return result

    # pylint: disable=broad-exception-raised
    def check_all_dependents_ready(self, service_name: str) -> bool:
        service = self.compose_file['services'][service_name]
        if self.is_exec_service(service_name):
            raise Exception(
                "trying to check dependencies for a exec container.")
        if 'depends_on' not in service:
            raise Exception("trying to check dependencies service without dependencies.")

        for dependency_name in service['depends_on']:
            if self.container_service.get_service_status(dependency_name) not in \
                    [ServiceStatus.READY, ServiceStatus.EXECUTED_SUCCESSFULLY]:
                return False

        return True

    def get_services_ready_to_start(self) -> list[str] | None:
        result = []
        services_status = self.get_services_status()

        all_started = True
        for service in services_status.values():
            all_started = all_started and (
                    service['status'] == ServiceStatus.READY or
                    service['status'] == ServiceStatus.EXECUTED_SUCCESSFULLY or
                    service['status'] == ServiceStatus.EXECUTED_ERROR)

        if all_started:
            return None

        for service_name in self.get_services_with_dependency():
            if services_status[service_name]['status'] == ServiceStatus.NOT_STARTED and \
                    self.check_all_dependents_ready(service_name):
                result.append(service_name)

        for service_name in self.get_services_without_dependency():
            if services_status[service_name]['status'] == ServiceStatus.NOT_STARTED:
                result.append(service_name)

        return result

    def start_all_available_services(self, until: str = None) -> bool:

        service_status = self.get_services_status()
        if until is not None and until in service_status and \
                (service_status[until]['status'] == ServiceStatus.READY or
                 service_status[until]['status'] == ServiceStatus.EXECUTED_SUCCESSFULLY or
                 service_status[until]['status'] == ServiceStatus.EXECUTED_ERROR):
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
        presentation(
            Services.transform_status_to_log(
                self.get_services_status()))

    def run_exec_container(self) -> int:
        return self.container_service.run_exec_container()

    def status(self, presentation: Callable[[list[str]], None]):
        presentation(
            Services.transform_status_to_log(
                self.get_services_status()))

    def restart(self, service_name) -> str:
        return self.container_service.restart(service_name)

    def run_one_shot_service(self, one_shot_service_name) -> int:
        return self.container_service.run_one_shot_service(one_shot_service_name)

    def clear(self, services, unless):

        if services:
            for service in services:
                self.container_service.clear(service)
            return

        if unless:
            for service in self.compose_file['services']:
                if service not in unless:
                    self.container_service.clear(service)
            return

        for service in self.compose_file['services']:
            self.container_service.clear(service)

    def clear_all(self):
        return self.container_service.clear_all()


class ContainerService(BaseContainerService):

    def __init__(self, compose_file_path: Path, **kwargs):
        self.docker_client = docker.from_env()
        self.compose_file_path = compose_file_path
        self.compose_file = yaml.safe_load(compose_file_path.read_text())
        self.env_file = kwargs.get('env_file', None)
        self.environment = kwargs.get('environment', {})
        self.compose_file_path_host = kwargs.get('compose_file_path_host', compose_file_path)
        if 'readiness_check' in kwargs:
            self.readiness_check = kwargs.get('readiness_check')
        else:
            self.readiness_check = ComposeReadinessCheck([HttpReadinessCheck(self.compose_file),
                                                          HealthReadinessCheck(self.docker_client, self.compose_file)])

    def __del__(self):
        self.docker_client.close()

    # pylint: disable=broad-exception-raised
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

    # pylint: disable=too-many-return-statements
    def get_service_status(self, service_name: str) -> ServiceStatus:

        try:
            container = self.docker_client.containers.get(service_name)
            if container.status == 'exited':
                if 'x-one-shot' in self.compose_file['services'][service_name]:
                    if container.attrs['State']['ExitCode'] == 0:
                        return ServiceStatus.EXECUTED_SUCCESSFULLY
                    return ServiceStatus.EXECUTED_ERROR
                return ServiceStatus.NOT_STARTED
            if container.status in ['running']:
                self.attach_network(container)
                if self.readiness_check.is_ready(service_name, self._get_container_ip(container)):
                    return ServiceStatus.READY
                return ServiceStatus.NOT_READY
            return ServiceStatus.INVALID
        except NotFound:
            return ServiceStatus.NOT_STARTED

    def get_services_ips(self):
        result = {}
        for service_name in self.compose_file['services']:
            try:
                container = self.docker_client.containers.get(f'{service_name}')
                result[service_name.upper() + '_IP'] = self._get_container_ip(container)
            except NotFound:
                pass
        return result

    def start_service(self, service_name: str) -> None:

        try:
            self.docker_client.containers.get(f'{service_name}_creator')
            return
        except NotFound:
            env = {**dict(self.environment), **dict(self.get_services_ips())}
            env['ARGS'] = self.environment_to_docker_env(self.get_services_ips())
            if 'EXTRA_ARGS' in env:
                env['ARGS'] += env['ARGS'] + ' ' + env['EXTRA_ARGS']
            env_file_cli = ''
            volumes = {
                str(self.compose_file_path_host.absolute()): {
                    'bind': '/opt/docker-compose.yml',
                    'mode': 'ro'
                },
                '/var/run/docker.sock': {
                    'bind': '/var/run/docker.sock'
                }
            }
            if self.env_file:
                volumes[self.env_file] = {
                    'bind': '/opt/env',
                    'mode': 'ro'
                }
                env_file_cli = '--env-file=/opt/env'
            self.docker_client.containers.run(
                'docker:23.0.1-cli-alpine3.17',
                f'compose -f /opt/docker-compose.yml {env_file_cli} up {service_name}',
                name=f'{service_name}_creator',
                volumes=volumes,
                # remove=True,
                environment=self.environment,
                detach=True
            )

    def restart(self, service_name: str) -> (None | str):
        try:
            container = self.docker_client.containers.get(service_name)
            container.stop()
            container.remove(force=True)
            self.start_service(service_name)
            return None
        except NotFound:
            return f'serice {service_name} not found!'

    def _get_exec_container_name(self) -> str | None:
        for service_name in self.compose_file['services']:
            if 'x-exec-container' in self.compose_file['services'][service_name]:
                return service_name
        return None

    def environment_to_docker_env(self, env: dict):
        result = ''
        for env_key in env:
            result += f'{env_key}={env[env_key]} '

        return result

    def run_exec_container(self) -> int:
        try:
            container = self.docker_client.containers.get(self._get_exec_container_name())
            container.stop()
            container.remove()
        except NotFound:
            pass
        env = {**dict(self.environment), **dict(self.get_services_ips())}
        env['ARGS'] = self.environment_to_docker_env(self.get_services_ips())
        if 'EXTRA_ARGS' in env:
            env['ARGS'] += env['ARGS'] + ' ' + env['EXTRA_ARGS']
        env_file_cli = ''
        volumes = {
            str(self.compose_file_path_host.absolute()): {
                'bind': '/opt/docker-compose.yml',
                'mode': 'ro'
            },
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock'
            }
        }
        if self.env_file:
            volumes[self.env_file] = {
                'bind': '/opt/env',
                'mode': 'ro'
            }
            env_file_cli = '--env-file=/opt/env'
        self.docker_client.containers.run(
            'docker:23.0.1-cli-alpine3.17',
            f'compose -f /opt/docker-compose.yml {env_file_cli} up -d {self._get_exec_container_name()}',
            volumes=volumes,
            environment=env
        )
        container = self.docker_client.containers.get(self._get_exec_container_name())
        logs = container.logs(stream=True)
        for log in logs:
            print(log.decode('utf-8'), end='')
        container.reload()
        return container.attrs['State']['ExitCode']

    def _stop_service(self, service_name: str) -> None:
        try:
            container = self.docker_client.containers.get(service_name)
            container.stop()
        except NotFound:
            pass

    def run_one_shot_service(self, one_shot_service_name) -> int:
        try:
            container = self.docker_client.containers.get(one_shot_service_name)
            if container.status == 'exited':
                return container.attrs['State']['ExitCode']
            raise Exception(f'container for service {one_shot_service_name} is in invalid state '
                            f'${container.attrs["State"]["ExitCode"]}')
        except NotFound:
            pass
        env = {**dict(self.environment), **dict(self.get_services_ips())}
        env['ARGS'] = self.environment_to_docker_env(self.get_services_ips())
        if 'EXTRA_ARGS' in env:
            env['ARGS'] += env['ARGS'] + ' ' + env['EXTRA_ARGS']
        env_file_cli = ''
        volumes = {
            str(self.compose_file_path_host.absolute()): {
                'bind': '/opt/docker-compose.yml',
                'mode': 'ro'
            },
            '/var/run/docker.sock': {
                'bind': '/var/run/docker.sock'
            }
        }
        if self.env_file:
            volumes[self.env_file] = {
                'bind': '/opt/env',
                'mode': 'ro'
            }
            env_file_cli = '--env-file=/opt/env'
        self.docker_client.containers.run(
            'docker:23.0.1-cli-alpine3.17',
            f'compose -f /opt/docker-compose.yml {env_file_cli} up -d {self._get_exec_container_name()}',
            volumes=volumes,
            environment=env
        )
        print('   ************** logs ***************   ')
        logs = container.logs(stream=True)
        for log in logs:
            print(log)
        print('   *****************************   ')
        return self.docker_client.containers.get(one_shot_service_name).attrs['State']['ExitCode']

    def clear(self, service_name):
        print(f'removing service {service_name}')
        try:
            container = self.docker_client.containers.get(service_name)
            container.stop()
            container.reload()
            if container.status != 'removing':
                container.remove()
        except NotFound:
            pass
        try:
            container = self.docker_client.containers.get(f'{service_name}_creator')
            container.stop()
            container.reload()
            if container.status != 'removing':
                container.remove()
        except NotFound:
            pass

    def clear_all(self):
        for service_name in self.compose_file['services']:
            self.clear(service_name)

    def attach_network(self, container):
        if exists("/.dockerenv"):
            current_container = self.docker_client.containers.get(os.uname().nodename)
            if 'Networks' in container.attrs['NetworkSettings'] and len(
                    container.attrs['NetworkSettings']['Networks'].keys()) == 1:
                network_name = list(container.attrs['NetworkSettings']['Networks'].keys())[0]
                if network_name not in list(current_container.attrs['NetworkSettings']['Networks']):
                    network = self.docker_client.networks.get(network_name)
                    network.connect(current_container)


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
                actual_json_body = json.loads(response.read())
                diff = deepdiff.DeepDiff(config['json-body'], actual_json_body)
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


class HealthReadinessCheck(BaseReadinessCheck):

    def __init__(self, docker_client, compose_file):
        self.docker_client = docker_client
        self.compose_file = compose_file
        self.api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        if 'x-container-readiness-check' not in self.compose_file['services'][service_name]:
            return True
        info = self.api_client.inspect_container(service_name)
        if 'Health' in info['State']:
            return info['State']['Health']['Status'] == 'healthy'
        return True


class HttpReadinessCheck(BaseReadinessCheck):

    def __init__(self, compose_file: dict, check_function=check):
        self._not_ready_cause = None
        self.compose_file = compose_file
        self.check_function = check_function

    def is_ready(self, service_name: str, service_ip: str) -> bool:
        if 'x-http-readiness-checks' not in self.compose_file['services'][service_name]:
            return True

        all_true = True
        for config in self.compose_file['services'][service_name]['x-http-readiness-checks']:
            config['service-ip'] = service_ip
            all_true = all_true and self.check_function(config)[0]

        return all_true


class TestContainer:

    # pylint: disable=too-many-arguments
    def __init__(self, compose_file_path: str, environment: dict, env_file: str, silent: bool,
                 print_function: Callable[[str], None]):

        path = Path(compose_file_path)
        self.env_file = env_file
        self.services = Services(path, ContainerService(path, environment=environment, env_file=env_file))
        self.print_function = print_function
        self.last_lines_showed = 0
        self.max_line_size = 0
        self.silent = silent

    def _print(self, line: str):
        if not self.silent:
            self.print_function(line)

    def _present_status(self, lines_to_show: list[str]):
        if self.last_lines_showed > 0:
            self._print("\033[F" * (self.last_lines_showed + 1))
        for line in lines_to_show:
            if len(line) > self.max_line_size:
                self.max_line_size = len(line)
            self._print(line + " " * (self.max_line_size - len(line)))
        self.last_lines_showed = len(lines_to_show)

    def start(self, verification_step_millis: int, presentation_step_millis: int,
              run_exec_container: bool, until: str = None):
        self.services.start(verification_step_millis, presentation_step_millis, self._present_status, until)

        if run_exec_container:
            self.run_exec_container()

    def status(self):
        self.services.status(self._present_status)

    def restart(self, service_name: str):
        message = self.services.restart(service_name)
        if message:
            self._print(message)
            sys.exit(1)

    def run(self, one_shot_service_name: str):
        message = self.services.run_one_shot_service(one_shot_service_name)
        if message:
            self._print(message)
            sys.exit(1)

    def run_exec_container(self):
        exit_code = self.services.run_exec_container()
        self._print(f'exec-container exit code ({exit_code})')
        sys.exit(exit_code)

    def run_one_shot_service(self, one_shot_service_name):
        exit_code = self.services.run_one_shot_service(one_shot_service_name)
        self._print(f'one-shot-exec exit code ({exit_code})')
        sys.exit(exit_code)

    def clear(self, services, unless):
        self.services.clear(services, unless)

    def clear_all(self):
        self.services.clear_all()
