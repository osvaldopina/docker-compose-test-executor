import os
from os.path import abspath
from pathlib import Path

from dc_test_exec.docker_compose_test_executor import TestContainer


# from dc_test_exec import TestContainer


def main():
    path = abspath('/home/osvaldo/projects/app/collector/tests/test_collector.yml')
    # extra_env = {
    #     'APPDIR': '/home/osvaldo/projects/app/splunk-app/app',
    #     'TRACESDIR': '/home/osvaldo/projects/app/collector/tests/traces'
    # }
    os.environ['APPDIR'] = '/home/osvaldo/projects/app/splunk-app/app'
    os.environ['TRACESDIR'] ='/home/osvaldo/projects/app/collector/tests/traces'
    os.environ['DC_FILE'] ='/home/osvaldo/projects/app/collector/tests/test_collector.yml'

    env = {**dict(os.environ), **dict({})}
    test_container = TestContainer(path, env, False, print)
    # test_container.status()
    test_container.run_one_shot_service("trace-generator")
    # test_container.restart('trace-generator')
    # test_container.start(1000, 1000, False, None)


if __name__ == '__main__':
    main()
