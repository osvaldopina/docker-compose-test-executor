import os
from pathlib import Path

# from test_containers import TestContainer


def main():
    os.environ['HTTP_SERVER_VOLUME'] = os.path.join(Path(__file__).parent.parent, 'httpservervolume')

    # test_container = TestContainer('../testsConfig/docker_compose_test_exec_script.yml')
    # test_containers.start(1000, 1000)
    # test_container.show_status()


if __name__ == '__main__':
    main()
