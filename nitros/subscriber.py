"""Subscriber module for NitROS - User-facing Subscriber class."""

import asyncio
import collections
import threading
from typing import Callable, Dict, Optional

from .compression import decompress
from .connection import ConnectionManager
from .discovery import DiscoveryService
from .logger import _log
from .serializer import deserialize

import nitros.logger as _logger


class Subscriber:
    """Subscriber for receiving messages from publishers on a topic."""

    def __init__(self, topic: str, callback: Callable, log: bool = False):
        """
        Initialize subscriber.

        Args:
            topic: Topic name to subscribe to
            callback: Function to call with received messages
            log: Enable print-based logging
        """
        _logger._enabled = _logger._enabled or log

        self.topic = topic
        self.callback = callback

        # Event loop for asyncio
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

        # Connection managers (one per discovered publisher)
        self._connections: Dict[str, ConnectionManager] = {}
        self._connections_lock = threading.Lock()

        # Discovery service
        self.discovery: Optional[DiscoveryService] = None

        self._running = False

        # Callback processing: latest-frame-only queue + dedicated thread
        self._msg_deque = collections.deque(maxlen=1)
        self._msg_event = threading.Event()
        self._callback_thread: Optional[threading.Thread] = None

        # Start everything
        self._start()

    def _start(self):
        """Start subscriber components."""
        self._running = True

        # Start callback processing thread
        self._callback_thread = threading.Thread(target=self._callback_worker, daemon=True)
        self._callback_thread.start()

        # Start event loop in background thread
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            pass

        # Start discovery
        try:
            self.discovery = DiscoveryService()
            self.discovery.browse_services(
                self.topic, self._on_publisher_found, self._on_publisher_removed
            )
        except ImportError:
            _log("zeroconf not available, discovery disabled")

        _log(f"Subscriber started for topic '{self.topic}'")

    def _run_event_loop(self):
        """Run asyncio event loop in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _on_publisher_found(self, host: str, port: int):
        """Callback when a publisher is discovered."""
        conn_id = f"{host}:{port}"

        with self._connections_lock:
            if conn_id in self._connections:
                return  # Already connected

            # Create connection manager
            conn = ConnectionManager(host, port, self._on_message)
            self._connections[conn_id] = conn

        # Start connection in event loop
        asyncio.run_coroutine_threadsafe(conn.start(), self._loop)

        _log(f"Connecting to publisher at {host}:{port}")

    def _on_publisher_removed(self, host: str, port: int):
        """Callback when a publisher disappears."""
        conn_id = f"{host}:{port}"

        with self._connections_lock:
            conn = self._connections.pop(conn_id, None)

        if conn and self._loop:
            asyncio.run_coroutine_threadsafe(conn.stop(), self._loop)
            _log(f"Publisher removed at {host}:{port}")

    def _on_message(self, payload: bytes):
        """Handle received message - just enqueue, never blocks the receive loop."""
        if payload:
            self._msg_deque.append(payload)
            self._msg_event.set()

    def _callback_worker(self):
        """Dedicated thread: deserialize + call user callback. Drops stale frames."""
        while self._running:
            self._msg_event.wait(timeout=0.1)
            self._msg_event.clear()

            # Grab latest payload (deque maxlen=1 auto-drops old ones)
            try:
                payload = self._msg_deque.pop()
            except IndexError:
                continue

            try:
                flags = payload[0]
                data = payload[1:]
                compression_mode = flags & 0x03

                if compression_mode == 0:
                    msg = deserialize(data)
                elif compression_mode == 1:
                    msg = decompress(data, "image")
                elif compression_mode == 2:
                    msg = decompress(data, "pointcloud")
                else:
                    _log(f"Unknown compression mode: {compression_mode}")
                    continue

                self.callback(msg)
            except Exception as e:
                _log(f"Failed to process message: {e}")

    def close(self):
        """Close subscriber and cleanup resources."""
        if not self._running:
            return
        self._running = False

        # Wake up and stop callback worker
        self._msg_event.set()
        if self._callback_thread:
            self._callback_thread.join(timeout=1.0)

        # Stop all connections
        if self._loop:
            for conn in self._connections.values():
                future = asyncio.run_coroutine_threadsafe(conn.stop(), self._loop)
                try:
                    future.result(timeout=1.0)
                except:
                    pass

        self._connections.clear()

        # Close discovery
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

        _log(f"Subscriber closed for topic '{self.topic}'")

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.close()
        except:
            pass
