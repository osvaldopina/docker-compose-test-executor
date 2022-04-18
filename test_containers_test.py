from asyncio import current_task
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import docker
import unittest
import os

from test_containers import \
    BaseContainerCreator,  \
    BaseContainer,  \
    ContainersStarter, \
    BaseTestContainers, \
    Context, \
    DockerTestContainers, \
    HttpReadinessCheck, \
    SimpleTemplateEngine


def insideContainer() -> bool:
    return os.path.exists("/.dockerenv")


class MockBaseContainer(BaseContainer):

    def __init__(self, maxWaitTimeInSeconds: int, name: str,
                 dependent: list['MockBaseContainer']):
        super().__init__(maxWaitTimeInSeconds, dependent, [])
        self.name = name
        self.ready = False
        self.started = False

    def getName(self) -> str:
        return self.name

    def isReady(self):
        return self.ready

    def isStarted(self):
        return self.started

    def start(self):
        BaseContainer.start(self)
        self.started = True


class MockContainerCreator(BaseContainerCreator):

    def __init__(self, maxWaitTimeInSeconds):
        self.maxWaitTimeInSeconds = maxWaitTimeInSeconds

    def createContainer(self, context: Context,
                        containerConfig: dict) -> MockBaseContainer:
        return MockBaseContainer(
            self.maxWaitTimeInSeconds, containerConfig['name'], [])


class TestContainerStarter(unittest.TestCase):

    def testCurrentState(self):
        self.maxDiff = None
        root = MockBaseContainer(10, 'a', [
            MockBaseContainer(10, 'b', [
                MockBaseContainer(10, 'e', []),
                MockBaseContainer(10, 'f', [])
            ]),
            MockBaseContainer(10, 'c', [
                MockBaseContainer(10, 'g', [])
            ]),
            MockBaseContainer(10, 'd', [])
        ])

        containerSarter = ContainersStarter([root])

        state = containerSarter.currentState()

        self.assertDictEqual({
            'a': {'started': False, 'ready': False,
                  'b': {'started': False, 'ready': False,
                        'e': {'started': False, 'ready': False},
                        'f': {'started': False, 'ready': False},
                        },
                  'c': {'started': False, 'ready': False,
                        'g': {'started': False, 'ready': False}
                        },
                  'd': {'started': False, 'ready': False}
                  }}, state)

    def testSingleContainerStateChange(self):

        root = MockBaseContainer(10, 'root', [])
        containerStarter = ContainersStarter([root])

        self.assertDictEqual(containerStarter.currentState(),
                             {'root': {'started': False, 'ready': False}})

        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'root': {'started': True, 'ready': False}})

        root.ready = True
        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'root': {'started': True, 'ready': True}})

    def testContainerWithDependentStateChange(self):

        child1 = MockBaseContainer(10, 'child1', [])
        child2 = MockBaseContainer(10, 'child2', [])
        parent = MockBaseContainer(10, 'parent', [child1, child2])
        containerStarter = ContainersStarter([parent])

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': False, 'ready': False,
                                         'child1': {'started': False, 'ready': False},
                                         'child2': {'started': False, 'ready': False}
                                         }
                              })

        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': False,
                                         'child1': {'started': False, 'ready': False},
                                         'child2': {'started': False, 'ready': False}
                                         }
                              })

        parent.ready = True
        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': True,
                                         'child1': {'started': False, 'ready': False},
                                         'child2': {'started': False, 'ready': False}
                                         }
                              })

        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': True,
                                         'child1': {'started': True, 'ready': False},
                                         'child2': {'started': True, 'ready': False}
                                         }
                              })

        child1.ready = True
        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': True,
                                         'child1': {'started': True, 'ready': True},
                                         'child2': {'started': True, 'ready': False}
                                         }
                              })

        child2.ready = True
        containerStarter.upadateContainersState()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': True,
                                         'child1': {'started': True, 'ready': True},
                                         'child2': {'started': True, 'ready': True}
                                         }
                              })

    def testContainerWithDependentStart(self):

        child1 = MockBaseContainer(10, 'child1', [])
        child1.ready = True
        child2 = MockBaseContainer(10, 'child2', [])
        child2.ready = True
        parent = MockBaseContainer(10, 'parent', [child1, child2])
        parent.ready = True
        containerStarter = ContainersStarter([parent])

        containerStarter.start()

        self.assertDictEqual(containerStarter.currentState(),
                             {'parent': {'started': True, 'ready': True,
                                         'child1': {'started': True, 'ready': True},
                                         'child2': {'started': True, 'ready': True}
                                         }
                              })

    def testReadinessExpiration(self):
        root = MockBaseContainer(1, 'root', [])
        containerStarter = ContainersStarter([root])

        containerStarter.upadateContainersState()
        time.sleep(3)
        self.assertFalse(containerStarter.upadateContainersState())


class BaseTestContainersTest(unittest.TestCase):

    def testCreateContainers(self):
        self.maxDiff = None
        containersConfig = [
            {'name': 'a'},
            {'name': 'd', 'parent': 'a'},
            {'name': 'e', 'parent': 'a'},
            {'name': 'b'},
            {'name': 'f', 'parent': 'b'},
            {'name': 'c'},
        ]
        testContainerStarter = BaseTestContainers(
            MockContainerCreator(10), containersConfig)

        testContainerStarter.loadConfigurations()

        currentState = testContainerStarter._getCurrentState()
        self.assertDictEqual({
            'a': {'started': False, 'ready': False,
                  'd': {'started': False, 'ready': False},
                  'e': {'started': False, 'ready': False}},
            'b': {'started': False, 'ready': False,
                  'f': {'started': False, 'ready': False}},
            'c': {'started': False, 'ready': False
                  }}, currentState)


class MockContainerForReadinessTest(BaseContainer):

    def __init__(self):
        super().__init__(10, [], [])

    def getIp(self) -> str:
        return 'localhost'


def startServer():
    global global_httpd

    global_httpd = HTTPServer(
        ('localhost', 8080), HttpRedinessCheckHttpServerRequestHandler)
    global_httpd.serve_forever()


def startServerOtherThread():
    global daemon

    daemon = threading.Thread(name='daemon_server',
                              target=startServer)
    daemon.setDaemon(True)
    daemon.start()
    time.sleep(5)


def stopServer():
    global global_httpd
    global daemon

    global_httpd.shutdown()
    time.sleep(5)

    while daemon.is_alive():
        time.sleep(1)


def addResponse(path: str, status: int, body: str) -> None:
    global global_responses

    try:
        global_responses
    except NameError:
        global_responses = {}

    global_responses[path] = {
        'status': status,
        'body': body
    }


class HttpRedinessCheckHttpServerRequestHandler(BaseHTTPRequestHandler):
    global global_responses

    def do_GET(self):
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
                self.wfile.write(bytes("Not suppoed to be called!", "utf-8"))
        except Exception as e:
            print(str(e))
        pass


class HttpServerForReadinessTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        startServerOtherThread()

    @classmethod
    def tearDownClass(cls):
        stopServer()

    def testIsReady(self):
        addResponse('/ready-1', 200, '{ "body_value" :  "body" }')
        readinessCheck = HttpReadinessCheck(MockContext(), {
            'protocol': 'http',
            'host': 'localhost',
            'headers': {'Authorization': 'Basic 1234'},
            'port': 8080,
            'url': '/ready-1',
            'responseStatus': 200,
            'jsonBody': '{"body_value":"body"}',

        })

        self.assertTrue(
            readinessCheck.isReady(
                MockContainerForReadinessTest()))

    def testNoHttpServer(self):
        readinessCheck = HttpReadinessCheck(MockContext(), {
            'protocol': 'http',
            'host': 'localhost',
            'port': 9000,
            'sslVerification': False,
            'url': '/ready-2'
        })

        self.assertFalse(
            readinessCheck.isReady(
                MockContainerForReadinessTest()))

        if insideContainer():
            self.assertTrue(
                readinessCheck._notReadyCause.__class__.__name__ == 'OSError')
        else:
            self.assertTrue(
                readinessCheck._notReadyCause.__class__.__name__ == 'ConnectionRefusedError')

    def testHttpStatusDiferent(self):
        addResponse('/ready-3', 201, 'does not matter')
        readinessCheck = HttpReadinessCheck(MockContext(), {
            'protocol': 'http',
            'host': 'localhost',
            'port': 8080,
            'responseStatus': 200,
            'url': '/ready-3'
        })

        self.assertFalse(
            readinessCheck.isReady(
                MockContainerForReadinessTest()))
        self.assertEqual('different status', readinessCheck._notReadyCause)

    def testHttpJdonBodyDiferent(self):
        addResponse('/ready-4', 200, '{ "body_value" :  "body" }')
        readinessCheck = HttpReadinessCheck(MockContext(), {
            'protocol': 'http',
            'host': 'localhost',
            'port': 8080,
            'url': '/ready-4',
            'responseStatus': 200,
            'jsonBody': '{"body_value":"different body"}',

        })

        self.assertFalse(
            readinessCheck.isReady(
                MockContainerForReadinessTest()))
        self.assertEqual(
            "different json body: {'values_changed': {\"root['body_value']\": {'new_value': 'body', 'old_value': 'different body'}}}",
            readinessCheck._notReadyCause)


class DockerTestContainersTest(unittest.TestCase):

    def testSubstituteValuesInConfig(self):

        containersConfig = [
            {
                'name': 'service-sub-parent',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8086'
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'host': 'localhost',
                        'port': 80 if insideContainer() else 8086,
                        'host': '{service-sub-parent_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'test-value': '{service-sub-parent_ip}',
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    }
                ],
            }, {
                'name': 'service-sub-child',
                'parent': 'service-sub-parent',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8087'
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    },
                    'environment': [
                        'ENV_SUB_IP={service-sub-parent_ip}',
                        'ENV_SUB_NAME={service-sub-parent_name}',
                    ]
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8087,
                        'host': '{service-sub-child_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    }
                ]
            }
        ]

        dockerTestContainers = DockerTestContainers(containersConfig)

        self.assertTrue(dockerTestContainers.start())

        self.assertTrue(
            dockerTestContainers.rootContainers[0].readinessChecks[0].lastConfigSubstitute['test-value'].startswith('172.'))

        client = docker.from_env()
        containers = client.containers.list()

        containersSub = [
            container for container in containers if container.name == 'service-sub-child']
        self.assertEqual(1, len(containersSub))

        containerSub = containersSub[0]

        result = containerSub.exec_run('sh -c "echo ${ENV_SUB_IP}"')

        self.assertTrue(result.output.decode('utf-8').startswith('172.'))

        result = containerSub.exec_run('sh -c "echo ${ENV_SUB_NAME}"')

        self.assertTrue(result.output.decode(
            'utf-8').startswith('service-sub-parent'))

        dockerTestContainers.stop()

    def _getDockerContainerWithSameName(self, client, name: str):
        containers = [
            container for container in client.containers.list(
                all=True) if container.name == name]
        if len(containers) == 1:
            return containers[0]
        return None

    def testCreateDockerContainerAndStopAlreadyRunning(self):
        client = docker.from_env()

        while (container := self._getDockerContainerWithSameName(client, 'service')):
            if container.status == 'running':
                container.stop()
            elif container.status == 'exited':
                container.remove(v=True)
            time.sleep(1)

        client.containers.run(**{
            'image': 'nginx:latest',
            'detach': True,
            'name': 'service',
            'remove': True,
        })

        time.sleep(10)

        containersConfig = [
            {
                'name': 'service',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'name': 'service',
                    'ports': {
                        '80/tcp': '8085'
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8085,
                        'host': '{service_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    },
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8085,
                        'host': '{service_ip}' if insideContainer() else 'localhost',
                        'url': '/ready2.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 2, "message" : "ready 2 message"}'
                    },
                ]
            }
        ]

        dockerTestContainers = DockerTestContainers(containersConfig)

        self.assertTrue(dockerTestContainers.start())
        actualState = dockerTestContainers._getCurrentState()
        self.assertDictEqual(actualState,
                             {'service': {'started': True, 'ready': True}})

        client = docker.from_env()
        containers = client.containers.list()
        self.assertTrue(
            any(container.name == 'service' for container in containers))

        dockerTestContainers.stop()

        containers = client.containers.list()
        self.assertFalse(
            any(container.name == 'service' for container in containers))

    def testCreateDockerContainerExecContainer(self):
        containersConfig = [
            {
                'name': 'service-a',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8081'
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8081,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    },
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8081,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready2.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 2, "message" : "ready 2 message"}'
                    },
                ]
            },
            {
                'name': 'service-b',
                'parent': 'service-a',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8082',
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8082,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    },
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8082,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready2.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 2, "message" : "ready 2 message"}'
                    },
                ]
            }, {
                'name': 'exec-container',
                'execContainer': True,
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'command': 'sh -c "exit ${{EXEC_CONTAINER_EXIT_CODE}}"',
                    'image': 'busybox:latest',
                    'environment': [
                        'EXEC_CONTAINER_EXIT_CODE=12'
                    ],
                }
            }
        ]

        dockerTestContainers = DockerTestContainers(containersConfig)

        self.assertTrue(dockerTestContainers.start())
        actualState = dockerTestContainers._getCurrentState()

        self.assertDictEqual(actualState,
                             {'service-a': {'started': True, 'ready': True,
                                            'service-b': {'started': True, 'ready': True}}
                              })
        client = docker.from_env()
        containers = client.containers.list(all=True)
        self.assertTrue(
            any(container.name == 'service-a' for container in containers))
        self.assertTrue(
            any(container.name == 'service-b' for container in containers))
        self.assertFalse(
            any(container.name == 'exec-container' for container in containers))

        self.assertEqual(12, dockerTestContainers.runExecContainer())

        dockerTestContainers.stop()
        containers = client.containers.list(all=True)
        self.assertFalse(
            any(container.name == 'service-a' for container in containers))
        self.assertFalse(
            any(container.name == 'service-b' for container in containers))
        self.assertFalse(
            any(container.name == 'exec-container' for container in containers))

    def testCreateDockerContainerExecScript(self):
        containersConfig = [
            {
                'name': 'service-a',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8081'
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8081,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    },
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8081,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready2.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 2, "message" : "ready 2 message"}'
                    },
                ]
            },
            {
                'name': 'service-b',
                'parent': 'service-a',
                'config': {
                    'maxWaitToBeReadyInSeconds': 10,
                    'image': 'nginx:latest',
                    'detach': True,
                    'ports': {
                        '80/tcp': '8082',
                    },
                    'volumes': {
                        '{env_HTTPSERVERVOLUME}' if insideContainer() else os.path.join(os.getcwd(), 'httpservervolume'): {
                            'bind': '/usr/share/nginx/html',
                            'mode': 'rw'
                        }
                    }
                },
                'httpReadinessChecks': [
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8082,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready1.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 1, "message" : "ready 1 message"}'
                    },
                    {
                        'protocol': 'http',
                        'port': 80 if insideContainer() else 8082,
                        'host': '{service-a_ip}' if insideContainer() else 'localhost',
                        'url': '/ready2.json',
                        'responseStatus': 200,
                        'jsonBody': '{ "code" : 2, "message" : "ready 2 message"}'
                    },
                ]
            }, {
                'name': 'test-script',
                'execScript': True,
                'config': {
                    'file': 'execScriptTest',
                    'params': {
                        'a': 1,
                        'b': 2,
                        'c': 3
                    }
                }
            }
        ]

        dockerTestContainers = DockerTestContainers(containersConfig)

        self.assertTrue(dockerTestContainers.start())
        actualState = dockerTestContainers._getCurrentState()

        self.assertDictEqual(actualState,
                             {'service-a': {'started': True, 'ready': True,
                                            'service-b': {'started': True, 'ready': True}}
                              })
        client = docker.from_env()
        containers = client.containers.list(all=True)
        self.assertTrue(
            any(container.name == 'service-a' for container in containers))
        self.assertTrue(
            any(container.name == 'service-b' for container in containers))

        self.assertEqual(6, dockerTestContainers.runExecScript())

        dockerTestContainers.stop()
        containers = client.containers.list(all=True)
        self.assertFalse(
            any(container.name == 'service-a' for container in containers))
        self.assertFalse(
            any(container.name == 'service-b' for container in containers))


class MockContext(Context):

    def getValue(self, containerName: str, variable: str):
        if containerName == 'cont1':
            if variable == 'ip':
                return 'cont1_ip_value'
            elif variable == 'name':
                return 'cont1_name_value'
        return 'dont know'


def getEnvSimulator(env: dict) -> str:
    def getEnv(key: str) -> str:
        return env[key]

    return getEnv


class TestSimpleTamplateEngine(unittest.TestCase):

    def testGetVars(self):
        ctx = Context()
        templateEngine = SimpleTemplateEngine(ctx)

        self.assertListEqual(['var1', 'var2'], templateEngine._getVars(
            'in this template {var1} and {var2} are variables'))

    def testGetTemplateVariables(self):
        ctx = Context()
        templateEngine = SimpleTemplateEngine(ctx)

        self.assertListEqual([['cont1', 'ip'], ['cont2', 'name'], ['env', 'value']], templateEngine._getTemplateVariables(
            'in this template {cont1_ip} and {cont2_name} {env_value} are variables'))

    def testGetTemplateValues(self):
        ctx = MockContext()
        templateEngine = SimpleTemplateEngine(ctx)

        self.assertDictEqual({
            'cont1_ip': 'cont1_ip_value',
            'cont1_name': 'cont1_name_value',
            'cont2_x': 'dont know'
        }, templateEngine._getTemplateValues('in this template {cont1_ip} and {cont1_name} and {cont2_x} are variables'))

    def testSubstitute(self):
        ctx = MockContext()
        templateEngine = SimpleTemplateEngine(ctx)
        templateEngine._getEnv = getEnvSimulator({
            'VAR': 'env-var-value'
        })

        self.assertEqual('in this template cont1_ip_value and cont1_name_value and dont know and env-var-value are variables',
                         templateEngine._substitute('in this template {cont1_ip} and {cont1_name} and {cont2_x} and {env_VAR} are variables'))

    def testReplaceConfig(self):
        ctx = MockContext()
        templateEngine = SimpleTemplateEngine(ctx)
        templateEngine._getEnv = getEnvSimulator({
            'VAR': 'env-var-value'
        })

        config = {
            'prop1': {
                'v1': 10,
                'v2': {
                    'v3': 'template {cont1_ip}',
                    'v4': '${{not a template}}',
                    'jsonBody': '{cont1_ip}'

                },
                'v5': ['other template {cont2_x}', 'not a template either'],
                'v7': ('other template {env_VAR}'),
                '{env_VAR}': 'a key variable'
            },
            'prop2': 'other template {cont1_name}'
        }

        self.assertDictEqual({
            'prop1': {
                'v1': 10,
                'v2': {
                    'v3': 'template cont1_ip_value',
                    'v4': '${not a template}',
                    'jsonBody': '{cont1_ip}'
                },
                'v5': ['other template dont know', 'not a template either'],
                'v7': ('other template env-var-value'),
                'env-var-value': 'a key variable'
            },
            'prop2': 'other template cont1_name_value'
        }, templateEngine.replace(config))


if __name__ == '__main__':
    unittest.main()
