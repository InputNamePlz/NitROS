"""Serializer module for NitROS - MessagePack-based data serialization with type detection."""

import msgpack
from typing import Any, Optional

# Optional imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def serialize(data: Any, type_hint: Optional[str] = None) -> bytes:
    """
    Serialize data using MessagePack with automatic type detection.

    Args:
        data: Data to serialize (dict, list, numpy array, torch tensor, or primitives)
        type_hint: Optional type name to include in metadata

    Returns:
        Serialized bytes
    """
    # Numpy array → raw bytes + metadata
    if HAS_NUMPY and isinstance(data, np.ndarray):
        wrapper = {
            "__ndarray": True,
            "dtype": str(data.dtype),
            "shape": list(data.shape),
            "data": data.tobytes(),
        }
        if type_hint:
            wrapper["__type"] = type_hint
        return msgpack.packb(wrapper, use_bin_type=True)

    # Torch tensor → same path via numpy
    if HAS_TORCH and isinstance(data, torch.Tensor):
        arr = data.cpu().numpy()
        wrapper = {
            "__ndarray": True,
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
            "data": arr.tobytes(),
        }
        if type_hint:
            wrapper["__type"] = type_hint
        return msgpack.packb(wrapper, use_bin_type=True)

    # Add type hint if provided
    if type_hint:
        if isinstance(data, dict):
            data = {"__type": type_hint, **data}
        else:
            data = {"__type": type_hint, "data": data}

    return msgpack.packb(data, use_bin_type=True)


def deserialize(data: bytes) -> Any:
    """
    Deserialize MessagePack bytes back to Python objects.

    Args:
        data: Serialized bytes

    Returns:
        Deserialized Python object
    """
    result = msgpack.unpackb(data, raw=False)

    # Reconstruct numpy array if present
    if isinstance(result, dict) and result.get("__ndarray"):
        if HAS_NUMPY:
            arr = np.frombuffer(result["data"], dtype=np.dtype(result["dtype"]))
            return arr.reshape(result["shape"]).copy()
        # Fall back to raw bytes if numpy not available

    # Unwrap non-dict type hint wrapper
    if isinstance(result, dict) and "__type" in result and "data" in result and len(result) == 2:
        return result["data"]

    return result
