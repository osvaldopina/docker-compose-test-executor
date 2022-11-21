from setuptools import setup

setup(
    name="dc_test_exec",
    version="1.0.0",
    description="docker compose test executor - tool to execute tests using docker compose",
    author="Osvaldo Pina",
    author_email="osvaldo.pina@gmail.com",
    url="https://github.com/osvaldopina/testcontainers",
    packages=['dc_test_exec'],
    entry_points={
        "console_scripts": [
            'dc-test-exec=dc_test_exec.main:cli'
        ]
    },
    install_requires=[
        'deepdiff',
        'docker',
        'pyyaml',
        'click'
    ]

)
