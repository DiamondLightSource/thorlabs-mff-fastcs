from pathlib import Path
from typing import Optional

import typer
from fastcs.connections.serial_connection import SerialConnectionSettings

from thorlabs_mff_fastcs.controllers import (
    ThorlabsMFF,
    ThorlabsMFFSettings,
)

from . import __version__

__all__ = ["main"]


app = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Print the version and exit",
    ),
):
    pass


@app.command()
def ioc(
    pv_prefix: str = typer.Argument(..., help="Name of the IOC/service to attach to"),
    port: str = typer.Argument(..., help="Serial port to open such as /dev/ttyUSB0"),
    baud: int = typer.Option(115200, help="Baud rate"),
    output_path: Path = typer.Option(  # noqa: B008
        Path.cwd(),  # noqa: B008
        help="folder of local service definition",
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=False,
        readable=True,
        resolve_path=True,
    ),
):
    """
    Start up the service
    """
    from fastcs.backends.epics.backend import EpicsBackend, EpicsGUIOptions

    backend = EpicsBackend(get_controller(port, baud), pv_prefix)
    backend.create_gui(EpicsGUIOptions(output_path / "index.bob"))
    backend.run()


def get_controller(port: str, baud: int) -> ThorlabsMFF:
    serial_settings = SerialConnectionSettings(port=port, baud=baud)
    settings = ThorlabsMFFSettings(serial_settings)
    tcont = ThorlabsMFF(settings)
    return tcont


# test with: python -m thorlabs_mff_fastcs
if __name__ == "__main__":
    app()
