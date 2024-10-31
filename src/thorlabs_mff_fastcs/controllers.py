from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastcs.attributes import AttrR, AttrW
from fastcs.connections.serial_connection import (
    SerialConnection,
    SerialConnectionSettings,
)
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Int, String
from fastcs.wrappers import command


@dataclass
class ThorlabsMFFSettings:
    serial_settings: SerialConnectionSettings


class ThorlabsAPTProtocol:
    def set_identify(self):
        return b"\x23\x02\x00\x00\x50\x01"

    def get_position(self) -> bytes:
        return b"\x29\x04\x00\x00\x50\x01"

    def read_position(self, response: bytes) -> bool:
        return bool(int(response[8]) - 1)

    def set_position(self, desired: bool) -> bytes:
        if desired:
            return b"\x6a\x04\x00\x02\x50\x01"
        else:
            return b"\x6a\x04\x00\x01\x50\x01"

    def get_info(self) -> bytes:
        return b"\x05\x00\x00\x00\x50\x01"

    def read_model(self, response: bytes) -> str:
        return response[10:18].decode("ascii")

    def read_type(self, response: bytes) -> int:
        return int.from_bytes(response[18:20], byteorder="little")

    def read_serial_no(self, response: bytes) -> int:
        return int.from_bytes(response[6:10], byteorder="little")

    def read_firmware_v(self, response: bytes) -> int:
        return int.from_bytes(response[20:24], byteorder="little")

    def read_hardware_v(self, response: bytes) -> int:
        return int.from_bytes(response[84:86], byteorder="little")


protocol = ThorlabsAPTProtocol()


@dataclass
class ResponseCache:
    _last_update: datetime | None = None
    _response: bytes | None = None
    _update_event: asyncio.Event = asyncio.Event()

    def __post_init__(self) -> None:
        self._update_event.set()

    def _has_expired(self, time_step: float) -> bool:
        if self._last_update is None:
            return True
        delta_t = datetime.now() - self._last_update
        return delta_t.total_seconds() > time_step

    def _update_response(self, response: bytes | None) -> None:
        self._response = response
        self._last_update = datetime.now()

    async def get_response(
        self, expiry_period: float, to_await: Coroutine[Any, Any, bytes | None]
    ):
        # Immediately short circuit if not expired
        if self._has_expired(expiry_period):
            # Wait if an update is in progress
            if self._update_event.is_set():
                self._update_event.clear()  # Lock
                response = await to_await
                self._update_response(response)
                self._update_event.set()  # Free
                return response
            else:
                await self._update_event.wait()

        response = self._response
        to_await.close()  # Solves RuntimeWarning: coroutine not awaited
        return response


info_cache = ResponseCache()


@dataclass
class ThorlabsMFFHandlerW:
    cmd: Callable

    async def put(
        self,
        controller: ThorlabsMFF,
        attr: AttrW,
        value: Any,
    ) -> None:
        try:
            if attr.dtype is bool:
                value = int(value)
            await controller.conn.send_command(
                self.cmd(value),
            )
        except Exception as e:
            print(f"An error occurred: {e}")
            os.kill(os.getpid(), signal.SIGTERM)


@dataclass
class ThorlabsMFFHandlerR:
    cmd: Callable
    response_size: int
    response_handler: Callable
    update_period: float = 0.2
    cache: ResponseCache | None = None

    async def update(
        self,
        controller: ThorlabsMFF,
        attr: AttrR,
    ) -> None:
        try:
            if self.cache is not None:
                response = await self.cache.get_response(
                    self.update_period,
                    controller.conn.send_query(
                        self.cmd(),
                        self.response_size,
                    ),
                )
            else:
                response = await controller.conn.send_query(
                    self.cmd(),
                    self.response_size,
                )

            response = self.response_handler(response)
            if attr.dtype is bool:
                await attr.set(int(response))
            else:
                await attr.set(response)
        except Exception as e:
            print(f"An error occurred: {e}")
            os.kill(os.getpid(), signal.SIGTERM)


class ThorlabsMFF(Controller):
    readback_position = AttrR(
        Bool(znam="Disabled", onam="Enabled"),
        handler=ThorlabsMFFHandlerR(
            protocol.get_position,
            12,
            protocol.read_position,
            update_period=0.2,
        ),
    )
    desired_position = AttrW(
        Bool(znam="Disabled", onam="Enabled"),
        handler=ThorlabsMFFHandlerW(
            protocol.set_position,
        ),
    )
    model = AttrR(
        String(),
        handler=ThorlabsMFFHandlerR(
            protocol.get_info,
            90,
            protocol.read_model,
            update_period=10,
            cache=info_cache,
        ),
        group="Information",
    )
    device_type = AttrR(
        Int(),
        handler=ThorlabsMFFHandlerR(
            protocol.get_info,
            90,
            protocol.read_type,
            update_period=10,
            cache=info_cache,
        ),
        group="Information",
    )
    serial_no = AttrR(
        Int(),
        handler=ThorlabsMFFHandlerR(
            protocol.get_info,
            90,
            protocol.read_serial_no,
            update_period=10,
            cache=info_cache,
        ),
        group="Information",
    )
    firmware_version = AttrR(
        Int(),
        handler=ThorlabsMFFHandlerR(
            protocol.get_info,
            90,
            protocol.read_firmware_v,
            update_period=10,
            cache=info_cache,
        ),
        group="Information",
    )
    hardware_version = AttrR(
        Int(),
        handler=ThorlabsMFFHandlerR(
            protocol.get_info,
            90,
            protocol.read_hardware_v,
            update_period=10,
            cache=info_cache,
        ),
        group="Information",
    )

    def __init__(self, settings: ThorlabsMFFSettings) -> None:
        super().__init__()

        self.suffix = ""
        self._settings = settings
        self.conn = SerialConnection()

    async def connect(self) -> None:
        await self.conn.connect(self._settings.serial_settings)

    async def close(self) -> None:
        await self.conn.close()

    @command()
    async def blink_led(self) -> None:
        await self.conn.send_command(
            protocol.set_identify(),
        )
