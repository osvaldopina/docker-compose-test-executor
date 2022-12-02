import os

import click
from os.path import abspath

from dc_test_exec.docker_compose_test_executor import TestContainer


@click.group()
def cli():
    pass


def __print(line: str):
    click.echo(str)


# TODO restart, mostrar resultado execucao container
@click.command(name="status")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
def status(file):
    """show services status and dependencies"""
    TestContainer(abspath(file), False, click.echo).status()


@click.command(name="start")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--until', '-u', metavar='<SERVICE_NAME>',
              help="stop starting services when <SERVICE_NAME> is started")
@click.option('--silent', '-s', is_flag=True)
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
def start(file, until, no_exec_container, silent, environment):
    """start services without running exec-container"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).start(100, 1000, False,  until)


@click.command(name="run")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--silent', '-s', is_flag=True)
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
def run(file, no_exec_container, silent, environment):
    """start services and run exec container"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).start(100, 1000, True)

@click.command(name="restart")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--service', '-s', metavar='<SERVICE_NAME>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
def restart(file, service, environment):
    """restart a specific service"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, False, click.echo).restart(service)


@click.command(name="run-exec-container")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
@click.option('--silent', '-s', is_flag=True)
def run_exec_container(file, environment, silent):
    """restart a specific service"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).run_exec_container()


cli.add_command(status)
cli.add_command(start)
cli.add_command(restart)
cli.add_command(run_exec_container)

if __name__ == '__main__':
    cli()
