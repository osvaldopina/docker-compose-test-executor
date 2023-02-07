import os

import click
from os.path import abspath

from click import ClickException
from dc_test_exec.docker_compose_test_executor import TestContainer


@click.group()
def cli():
    pass


def __print(line: str):
    click.echo(str)


# TODO restart, mostrar resultado execucao container
@click.command(name="status")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
def status(file):
    """show services status and dependencies"""
    TestContainer(abspath(file), {}, False, click.echo).status()


@click.command(name="start")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
@click.option('--until', '-u', metavar='<SERVICE_NAME>',
              help="stop starting services when <SERVICE_NAME> is started")
@click.option('--silent', '-s', is_flag=True)
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
def start(file, until, silent, environment):
    """start services without running exec-container"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).start(100, 1000, False, until)


@click.command(name="run")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
@click.option('--silent', '-s', is_flag=True)
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
def run(file, silent, environment):
    """start services and run exec container"""
    env = {**dict(os.environ), **dict(environment)}
    print(f'absoluto:{abspath(file)}')
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


@click.command(name="exec-container")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
@click.option('--silent', '-s', is_flag=True)
def run_exec_container(file, environment, silent):
    """run exec container"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).run_exec_container()


@click.command(name="one-shot")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
@click.option('--environment', '-e', metavar='<ENV_VAR_NAME> <ENV_VAR_VALUE>', type=(str, str), multiple=True,
              help="stop starting services when <SERVICE_NAME> is started")
@click.option('--service', '-s', metavar='<SERVICE_NAME>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--silent', '-s', is_flag=True)
def run_one_shot_service(file, environment, service, silent):
    """run one shot service"""
    env = {**dict(os.environ), **dict(environment)}
    TestContainer(abspath(file), env, silent, click.echo).run_one_shot_service(service)


@click.command(name="clear")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file",
              default=lambda: os.environ.get('DC_FILE', ''), show_default="env variable DC_FILE")
@click.option('--service', '-s', metavar='<SERVICE_NAME>', multiple=True,
              type=str, help="clear only this service")
@click.option('--unless', '-u', metavar='<SERVICE_NAME>', multiple=True,
              type=str, help="clear all but this service")
@click.option('--silent', '-l', is_flag=True)
def clear(file, service, unless, silent):
    """run one shot service"""
    if len(unless) > 0 and len(service) > 0:
        raise ClickException('option service and unless are mutually exclusive')
    TestContainer(abspath(file), {}, silent, click.echo).clear(service, unless)


cli.add_command(status)
cli.add_command(start)
cli.add_command(restart)
cli.add_command(run)
cli.add_command(run_exec_container)
cli.add_command(run_one_shot_service)
cli.add_command(clear)

if __name__ == '__main__':
    cli()
