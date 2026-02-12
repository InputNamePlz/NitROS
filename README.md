# NitROS - Communication made insanely easy

**Nitro + ROS** - A simple, fast, and reliable communication library for robotics.

## 🎯 Why NitROS?

### Before (ROS)
1. Create msg file
2. Edit CMakeLists.txt
3. catkin_make
4. Wait 5 minutes
5. Fix build errors
6. Write code

### After (NitROS)
```bash
pip install nitros
```
Done in 3 lines of code! ✨

## 🚀 Quick Start

### Basic Usage

```python
from nitros import Publisher, Subscriber

# Publisher
pub = Publisher("topic_name")
pub.send({"x": 1, "y": 2.5})

# Subscriber
def callback(msg):
    print(msg)

sub = Subscriber("topic_name", callback)
```

### Camera Streaming Example

**Publisher:**
```python
import cv2
from nitros import Publisher

pub = Publisher("camera", compression="image")
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    pub.send(frame)  # Done!
```

**Subscriber:**
```python
import cv2
from nitros import Subscriber

def show(frame):
    cv2.imshow('Camera', frame)
    cv2.waitKey(1)

sub = Subscriber("camera", show)  # Done!
```

## 📦 Features

- **Zero configuration** - Automatic peer discovery with mDNS
- **Type flexibility** - Send dicts, lists, numpy arrays, PyTorch tensors
- **Built-in compression** - JPEG for images (~10x), quantization+LZ4 for point clouds (~4-5x)
- **Reliable** - TCP-based, guaranteed delivery
- **Simple API** - Just `Publisher` and `Subscriber`
- **Fire and forget** - `send()` never blocks, even without subscribers

## 📚 Data Types

### Send anything

```python
# Dict - just send it
pub.send({"x": 1, "y": 2.5})

# Numpy array - auto-detected
import numpy as np
pub.send(np.array([1, 2, 3]))

# PyTorch tensor - auto-detected
import torch
pub.send(torch.tensor([1, 2]))
```

### Compression for large data

```python
# Images - automatic JPEG compression (~10x reduction)
pub = Publisher("camera", compression="image")
pub.send(camera_frame)  # numpy array

# Point clouds - quantization + LZ4 (~4-5x reduction)
pub = Publisher("lidar", compression="pointcloud")
pub.send(point_cloud)  # numpy array
```

## 🔧 Installation

**Basic (MessagePack only):**
```bash
pip install nitros
```

**Full installation (with all features):**
```bash
pip install nitros[full]
```

**Optional dependencies:**
```bash
pip install nitros[compression]  # Image/pointcloud compression
pip install nitros[discovery]    # mDNS discovery
pip install nitros[numpy]        # Numpy support
```

## 🎨 Design Philosophy

1. **"Just works"** - Minimal configuration, automatic discovery
2. **"Do one thing well"** - Perfect communication only
3. **"Reliable by default"** - TCP first, no packet loss
4. **"Progressive enhancement"** - Start simple, advanced features when needed

## 📊 Comparison

### vs ROS
✅ Learning curve: 5 minutes vs 5 hours
✅ No need to build msg files
✅ Minimal dependencies
✅ High reliability (TCP)
✅ Low resource usage

### vs ZeroMQ
✅ Built-in compression (images, point clouds)
✅ Automatic discovery (no configuration needed)
✅ Automatic type detection
✅ Robotics-specialized

## 🛠️ Requirements

- Python 3.7+
- `msgpack` (required)
- `numpy` (optional, for array support)
- `torch` (optional, for tensor support)
- `opencv-python` (optional, for image compression)
- `lz4` (optional, for pointcloud compression)
- `zeroconf` (optional, for mDNS discovery)

## 📝 License

MIT License

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
