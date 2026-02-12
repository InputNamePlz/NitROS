"""Transport module for NitROS - TCP server and client with asyncio."""

import asyncio
import struct
from typing import Callable, List, Optional

from .logger import _log


class TCPServer:
    """TCP server that accepts connections and broadcasts messages to all clients."""

    def __init__(self, host: str = "0.0.0.0", port: int = 0):
        """
        Initialize TCP server.

        Args:
            host: Host to bind to (default: 0.0.0.0)
            port: Port to bind to (0 = random available port)
        """
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.clients: List[asyncio.StreamWriter] = []
        self._lock = asyncio.Lock()
        self._running = False
        self.HIGH_WATER_MARK = 4 * 1024 * 1024  # 4MB - skip client if buffer exceeds this

    async def start(self) -> int:
        """
        Start the TCP server.

        Returns:
            Actual port number the server is listening on
        """
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        self._running = True

        # Get actual port
        addr = self.server.sockets[0].getsockname()
        self.port = addr[1]

        _log(f"TCP server started on {self.host}:{self.port}")
        return self.port

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a new client connection."""
        addr = writer.get_extra_info('peername')
        _log(f"Client connected: {addr}")

        async with self._lock:
            self.clients.append(writer)

        try:
            # Wait for client disconnect (read returns empty on EOF)
            while self._running:
                data = await reader.read(1024)
                if not data:
                    break
        except Exception:
            pass
        finally:
            async with self._lock:
                if writer in self.clients:
                    self.clients.remove(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def broadcast(self, data: bytes):
        """
        Broadcast message to all connected clients (fire-and-forget).
        Skips clients whose write buffer is full (per-client adaptive FPS).

        Args:
            data: Message payload to send
        """
        if not self.clients:
            return

        # Length-prefixed message: [4 bytes length][payload]
        length = struct.pack('>I', len(data))
        message = length + data

        async with self._lock:
            disconnected = []
            for writer in self.clients:
                try:
                    # Check if transport buffer is backed up
                    transport = writer.transport
                    buf_size = transport.get_write_buffer_size()
                    if buf_size > self.HIGH_WATER_MARK:
                        continue  # skip this client, it can't keep up

                    writer.write(message)  # non-blocking buffer write
                except Exception:
                    disconnected.append(writer)

            for writer in disconnected:
                self.clients.remove(writer)
                try:
                    writer.close()
                except:
                    pass

    async def stop(self):
        """Stop the TCP server and close all connections."""
        self._running = False

        # Close all client connections first (unblocks _handle_client reads)
        async with self._lock:
            for writer in self.clients:
                try:
                    writer.close()
                except:
                    pass
            self.clients.clear()

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        _log("TCP server stopped")


class TCPClient:
    """TCP client that connects to a server and receives messages."""

    def __init__(self, host: str, port: int):
        """
        Initialize TCP client.

        Args:
            host: Server host
            port: Server port
        """
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._callback: Optional[Callable[[bytes], None]] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Connect to the server."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self._running = True
        _log(f"Connected to {self.host}:{self.port}")

        # Start receive loop
        if self._callback:
            self._receive_task = asyncio.create_task(self._receive_loop())

    def on_message(self, callback: Callable[[bytes], None]):
        """
        Register callback for incoming messages.

        Args:
            callback: Function to call with received message bytes
        """
        self._callback = callback

    async def _receive_loop(self):
        """Receive messages from server."""
        try:
            while self._running:
                # Read length prefix (4 bytes)
                length_data = await self.reader.readexactly(4)
                length = struct.unpack('>I', length_data)[0]

                # Read payload
                payload = await self.reader.readexactly(length)

                # Call callback
                if self._callback:
                    try:
                        self._callback(payload)
                    except Exception as e:
                        _log(f"Callback error: {e}")
        except asyncio.IncompleteReadError:
            pass
        except Exception:
            pass
        finally:
            self._running = False

    async def stop(self):
        """Stop the client and close connection."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass

        _log(f"Disconnected from {self.host}:{self.port}")
