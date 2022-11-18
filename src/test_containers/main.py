import click


@click.group()
# @click.option('--file', '-f', type=str, help="compose file")
def cli():
    pass


@click.command(name="show-status")
@click.option('--file', '-f', required=True, type=str, help="compose file")
def show_status(file):
    """show services status and dependencies"""
    print('show-status')


@click.command(name="start")
@click.option('--file', '-f', required=True, type=str, help="compose file")
@click.option('--until')
def start(file):
    """start services and run exec container"""
    print('start')


cli.add_command(show_status)
cli.add_command(start)

if __name__ == '__main__':
    cli()
