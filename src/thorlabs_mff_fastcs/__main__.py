from pathlib import Path

import typer
from fastcs import FastCS
from fastcs.connections import SerialConnectionSettings

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


def get_controller(port: str, baud: int) -> ThorlabsMFF:
    serial_settings = SerialConnectionSettings(port=port, baud=baud)
    settings = ThorlabsMFFSettings(serial_settings)
    cont = ThorlabsMFF(settings)
    return cont


@app.callback()
def main(
    version: bool | None = typer.Option(
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
    pv_prefix: str = typer.Argument(..., help="IOC PV prefix"),
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
    from fastcs.backends import EpicsGUIOptions, EpicsIOCOptions, EpicsOptions

    options = EpicsOptions(
        ioc=EpicsIOCOptions(pv_prefix=pv_prefix),
        gui=EpicsGUIOptions(output_path / "index.bob"),
    )

    fast_cs = FastCS(get_controller(port, baud), options)
    fast_cs.create_gui()
    fast_cs.run()


@app.command()
def dsr(
    dev_name: str = typer.Argument(
        ..., help="Name of the device instance .e.g my/device/name"
    ),
    dsr_name: str = typer.Argument(
        ..., help="Name of the device server instance e.g. my_server-instance"
    ),
    port: str = typer.Argument(..., help="Serial port to open such as /dev/ttyUSB0"),
    baud: int = typer.Option(115200, help="Baud rate"),
):
    """
    Start up the service
    """

    from fastcs.backends import TangoDSROptions, TangoOptions

    controller = get_controller(port, baud)
    device_options = TangoOptions(
        TangoDSROptions(
            dev_class=controller.__class__.__name__,
            debug=False,
            dev_name=dev_name,
            dsr_instance=dsr_name,
        )
    )

    fast_cs = FastCS(controller, device_options)
    fast_cs.run()


# test with: python -m thorlabs_mff_fastcs
if __name__ == "__main__":
    app()
