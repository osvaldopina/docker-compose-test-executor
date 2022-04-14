import json
import os
import sys
from test_containers import DockerTestContainers


def start():

    with open('/app/config.json') as file:
        config = file.read()

        with DockerTestContainers(json.loads(config)) as dockerTestContainers:
            if dockerTestContainers.start():
                sys.exit(dockerTestContainers.runExec())
            sys.exit(1)


if __name__ == '__main__':
    start()
