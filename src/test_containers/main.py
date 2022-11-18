import click
from test_containers_impl import TestContainer


@click.group()
def cli():
    pass


def print():
    cli.echo()

@click.command(name="show-status")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
def show_status(docker_compose_file_path):
    """show services status and dependencies"""
    # TestContainer(docker_compose_file_path,click.echo).show_status()
    print('show-status')


@click.command(name="start")
@click.option('--file', '-f', metavar='<DOCKER_COMPOSE_FILE>', required=True,
              type=click.types.Path(file_okay=True, dir_okay=False), help="docker compose file")
@click.option('--until', '-u', metavar='<SERVICE_NAME>', help="stop starting services when <SERVICE_NAME> is started")
def start(file, until):
    """start services and run exec container"""
    print('start')


cli.add_command(show_status)
cli.add_command(start)

if __name__ == '__main__':
    cli()
