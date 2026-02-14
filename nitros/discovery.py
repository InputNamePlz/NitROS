"""Discovery module for NitROS - mDNS service registration and browsing."""

import socket
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional

from .logger import _log

try:
    from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

SERVICE_TYPE = "_nitros._tcp.local."


class DiscoveryService:
    """mDNS service registration and discovery."""

    def __init__(self):
        """Initialize discovery service."""
        if not HAS_ZEROCONF:
            raise ImportError("zeroconf is required for service discovery")

        self.zeroconf = Zeroconf()
        self.service_info: Optional[ServiceInfo] = None
        self.browser: Optional[ServiceBrowser] = None

    def register_service(self, topic: str, port: int, compression: str = "") -> None:
        """
        Register a publisher service for a topic.

        Args:
            topic: Topic name
            port: TCP port the publisher is listening on
        """
        # Get local IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # Create unique service name from topic + instance ID
        instance_id = uuid.uuid4().hex[:8]
        service_name = f"{topic}-{instance_id}.{SERVICE_TYPE}"

        # Create service info
        self.service_info = ServiceInfo(
            SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={"topic": topic, "compression": compression},
        )

        # Register
        self.zeroconf.register_service(self.service_info)
        _log(f"Registered service for topic '{topic}' on port {port}")

    def browse_services(
        self,
        topic: str,
        on_service_found: Callable[[str, int], None],
        on_service_removed: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        """
        Browse for publishers of a given topic.

        Args:
            topic: Topic name to search for
            on_service_found: Callback(host, port) when a publisher is found
            on_service_removed: Callback(host, port) when a publisher disappears
        """
        class ServiceListener:
            def __init__(self, zc, topic_filter, found_cb, removed_cb):
                self.zc = zc
                self.topic_filter = topic_filter
                self.found_cb = found_cb
                self.removed_cb = removed_cb

            def add_service(self, zc, service_type, name):
                info = zc.get_service_info(service_type, name)
                if info:
                    # Check if topic matches
                    topic_prop = info.properties.get(b"topic", b"").decode("utf-8")
                    if topic_prop == self.topic_filter:
                        # Get host and port
                        host = socket.inet_ntoa(info.addresses[0])
                        port = info.port
                        _log(f"Discovered publisher for topic '{self.topic_filter}' at {host}:{port}")
                        self.found_cb(host, port)

            def remove_service(self, zc, service_type, name):
                if not self.removed_cb:
                    return
                info = zc.get_service_info(service_type, name)
                if info:
                    topic_prop = info.properties.get(b"topic", b"").decode("utf-8")
                    if topic_prop == self.topic_filter:
                        host = socket.inet_ntoa(info.addresses[0])
                        port = info.port
                        _log(f"Publisher removed for topic '{self.topic_filter}' at {host}:{port}")
                        self.removed_cb(host, port)

            def update_service(self, zc, service_type, name):
                pass

        listener = ServiceListener(self.zeroconf, topic, on_service_found, on_service_removed)
        self.browser = ServiceBrowser(self.zeroconf, SERVICE_TYPE, listener)
        _log(f"Browsing for topic '{topic}'")

    def unregister_service(self) -> None:
        """Unregister the service."""
        if self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            _log("Service unregistered")

    def close(self) -> None:
        """Close the discovery service."""
        if self.browser:
            self.browser.cancel()

        # zeroconf.close() handles unregistration internally
        self.zeroconf.close()
        self.service_info = None
        _log("Discovery service closed")


def list_all_services(timeout: float = 2.0) -> Dict[str, List[dict]]:
    """
    Scan the network for all active NitROS topics.

    Args:
        timeout: How long to scan in seconds

    Returns:
        Dict mapping topic names to lists of {host, port, compression}
    """
    if not HAS_ZEROCONF:
        raise ImportError("zeroconf is required for service discovery")

    results: Dict[str, List[dict]] = {}
    lock = threading.Lock()

    zc = Zeroconf()

    class Listener:
        def add_service(self, zc, service_type, name):
            info = zc.get_service_info(service_type, name)
            if not info:
                return
            topic = info.properties.get(b"topic", b"").decode("utf-8")
            compression = info.properties.get(b"compression", b"").decode("utf-8")
            host = socket.inet_ntoa(info.addresses[0])
            port = info.port
            with lock:
                results.setdefault(topic, []).append({
                    "host": host,
                    "port": port,
                    "compression": compression,
                })

        def remove_service(self, zc, service_type, name):
            pass

        def update_service(self, zc, service_type, name):
            pass

    browser = ServiceBrowser(zc, SERVICE_TYPE, Listener())
    time.sleep(timeout)
    browser.cancel()
    zc.close()
    return results
