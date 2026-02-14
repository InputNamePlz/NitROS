"""Publisher module for NitROS - User-facing Publisher class."""

import asyncio
import queue
import threading
from typing import Any, Optional

from .compression import compress
from .discovery import DiscoveryService
from .logger import _log, _enabled
from .serializer import serialize
from .transport import TCPServer

import nitros.logger as _logger


class Publisher:
    """Publisher for sending messages to subscribers on a topic."""

    def __init__(self, topic: str, compression: Optional[str] = None, log: bool = False):
        """
        Initialize publisher.

        Args:
            topic: Topic name to publish on
            compression: Optional compression mode ("image" or "pointcloud")
            log: Enable print-based logging
        """
        _logger._enabled = _logger._enabled or log

        self.topic = topic
        self.compression = compression

        # Create event loop for asyncio in background thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

        # TCP server
        self.server: Optional[TCPServer] = None
        self.port: Optional[int] = None

        # Discovery service
        self.discovery: Optional[DiscoveryService] = None

        # Send queue (bounded to avoid memory issues)
        self._send_queue: queue.Queue = queue.Queue(maxsize=10)
        self._send_thread: Optional[threading.Thread] = None
        self._running = False

        # Start everything
        self._start()

    def _start(self):
        """Start publisher components."""
        # Start event loop in background thread
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            pass

        # Start TCP server
        future = asyncio.run_coroutine_threadsafe(self._start_server(), self._loop)
        self.port = future.result()

        # Register mDNS service
        try:
            self.discovery = DiscoveryService()
            self.discovery.register_service(self.topic, self.port, self.compression or "")
        except ImportError:
            _log("zeroconf not available, discovery disabled")

        # Start send thread
        self._running = True
        self._send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self._send_thread.start()

        _log(f"Publisher started for topic '{self.topic}' on port {self.port}")

    def _run_event_loop(self):
        """Run asyncio event loop in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _start_server(self) -> int:
        """Start TCP server."""
        self.server = TCPServer(port=0)  # Random available port
        port = await self.server.start()
        return port

    def _send_worker(self):
        """Background worker that processes send queue."""
        while self._running:
            try:
                # Get data from queue with timeout
                data = self._send_queue.get(timeout=0.1)

                # Process and send
                try:
                    # Extract type_hint if present
                    type_hint = None
                    if isinstance(data, tuple) and len(data) == 2 and isinstance(data[1], str):
                        data, type_hint = data

                    # Compress if needed
                    if self.compression:
                        data = compress(data, self.compression)
                        flags = 1 if self.compression == "image" else 2
                        payload = bytes([flags]) + data
                    else:
                        serialized = serialize(data, type_hint=type_hint)
                        payload = bytes([0]) + serialized

                    # Broadcast to all clients (fire-and-forget)
                    asyncio.run_coroutine_threadsafe(
                        self.server.broadcast(payload),
                        self._loop
                    )

                except Exception as e:
                    _log(f"Failed to send message: {e}")

            except queue.Empty:
                continue

    @property
    def subscriber_count(self) -> int:
        """Number of currently connected subscribers."""
        if self.server:
            return len(self.server.clients)
        return 0

    def wait_for_subscribers(self, count: int = 1, timeout: float = 10.0) -> bool:
        """
        Block until at least `count` subscribers are connected.

        Args:
            count: Minimum number of subscribers to wait for
            timeout: Maximum seconds to wait

        Returns:
            True if subscribers connected, False if timed out
        """
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.subscriber_count >= count:
                return True
            time.sleep(0.05)
        return False

    def send(self, data: Any, type_hint: Optional[str] = None):
        """
        Send data to all subscribers (non-blocking).

        Args:
            data: Data to send (dict, list, numpy array, etc.)
            type_hint: Optional type name to include in metadata
        """
        if type_hint:
            data = (data, type_hint)
        try:
            # Try to put on queue without blocking
            self._send_queue.put_nowait(data)
        except queue.Full:
            # Queue full, drop oldest and add new
            try:
                self._send_queue.get_nowait()
                self._send_queue.put_nowait(data)
                _log("Send queue full, dropped oldest message")
            except:
                pass

    def close(self):
        """Close publisher and cleanup resources."""
        if not self._running:
            return
        self._running = False

        # Stop send thread
        if self._send_thread:
            self._send_thread.join(timeout=1.0)

        # Stop TCP server
        if self.server and self._loop:
            future = asyncio.run_coroutine_threadsafe(self.server.stop(), self._loop)
            try:
                future.result(timeout=1.0)
            except:
                pass

        # Unregister discovery
        if self.discovery:
            try:
                self.discovery.close()
            except:
                pass

        # Stop event loop
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread:
            self._loop_thread.join(timeout=1.0)

        _log(f"Publisher closed for topic '{self.topic}'")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.close()
        except:
            pass
