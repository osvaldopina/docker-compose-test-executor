import json
import logging
from multiprocessing.connection import Client
import os
from string import Formatter
import time
import http
import ssl
import docker
import deepdiff


def activateLog():
    http.client.HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requestsLog = logging.getLogger("requests.packages.urllib3")
    requestsLog.setLevel(logging.DEBUG)
    requestsLog.propagate = True


class BaseContainer:

    def __init__(self, maxWaitToBeReadyInSeconds, dependent: list['BaseContainer'],
                 readinessChecks: list['BaseReadinessCheck']):
        self.dependent: list[BaseContainer] = dependent
        self.readinessChecks = readinessChecks
        self.startTime = -1
        self.maxWaitToBeReadyInSeconds = maxWaitToBeReadyInSeconds

    def getName(self) -> str:
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')

    def start(self) -> None:
        self.startTime = time.time()

    def stop(self) -> None:
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')

    def isStarted(self) -> bool:
        return self.startTime != -1

    def getStartedTime(self) -> int:
        return self.startTime

    def getMaxWaitToBeReadyInSeconds(self) -> int:
        return self.maxWaitToBeReadyInSeconds

    def isReady(self) -> bool:
        for readinessCheck in self.readinessChecks:
            if not readinessCheck.isReady(self):
                return False
        return True

    def getDependents(self) -> list['BaseContainer']:
        return self.dependent

    def addDependent(self, container: 'BaseContainer') -> None:
        return self.dependent.append(container)

    def getIp(self) -> str:
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')

    def getConfig(self) -> dict:
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')


class Context:
    def __init__(self):
        self.rootContainers = []
        self.simpleTemplateEngine = SimpleTemplateEngine(self)

    def getContainer(self, name: str) -> BaseContainer:
        return self._getContainer(self.rootContainers, name)

    def addRootContainer(self, container: BaseContainer) -> None:
        self.rootContainers.append(container)

    def _getContainer(
            self, containers: list[BaseContainer], name: str) -> BaseContainer:
        for container in containers:
            if container.getName() == name:
                return container
            tmp = self._getContainer(container.getDependents(), name)
            if tmp:
                return tmp
        return None

    def getValue(self, containerName: str, variable: str):
        container = self._getContainer(self.rootContainers, containerName)
        if variable == 'ip':
            return container.getIp()
        if variable == 'name':
            return container.getName()
        return container.getConfig()[variable]

    def replace(self, config: dict) -> dict:
        return self.simpleTemplateEngine.replace(config)


class SimpleTemplateEngine():
    # pylint: disable=too-few-public-methods,no-self-use,no-member

    def __init__(self, context: Context):
        self.context = context
        self._getEnv = os.getenv

    def _getVars(self, template: str):
        return [i[1] for i in Formatter().parse(template) if i[1] is not None]

    def _getTemplateVariables(self, template: str):
        tmp = []
        for var in self._getVars(template):
            tmp.append(var.split("_"))
        return tmp

    def _getTemplateValues(self, template: str):
        result = {}
        for tempVariable in self._getTemplateVariables(template):
            if tempVariable[0] == 'env':
                result[tempVariable[0] + '_' + tempVariable[1]
                       ] = self._getEnv(tempVariable[1])

            else:
                result[tempVariable[0] + '_' + tempVariable[1]
                       ] = self.context.getValue(tempVariable[0], tempVariable[1])

        return result

    def _substitute(self, template: str):
        values = self._getTemplateValues(template)
        return template.format(**values)

    def _replaceValue(self, value):
        if isinstance(value, dict):
            result = {}
            for key, val in value.items():
                subsKey = self._substitute(key)
                if subsKey == 'jsonBody' and isinstance(val, str):
                    result[subsKey] = val
                else:
                    result[subsKey] = self._replaceValue(val)
            return result
        if isinstance(value, str):
            return self._substitute(value)
        if isinstance(value, list):
            tmp = []
            for i in value:
                tmp.append(self._replaceValue(i))
            return tmp
        if isinstance(value, tuple):
            tmp = []
            for i in value:
                tmp.append(self._replaceValue(i))
            return tuple(tmp)
        return value

    def replace(self, config: dict) -> dict:
        return self._replaceValue(config)


class BaseReadinessCheck:
    # pylint: disable=too-few-public-methods

    def isReady(self, container: BaseContainer):
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')


class ContainersStarter:

    def __init__(
            self, containers: list[BaseContainer]):
        self.containers = containers
        self.started = False
        self.currentStartingContainers = []

    def upadateContainersState(self) -> bool:
        if not self.started:
            self.currentStartingContainers = self.containers[:]
            self.started = True
        return self.updateInternalContainerState()

    def updateInternalContainerState(self) -> bool:
        for container in self.currentStartingContainers:
            if not container.isStarted():
                print(f'      starting container {container.getName()}')
                container.start()

        for container in self.currentStartingContainers[:]:
            if container.isReady():
                print(f'        container {container.getName()} is ready')
                self.currentStartingContainers.remove(container)
                for depCont in container.getDependents():
                    self.currentStartingContainers.append(depCont)
            else:
                if int(time.time()) - \
                        container.getStartedTime() > container.getMaxWaitToBeReadyInSeconds():
                    print(
                        f'        container {container.getName()} ' +
                        f'is taking more than {container.getMaxWaitToBeReadyInSeconds()} seconds ' +
                        'to be ready. Aborting!')
                    return False
        return True

    def state(self, container: BaseContainer) -> dict:
        result = {
            'started': container.isStarted(),
            'ready': container.isReady()
        }
        for subContainer in container.getDependents():
            result[subContainer.getName()] = self.state(subContainer)
        return result

    def currentState(self) -> dict:
        result = {}
        for container in self.containers:
            result[container.getName()] = self.state(container)
        return result

    def start(self) -> bool:
        while True:
            if not self.upadateContainersState():
                return False
            if self.started and len(self.currentStartingContainers) == 0:
                break
        return True


class BaseContainerCreator:
    # pylint: disable=too-few-public-methods

    def createContainer(self, context: Context,
                        containerConfig: dict) -> BaseContainer:
        raise NotImplementedError(
            'I\'m not supposed to be called. I\'m abstract')


class BaseTestContainers:
    # pylint: disable=too-many-instance-attributes

    def __init__(self, containerCreator: BaseContainerCreator,
                 containersConfig: list[dict]):
        self.containerCreator = containerCreator
        self.containersConfig = containersConfig
        self.rootContainers = []
        self.execContainer = None
        self.context = Context()
        self.containerStarter = None
        self.execScriptFile = None
        self.execScriptParams = None

    def loadConfigurations(self):
        print("    loading container configurations:")
        for containerConfig in self.containersConfig:
            print(f'      loading {containerConfig["name"]} configuration')
            container = self.containerCreator.createContainer(
                self.context, containerConfig)
            if 'parent' in containerConfig:
                print(
                    f'        this container has {containerConfig["parent"]} as parent container')
                parentContainer = self.context.getContainer(
                    containerConfig['parent'])
                parentContainer.addDependent(container)
            else:
                if 'execContainer' in containerConfig and containerConfig['execContainer']:
                    self.execContainer = container
                elif 'execScript' in containerConfig and containerConfig['execScript']:
                    self.execScriptFile = containerConfig['config']['file']
                    self.execScriptParams = containerConfig['config']['params']
                else:
                    self.rootContainers.append(container)
                self.context.addRootContainer(container)
        self.containerStarter = ContainersStarter(
            self.rootContainers)

    def start(self) -> bool:
        self.loadConfigurations()
        print("    starting containers:")
        if self.containerStarter.start():
            print("    all containers started!")
            return True
        print("    failed to start all containers!")
        return False

    def runExec(self) -> int:
        if not self.execScriptFile is None:
            return self.runExecScript()
        return self.runExecContainer()

    def runExecContainer(self) -> int:
        self.execContainer.start()
        return self.execContainer.getExitStatus()

    def runExecScript(self) -> int:
        externalModule = __import__(self.execScriptFile)
        return externalModule.main(**self.execScriptParams)

    def stop(self) -> None:
        print("    stopping and removing containers:")
        for container in self.rootContainers:
            self._stopContainer(container)
        if self.execContainer:
            self.execContainer.stop()

    def _stopContainer(self, container: BaseContainer):
        for subContainer in container.getDependents():
            self._stopContainer(subContainer)

        container.stop()

    def _getCurrentState(self):
        return self.containerStarter.currentState()


class DockerTestContainers(BaseTestContainers):
    # pylint: disable=too-few-public-methods

    def __init__(
            self, containersConfig: list[dict]):
        super().__init__(
            DockerContainerCreator(),
            containersConfig)

    def __enter__(self):
        return self

    def __exit__(self, exceptionType, exceptionValue, traceback):
        self.stop()


class HttpReadinessCheck(BaseReadinessCheck):
    # pylint: disable=too-few-public-methods,protected-access,broad-except

    def __init__(self, context: Context, config: dict):
        self.context = context
        self.config = config
        self.lastConfigSubstitute = {}
        self._notReadyCause = None

    def isReady(self, container: BaseContainer) -> bool:
        localConfig = self.context.replace(self.config)
        self.lastConfigSubstitute = localConfig
        # activateLog()
        connection = None
        try:
            if self.config['protocol'] == 'https':
                connection = http.client.HTTPSConnection(
                    host=localConfig['host'] if 'host' in localConfig else container.getIp(
                    ),
                    port=localConfig['port'],
                    context=ssl._create_unverified_context())
            else:
                connection = http.client.HTTPConnection(
                    host=localConfig['host'] if 'host' in localConfig else container.getIp(
                    ),
                    port=localConfig['port'])
            connection.request(  #
                method='GET',  #
                url=localConfig['url'],
                headers=localConfig['headers'] if 'headers' in localConfig else {})
            response = connection.getresponse()
            if response.status == localConfig['responseStatus']:
                if 'jsonBody' in localConfig:
                    expectedJsonBody = json.loads(localConfig['jsonBody'])
                    actualJsonBody = json.loads(response.read())
                    diff = deepdiff.DeepDiff(expectedJsonBody, actualJsonBody)
                    if not diff.to_dict():
                        return True
                    self._notReadyCause = f'different json body: {diff.to_dict()}'
                    return False
                return True
            self._notReadyCause = 'different status'
            return False
        except Exception as exc:
            self._notReadyCause = exc
            return False
        finally:
            if connection is not None:
                connection.close()


class BaseDockerClientCreator():
    # pylint: disable=too-few-public-methods

    def createDockerClient(self):
        pass


class DockerContainer(BaseContainer):
    # pylint: disable=too-many-instance-attributes

    def __init__(self, context: Context, config: dict,
                 readinessChecks: list['BaseReadinessCheck']):
        super().__init__(config['config']['maxWaitToBeReadyInSeconds']
                         if 'maxWaitToBeReadyInSeconds' in config['config'] else 60,
                         [], readinessChecks)
        self.context = context
        self.config = config['config']
        self.config.pop('maxWaitToBeReadyInSeconds', None)
        self.name = config['name']
        self.execContainer = config['execContainer'] if 'execContainer' in config else False
        self.ip = ''
        self.client = None
        self.dockerContainer = None
        self.exitStatus = None

    def __del__(self) -> None:
        if self.client is not None:
            self.client.close()

    def getIp(self) -> str:
        if self.ip == '':
            self.dockerContainer.reload()
            self.ip = self.dockerContainer \
                .attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
        return self.ip

    def getConfig(self) -> dict:
        return self.config

    def getName(self) -> str:
        return self.name

    def _getClient(self) -> Client:
        if not self.client:
            self.client = docker.DockerClient(
                base_url='unix://var/run/docker.sock')
        return self.client

    def start(self) -> None:
        self.stop()
        config = self.context.replace(self.config)
        config['name'] = self.name
        if self.execContainer:
            try:
                self._getClient().containers.run(**config)
                self.exitStatus = 0
            except docker.errors.ContainerError as exc:
                self.exitStatus = exc.exit_status
        else:
            config['detach'] = True
            self.dockerContainer = self._getClient().containers.run(**config)
        super().start()

    def getExitStatus(self):
        return self.exitStatus

    def _getDockerContainerWithSameName(self):
        containers = [
            container for container in self._getClient().containers.list(
                all=True) if container.name == self.name]
        if len(containers) == 1:
            return containers[0]
        return None

    def stop(self) -> None:
        print(f'        will try stop container {self.name} ')
        while (container := self._getDockerContainerWithSameName()):
            if container.status in ['running', 'Restarting', 'paused']:
                print(f'          stopping container {self.name} ')
                container.stop()
            elif container.status in ['exited', 'created', 'dead']:
                print(f'          removing container {self.name} ')
                container.remove(v=True)
            time.sleep(1)


class DockerContainerCreator(BaseContainerCreator):
    # pylint: disable=too-few-public-methods

    def createContainer(self, context: Context,
                        containerConfig: dict) -> BaseContainer:
        readinessChecks: list[HttpReadinessCheck] = []
        if 'httpReadinessChecks' in containerConfig:
            for readinessCheckConfig in containerConfig['httpReadinessChecks']:
                readinessChecks.append(
                    HttpReadinessCheck(
                        context, readinessCheckConfig))
        return DockerContainer(context, containerConfig, readinessChecks)
