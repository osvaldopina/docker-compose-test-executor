import os
from os.path import abspath
from dc_test_exec.docker_compose_test_executor import TestContainer


# from dc_test_exec import TestContainer


def main():
    path = abspath('/home/osvaldo/projects/app/integration-tests/splunk_pointertrace.yml')
    env_file = abspath('/home/osvaldo/projects/app/integration-tests/otel_grpc.env')
    # extra_env = {
    #     'APPDIR': '/home/osvaldo/projects/app/splunk-app/app',
    #     'TRACESDIR': '/home/osvaldo/projects/app/collector/tests/traces'
    # }
    os.environ['APP_DIR'] = '/home/osvaldo/projects/app/splunk-app/app'
    # os.environ['TRACESDIR'] = '/home/osvaldo/projects/app/collector/tests/traces'
    # os.environ['TRACESDIR_SPLUNK'] = '/home/osvaldo/projects/app/collector/tests/traces_splunk'
    # os.environ['DC_FILE'] = '/home/osvaldo/projects/app/integration-tests/splunk_pointertrace.yml'
    # os.environ['SCRIPT'] = '/home/osvaldo/projects/app/collector/tests/test_collector.py'
    # os.environ['EXTRA_ARGS'] = '/opt/traces_splunk'

    env = {**dict(os.environ), **dict({})}
    test_container = TestContainer(path, env,env_file, False, print)
    # test_container.clear(['jaeger-ui', 'splunk'], [])
    # test_container.run_exec_container()
    # test_container.clear([],['jaeger-ui', 'splunk'])
    # test_container.run_one_shot_service("trace-generator")
    # test_container.restart('trace-generator')
    test_container.start(1000, 1000, False)


if __name__ == '__main__':
    main()
