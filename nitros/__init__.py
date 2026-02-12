"""
NitROS - Nitro + ROS
Communication made insanely easy.

A simple, fast, and reliable communication library for robotics.
"""

from .publisher import Publisher
from .subscriber import Subscriber

__version__ = "0.1.2"
__all__ = ["Publisher", "Subscriber"]
