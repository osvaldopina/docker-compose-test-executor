import click


@click.command()
@click.option('--list-services', help='list state of all compose services')
@click.argument('file', )
def list_services(count, name):
    for x in range(count):
        click.echo(f"Hello {name}!")