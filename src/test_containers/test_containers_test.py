import os.path
import threading
import unittest
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import yaml

from test_containers import ServiceStatus, Services, BaseContainerService, ContainerService, check, HttpReadinessCheck


class MockContainerService(BaseContainerService):

    def __init__(self, status: dict):
        self.status = status

    def get_service_status(self, service_name) -> ServiceStatus:
        return self.status[service_name]

    def start_service(self, service_name: str) -> None:
        self.status[service_name] = ServiceStatus.NOT_READY


class ServicesTestCase(unittest.TestCase):

    def test_get_service_status(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
            'service-b': ServiceStatus.NOT_STARTED
        }

        expected = {
            'service-a': {
                'status': ServiceStatus.NOT_STARTED
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.NOT_STARTED
                }
            }
        }

        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual(expected, services.get_services_status())

    def test_get_services_without_dependency(self):
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService({}))

        self.assertEqual(['service-a'], services.get_services_without_dependency())

    def test_get_services_with_dependency(self):
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService({}))

        self.assertEqual(['service-b'], services.get_services_with_dependency())

    def test_all_dependents_ready_false_dependent_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
        }

        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))
        self.assertFalse(services.check_all_dependents_ready('service-b'))

    def test_all_dependents_ready_false_dependent_not_ready(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
        }

        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))
        self.assertFalse(services.check_all_dependents_ready('service-b'))

    def test_all_dependents_ready_true(self):
        status = {
            'service-a': ServiceStatus.READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertTrue(services.check_all_dependents_ready('service-b'))

    def test_get_services_ready_to_start_service_a_not_started_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertEqual(['service-a'], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_not_ready_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertEqual([], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_ready_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertEqual(['service-b'], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_ready_service_b_not_ready(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertEqual([], services.get_services_ready_to_start())

    def test_start_all_available_service_service_a_not_started_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.NOT_STARTED
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.NOT_STARTED
                }
            }
        }, services.get_services_status())

        self.assertTrue(services.start_all_available_services())

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.NOT_READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.NOT_READY
                }
            }
        }, services.get_services_status())

    def test_start_all_available_service_service_a_not_ready_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.NOT_READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.NOT_READY
                }
            }
        }, services.get_services_status())

        self.assertTrue(services.start_all_available_services())

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.NOT_READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.NOT_READY
                }
            }
        }, services.get_services_status())

    def test_start_all_available_service_service_a_ready_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_STARTED,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }, services.get_services_status())

        self.assertTrue(services.start_all_available_services())

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_READY,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }, services.get_services_status())

    def test_start_all_available_service_service_a_ready_service_b_not_ready(self):
        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.NOT_READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_READY,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }, services.get_services_status())

        self.assertTrue(services.start_all_available_services())

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_READY,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }, services.get_services_status())

    def test_start_all_available_service_service_a_ready_service_b_ready(self):
        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertDictEqual({
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.READY,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }, services.get_services_status())

        self.assertFalse(services.start_all_available_services())

    def test_start_all_available_service_service_a_not_ready_until_service_a(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertTrue(services.start_all_available_services('service-a'))

    def test_start_all_available_service_service_a_ready_until_service_a(self):
        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.NOT_READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec_container.yml'), MockContainerService(status))

        self.assertFalse(services.start_all_available_services('service-a'))

    def test_transform_status_to_log(self):
        status = {
            'service-a': {
                'status': ServiceStatus.READY
            },
            'service-b': {
                'status': ServiceStatus.NOT_READY,
                'dependencies': {
                    'service-a': ServiceStatus.READY
                }
            }
        }

        self.assertEqual([
            'service-a : READY',
            'service-b : NOT_READY',
            '    -> service-a : READY'
        ], Services.transform_status_to_log(status))


class ContainerServiceTestCase(unittest.TestCase):

    def test_get_service_status(self):

        container_service = None
        try:
            container_service = ContainerService(
                Path('../testsConfig/docker_compose_test_exec_container.yml'),
                environment={'HTTP_SERVER_VOLUME': os.path.join(Path(__file__).parent.parent, 'httpservervolume')}
            )

            container_service.start_service('service-a')

            time.sleep(10)

            self.assertEqual(ServiceStatus.READY, container_service.get_service_status('service-a'))

        finally:
            if container_service:
                container_service._stop_service('service-a')

    def test_run_exec_container_container(self):

        container_service = ContainerService(Path('../testsConfig/docker_compose_test_exec_container.yml'))

        self.assertEqual(12, container_service.run_exec_container('exec-container'))

    def test_run_exec_container_script(self):

        container_service = ContainerService(
            Path('../testsConfig/docker_compose_test_exec_script.yml'),
            environment={
                'VENV_PATH': os.path.join(Path(__file__).parent.parent, '.venv'),
                'SCRIPT': os.path.join(Path(__file__).parent.parent, 'testsConfig','execScriptTest.py'),
            })

        self.assertEqual(22, container_service.run_exec_container('exec-container'))


class HttpReadinessCheckHttpServerRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        global global_responses
        try:
            if self.path in global_responses:
                response = global_responses[self.path]
                self.send_response(response['status'])
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(response['body'], "utf-8"))
            else:
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(bytes("Not supposed to be called!", "utf-8"))
        except Exception as e:
            print(str(e))
        pass


def start_server():
    global global_httpd

    global_httpd = HTTPServer(
        ('localhost', 8080), HttpReadinessCheckHttpServerRequestHandler)
    global_httpd.serve_forever()


def start_server_other_thread():
    global daemon

    daemon = threading.Thread(name='daemon_server',
                              target=start_server)
    daemon.daemon = True
    daemon.start()
    time.sleep(5)


def stop_server():
    global global_httpd
    global daemon

    global_httpd.shutdown()
    time.sleep(5)

    while daemon.is_alive():
        time.sleep(1)


def add_response(path: str, status: int, body: str) -> None:
    global global_responses

    try:
        global_responses
    except NameError:
        global_responses = {}

    global_responses[path] = {
        'status': status,
        'body': body
    }


def inside_container() -> bool:
    return os.path.exists("/.dockerenv")


class HttpServerForReadinessTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        start_server_other_thread()

    @classmethod
    def tearDownClass(cls):
        stop_server()

    def test_is_ready(self):
        add_response('/ready-1', 200, '{ "body_value" :  "body" }')
        self.assertTrue(check({
            'protocol': 'http',
            'host': 'localhost',
            'headers': {'Authorization': 'Basic 1234'},
            'port': 8080,
            'url': '/ready-1',
            'response-status': 200,
            'json-body': '{"body_value":"body"}',

        }))

    def test_no_http_server(self):
        result, error_cause = check({
            'protocol': 'http',
            'host': 'localhost',
            'port': 9000,
            'ssl-verification': False,
            'url': '/ready-2'
        })

        self.assertFalse(result)

        if inside_container():
            self.assertEqual('OSError', error_cause.__class__.__name__)
        else:
            self.assertEqual('ConnectionRefusedError', error_cause.__class__.__name__)

    def test_http_status_different(self):
        add_response('/ready-3', 201, 'does not matter')

        result, error_cause = check({
            'protocol': 'http',
            'host': 'localhost',
            'port': 8080,
            'response-status': 200,
            'url': '/ready-3'
        })

        self.assertFalse(result)
        self.assertEqual('different status', error_cause)

    def test_http_json_body_different(self):

        add_response('/ready-4', 200, '{ "body_value" :  "body" }')

        result, error_cause = check({
            'protocol': 'http',
            'host': 'localhost',
            'port': 8080,
            'url': '/ready-4',
            'response-status': 200,
            'json-body': '{"body_value":"different body"}',

        })

        self.assertFalse(result)
        self.assertEqual(
            "different json body: {'values_changed': {\"root['body_value']\": "
            "{'new_value': 'body', 'old_value': 'different body'}}}",
            error_cause)


class MockCheck:

    def __init__(self):
        self.configs = []

    def check(self, config):
        self.configs.append(config)
        return True


class HttpReadinessCheckTest(unittest.TestCase):

    def test_is_ready(self):
        mock_check = MockCheck()
        compose_file = yaml.safe_load(Path('../testsConfig/docker_compose_test_exec_container.yml').read_text())
        http_readiness_check = HttpReadinessCheck(compose_file, mock_check.check)

        self.assertTrue(http_readiness_check.is_ready('service-a'))
        self.assertEqual([
            {
                'protocol': 'http',
                'port': 80,
                'host': 'service-a',
                'url': '/ready1.json',
                'response-status': 200,
                'json-body': {'code': 1, 'message': 'ready 1 message'}
            },
            {
                'protocol': 'http',
                'port': 80,
                'host': 'localhost',
                'url': '/ready2.json',
                'response-status': 200,
                'json-body': {'code': 2, 'message': 'ready 2 message'}
            }
        ], mock_check.configs)


if __name__ == '__main__':
    unittest.main()
