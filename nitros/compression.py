"""Compression module for NitROS - Image (JPEG) and pointcloud (quantization+LZ4) compression."""

from typing import Any

# Optional imports
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


def compress(data: Any, mode: str) -> bytes:
    """
    Compress data based on compression mode.

    Args:
        data: Data to compress (numpy array for image/pointcloud)
        mode: Compression mode ("image" or "pointcloud")

    Returns:
        Compressed bytes
    """
    if mode == "image":
        if not HAS_CV2:
            raise ImportError("opencv-python is required for image compression")

        # JPEG compression with quality 80
        success, encoded = cv2.imencode('.jpg', data, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            raise ValueError("Failed to encode image")
        return encoded.tobytes()

    elif mode == "pointcloud":
        if not HAS_LZ4:
            raise ImportError("lz4 is required for pointcloud compression")
        if not HAS_NUMPY:
            raise ImportError("numpy is required for pointcloud compression")

        # Convert to numpy array if not already
        if not isinstance(data, np.ndarray):
            data = np.array(data)

        # Quantize to 1mm (assuming meters input) and convert to int16
        quantized = (data * 1000).astype(np.int16)

        # Store shape for reconstruction
        shape_bytes = np.array(quantized.shape, dtype=np.int32).tobytes()

        # LZ4 compression
        compressed = lz4.frame.compress(quantized.tobytes())

        # Combine shape + compressed data
        return len(shape_bytes).to_bytes(4, 'big') + shape_bytes + compressed

    else:
        raise ValueError(f"Unknown compression mode: {mode}")


def decompress(data: bytes, mode: str) -> Any:
    """
    Decompress data based on compression mode.

    Args:
        data: Compressed bytes
        mode: Compression mode ("image" or "pointcloud")

    Returns:
        Decompressed data (numpy array)
    """
    if mode == "image":
        if not HAS_CV2:
            raise ImportError("opencv-python is required for image decompression")

        # Decode JPEG
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")
        return img

    elif mode == "pointcloud":
        if not HAS_LZ4:
            raise ImportError("lz4 is required for pointcloud decompression")
        if not HAS_NUMPY:
            raise ImportError("numpy is required for pointcloud decompression")

        # Extract shape
        shape_len = int.from_bytes(data[:4], 'big')
        shape_bytes = data[4:4+shape_len]
        shape = np.frombuffer(shape_bytes, dtype=np.int32)

        # Decompress LZ4
        compressed_data = data[4+shape_len:]
        decompressed = lz4.frame.decompress(compressed_data)

        # Reconstruct array
        quantized = np.frombuffer(decompressed, dtype=np.int16).reshape(shape)

        # Dequantize back to meters
        return quantized.astype(np.float32) / 1000.0

    else:
        raise ValueError(f"Unknown compression mode: {mode}")
