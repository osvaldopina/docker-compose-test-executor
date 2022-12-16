from setuptools import setup, find_packages

setup(
    name="dc_test_exec",
    version="0.0.6",
    description="docker compose test executor - tool to execute tests using docker compose",
    author="Osvaldo Pina",
    author_email="osvaldo.pina@gmail.com",
    url="https://github.com/osvaldopina/testcontainers",
    packages=['dc_test_exec'],
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            'dc-test-exec=dc_test_exec.main:cli'
        ]
    },
    dependencies=[
        'deepdiff>=6.2',
        'docker>=6.0',
        'pyyaml>=6.0',
        'click>=8.1.3'
    ]

)
