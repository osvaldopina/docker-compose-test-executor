
import click


@click.group()
def cli():
    pass


@click.command(name="show-status")
def show_status():
    """show services status and dependencies"""
    print('show-status')


@click.command(name="start")
@click.option('--until')
def start():
    """start services and run exec container"""
    print('start')


cli.add_command(show_status)
cli.add_command(start)

if __name__ == '__main__':
    cli()
