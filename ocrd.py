from app import app
import click

@click.command('okralact')
@click.version_option()
@click.option('-h', '--host',
              default='0.0.0.0',
              help='Host to run on',
              show_default=True)
@click.option('-p', '--port',
              default=5000,
              help='Port to run on',
              show_default=True)
def okralact_cli(host, port):
    app.run(debug=True, host=host, port=port)

if __name__ == '__main__':
    okralact_cli()
