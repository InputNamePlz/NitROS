"""Simple print-based logger for NitROS."""

# Global flag, set by Publisher/Subscriber
_enabled = False


def _log(msg: str):
    if _enabled:
        print(f"[NitROS] {msg}")
