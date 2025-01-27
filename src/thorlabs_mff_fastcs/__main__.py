from fastcs import launch

from thorlabs_mff_fastcs.controllers import (
    ThorlabsMFF,
)

from . import __version__

__all__ = ["main"]


def main() -> None:
    launch(ThorlabsMFF, version=__version__)


if __name__ == "__main__":
    main()
