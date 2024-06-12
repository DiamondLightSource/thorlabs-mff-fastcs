from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from fastcs.attributes import AttrR, AttrW
from fastcs.connections.serial_connection import (
    SerialConnection,
    SerialConnectionSettings,
)
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Int, String


@dataclass
class ThorlabsMFFSettings:
    serial_settings: SerialConnectionSettings


class ThorlabsAPTProtocol:
    def set_identify(self, action: bool) -> bytes:
        if action:
            return b"\x23\x02\x00\x00\x50\x01"
        else:
            return b""

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
    _response: Any = None
    update_event: asyncio.Event = asyncio.Event()

    def __post_init__(self):
        self.update_event.set()

    def check_expired(self, time_step):
        if self._last_update is None:
            return True
        delta_t = datetime.now() - self._last_update
        return delta_t.total_seconds() > time_step

    def update_response(self, response):
        self._response = response
        self._last_update = datetime.now()

    def get_response(self):
        return self._response


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
        if attr.dtype is bool:
            value = int(value)
        await controller.conn.send_command(
            self.cmd(value),
        )


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
        if self.cache is not None:
            read_cache = False

            # Short circuit if expired
            if self.cache.check_expired(self.update_period):
                # Wait if an update is in progress
                if self.cache.update_event.is_set():
                    self.cache.update_event.clear()
                else:
                    await self.cache.update_event.wait()
                    # Check if updated since
                    if not self.cache.check_expired(self.update_period):
                        read_cache = True
            else:
                read_cache = True

            if read_cache:
                response = self.cache.get_response()
            else:
                response = await controller.conn.send_query(
                    self.cmd(),
                    self.response_size,
                )
                self.cache.update_response(response)
                self.cache.update_event.set()

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
    blink_LED = AttrW(
        Bool(znam="Disabled", onam="Enabled"),
        handler=ThorlabsMFFHandlerW(
            protocol.set_identify,
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
