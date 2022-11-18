from setuptools import setup

setup(
    name="test_containers",
    version="1.0.0",
    description="tool to execute tests using docker compose",
    author="Osvaldo Pina",
    author_email="osvaldo.pina@gmail.com",
    url="https://github.com/osvaldopina/testcontainers",
    packages=['test_containers'],
    entry_points={
        "console_scripts": [
            'test-containers = test_containers.main:cli'
        ]
    }

)
