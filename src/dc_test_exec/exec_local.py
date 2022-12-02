import os
from os.path import abspath
from pathlib import Path

from dc_test_exec.docker_compose_test_executor import TestContainer


# from dc_test_exec import TestContainer


def main():
    path = abspath('../../testsConfig/docker_compose_test_exec_container.yml')
    extra_env = {
        'HTTP_SERVER_VOLUME' : '/home/osvaldo/projects/testcontainers/httpservervolume'
    }
    test_container = TestContainer(path,extra_env, print)
    test_container.start(1000, 1000)
    # test_container.show_status()


if __name__ == '__main__':
    env = {
        'a' : 'a'
    }
    print(dict({**env, **os.environ}))
    # main()
