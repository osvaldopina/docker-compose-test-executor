import unittest
from pathlib import Path

from test_containers import ServiceStatus, Services, BaseContainerService


class MockContainerService(BaseContainerService):

    def __init__(self, status: dict):
        self.status = status

    def get_service_status(self, service_name) -> ServiceStatus:
        return self.status[service_name]


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

        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertDictEqual(expected, services.get_services_status())

    def test_get_services_without_dependency(self):
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService({}))

        self.assertEqual(['service-a'], services.get_services_without_dependency())

    def test_get_services_with_dependency(self):
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService({}))

        self.assertEqual(['service-b'], services.get_services_with_dependency())

    def test_all_dependents_ready_false_dependent_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
        }

        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))
        self.assertFalse(services.check_all_dependents_ready('service-b'))

    def test_all_dependents_ready_false_dependent_not_ready(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
        }

        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))
        self.assertFalse(services.check_all_dependents_ready('service-b'))

    def test_all_dependents_ready_true(self):
        status = {
            'service-a': ServiceStatus.READY,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertTrue(services.check_all_dependents_ready('service-b'))

    def test_get_services_ready_to_start_service_a_not_started_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_STARTED,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertEquals(['service-a'], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_not_ready_service_b_not_started(self):
        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertEquals([], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_ready_service_b_not_started(self):

        status = {
            'service-a': ServiceStatus.READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertEquals(['service-b'], services.get_services_ready_to_start())

    def test_get_services_ready_to_start_service_a_ready_service_b_not_ready(self):

        status = {
            'service-a': ServiceStatus.NOT_READY,
            'service-b': ServiceStatus.NOT_STARTED,
        }
        services = Services(Path('../testsConfig/docker_compose_test_exec.yml'), MockContainerService(status))

        self.assertEqual([], services.get_services_ready_to_start())

    def test_start_all_available_service_service_a_not_started_service_b_not_started(self):
        #TODO
        pass

if __name__ == '__main__':
    unittest.main()