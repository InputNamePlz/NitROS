"""Connection manager for NitROS - Reconnection logic with exponential backoff."""

import asyncio
from typing import Callable, Optional

from .logger import _log
from .transport import TCPClient


class ConnectionManager:
    """Manages TCP client connections with automatic reconnection."""

    def __init__(self, host: str, port: int, on_message: Callable[[bytes], None]):
        """
        Initialize connection manager.

        Args:
            host: Server host
            port: Server port
            on_message: Callback for received messages
        """
        self.host = host
        self.port = port
        self.on_message = on_message

        self.client: Optional[TCPClient] = None
        self._running = False
        self._connect_task: Optional[asyncio.Task] = None

        # Exponential backoff parameters
        self.min_backoff = 1.0  # seconds
        self.max_backoff = 32.0  # seconds
        self.current_backoff = self.min_backoff

    async def start(self):
        """Start connection with automatic reconnection."""
        self._running = True
        self._connect_task = asyncio.create_task(self._connect_loop())

    async def _connect_loop(self):
        """Connection loop with exponential backoff."""
        while self._running:
            try:
                # Create new client
                self.client = TCPClient(self.host, self.port)
                self.client.on_message(self.on_message)

                # Attempt connection
                await self.client.connect()

                # Reset backoff on successful connection
                self.current_backoff = self.min_backoff

                # Wait for disconnection
                while self._running and self.client._running:
                    await asyncio.sleep(0.1)

                # Connection lost
                if self._running:
                    _log(f"Connection to {self.host}:{self.port} lost, reconnecting...")

            except Exception:
                pass

            # Exponential backoff before retry
            if self._running:
                await asyncio.sleep(self.current_backoff)

                # Increase backoff
                self.current_backoff = min(self.current_backoff * 2, self.max_backoff)

    async def stop(self):
        """Stop the connection manager."""
        self._running = False

        if self.client:
            await self.client.stop()

        if self._connect_task:
            self._connect_task.cancel()
            try:
                await self._connect_task
            except asyncio.CancelledError:
                pass

        _log(f"Connection manager stopped for {self.host}:{self.port}")
