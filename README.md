# robot-feedback-rate
Python tool to measure and log how many feedback packets per second a robot controller streams over TCP/IP. Reports average Hz, jitter, and dropped packets.  Topics: robotics python robot-feedback tcp-ip real-time benchmarking industrial-automation data-logging

# Dobot Nova 5 Real-Time Data Logger

A Python-based real-time feedback logger for the **Dobot Nova 5 robotic arm**.

The script connects to the robot through a TCP socket, receives the robot's real-time feedback packets, extracts joint and TCP motion data, and records the data into daily CSV files.

The logger is designed for **robot experiments, motion analysis, trajectory evaluation, repeatability studies, and long-duration data collection**.

---

## Features

* Connects to a Dobot Nova 5 through TCP/IP
* Receives real-time robot feedback packets
* Processes **1440-byte feedback packets**
* Records data at **1 Hz**
* Stores data in daily CSV files
* Automatically creates a new CSV file each day
* Continues writing to an existing daily CSV file after restarting
* Maintains cumulative movement state between program restarts
* Calculates cumulative TCP translational movement
* Calculates cumulative joint rotation
* Records TCP position and orientation
* Records joint positions
* Records joint velocities
* Records TCP linear and rotational velocities
* Uses high-resolution computer timing for logging
* Uses a persistent JSON state file
* Flushes data to disk after each logged sample
* Attempts to protect the persistent state file from corruption using a temporary file

---

# System Overview

The logger follows this basic workflow:

```text
Dobot Nova 5
      │
      │ TCP/IP
      │
      ▼
Port 30004
      │
      ▼
Python Data Logger
      │
      ├── Receive 1440-byte feedback packets
      │
      ├── Decode robot feedback
      │
      ├── Extract joint data
      │
      ├── Extract TCP pose
      │
      ├── Extract velocity data
      │
      ├── Calculate movement
      │
      └── Write one sample / second
              │
              ├── CSV files
              │
              └── JSON state file
```

---

# Requirements

## Hardware

* Dobot Nova 5 robotic arm
* Computer connected to the same network as the robot
* Ethernet/network connection between the computer and robot

## Software

* Python 3.8+
* Standard Python library only

The script does **not require external Python packages**.

It uses:

```text
socket
struct
time
csv
datetime
math
os
json
```

All of these modules are included with Python.

---

# Network Configuration

The robot IP address and feedback port are defined near the beginning of the script:

```python
ROBOT_IP = "192.168.6.3"
FEEDBACK_PORT = 30004
PACKET_SIZE = 1440
```

Change `ROBOT_IP` to match the IP address of your Dobot Nova 5.

For example:

```python
ROBOT_IP = "192.168.1.100"
```

The logger expects the robot's real-time feedback interface to be available on:

```text
TCP port 30004
```

Make sure the computer can communicate with the robot before starting the logger.

You can test basic network connectivity with:

```bash
ping 192.168.6.3
```

On systems where `ping` is not sufficient to verify the TCP service, you can also test the port with an appropriate network utility.

---

# Running the Logger

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

Run the script:

```bash
python robot_logger.py
```

Depending on your system, you may need:

```bash
python3 robot_logger.py
```

If the connection is successful, the program will display something similar to:

```text
==============================================
 DOBOT NOVA 5 - 1 Hz DATA LOGGER
==============================================

Robot IP : 192.168.6.3
Port     : 30004
CSV rate : 1.0 second

Connecting to Dobot Nova 5...
CONNECTED!
Receiving real-time feedback...
Press Ctrl+C to stop.
```

Stop the logger with:

```text
Ctrl+C
```

---

# Output Files

The logger creates a directory:

```text
robot_logs/
```

Daily CSV files are stored inside this directory.

Example:

```text
robot_logs/
├── robot_feedback_2026-10-08.csv
├── robot_feedback_2026-10-09.csv
└── robot_feedback_2026-10-10.csv
```

The date is determined from the computer's local system time.

---

# CSV Data

Each CSV file contains one row per logging sample.

The default logging rate is:

```python
LOG_INTERVAL = 1.0
```

Therefore, the logger attempts to record approximately:

```text
1 sample / second
60 samples / minute
3,600 samples / hour
86,400 samples / day
```

The CSV header contains:

```text
run_id
cycle_id
seg_id
t_s
wall
set_vel
x_mm
y_mm
z_mm
rx_deg
ry_deg
rz_deg
j1_deg
j2_deg
j3_deg
j4_deg
j5_deg
j6_deg
moved_mi_mm
moved_de_deg
vel_j1_deg_s
vel_j2_deg_s
vel_j3_deg_s
vel_j4_deg_s
vel_j5_deg_s
vel_j6_deg_s
vel_tcp1_mm_s
vel_tcp2_mm_s
vel_tcp3_mm_s
vel_tcp4_deg_s
vel_tcp5_deg_s
vel_tcp6_deg_s
```

---

# Recorded Data

## Experiment Metadata

### `run_id`

Identifies the logger run.

The current implementation generates the value from the date:

```python
RUN_ID = "Observer_" + datetime.datetime.now().strftime("%Y%m%d")
```

Example:

```text
Observer_20261008
```

---

### `cycle_id`

Experiment cycle identifier.

The current script initializes and persists this value, but does not automatically increment it.

It can be connected to experiment logic in a future version.

---

### `seg_id`

Segment identifier.

Like `cycle_id`, this is available for experiment-specific segmentation of robot motion.

---

### `set_vel`

User-defined experiment field.

It is currently initialized as:

```python
set_vel = ""
```

You can assign a commanded velocity or other experimental value to this field.

For example:

```python
set_vel = 50
```

---

# TCP Position

The logger records the actual TCP position:

```text
x_mm
y_mm
z_mm
```

Values are recorded in millimeters.

---

# TCP Orientation

The logger records:

```text
rx_deg
ry_deg
rz_deg
```

These represent the TCP orientation values supplied by the robot feedback interface.

The exact interpretation of the orientation representation should be verified against the Dobot Nova 5 feedback/API documentation for the specific robot/software version being used.

---

# Joint Position

The six robot joints are recorded as:

```text
j1_deg
j2_deg
j3_deg
j4_deg
j5_deg
j6_deg
```

The values come directly from the robot's actual joint feedback.

---

# Joint Velocity

Actual joint velocities are recorded as:

```text
vel_j1_deg_s
vel_j2_deg_s
vel_j3_deg_s
vel_j4_deg_s
vel_j5_deg_s
vel_j6_deg_s
```

These represent the joint velocity feedback received from the robot.

---

# TCP Velocity

TCP velocity is divided into translational and rotational components.

### Linear velocity

```text
vel_tcp1_mm_s
vel_tcp2_mm_s
vel_tcp3_mm_s
```

### Rotational velocity

```text
vel_tcp4_deg_s
vel_tcp5_deg_s
vel_tcp6_deg_s
```

The exact axis/reference-frame convention should be interpreted according to the Dobot feedback protocol documentation.

---

# Cumulative Movement

The logger calculates two additional quantities.

## TCP Translational Distance

The script calculates the Euclidean distance between consecutive logged TCP positions:

```python
distance = math.sqrt(
    dx * dx +
    dy * dy +
    dz * dz
)
```

The result is added to:

```text
moved_mi_mm
```

Therefore:

```text
moved_mi_mm
```

represents the cumulative translational distance traveled by the TCP based on the 1 Hz samples.

### Important

This is **not necessarily the exact physical path length of the robot**.

Because the logger records movement at 1 Hz, motion occurring between samples is not directly observed.

For example, if the TCP moves:

```text
0 mm → 100 mm → 0 mm
```

between two logged samples, that movement may not be captured correctly.

For high-accuracy path-length measurement, a higher-frequency logging rate should be used.

---

# Cumulative Joint Rotation

The logger calculates the absolute change of each joint between consecutive logged samples:

```python
joint_rotation = sum(
    abs(
        joints[i] - prev_joints[i]
    )
    for i in range(6)
)
```

The cumulative value is stored in:

```text
moved_de_deg
```

This represents the accumulated absolute angular movement of all six joints.

It is useful as a general indicator of total joint motion.

It should not be interpreted as the angular displacement of any single joint.

---

# Persistent State

The logger maintains:

```text
robot_logger_state.json
```

Example:

```json
{
    "moved_mi_total": 12345.678,
    "moved_de_total": 9876.543,
    "cycle_id": 4,
    "seg_id": 12
}
```

This allows cumulative movement and experiment identifiers to survive a logger restart.

---

# Restart Behavior

An important design decision is that the logger does **not** calculate movement between the final sample of a previous session and the first sample of a new session.

At startup:

```python
prev_xyz = None
prev_joints = None
```

Therefore, the first sample after restarting establishes a new reference point.

This prevents an artificial movement measurement caused by a robot position change that occurred while the logger was not running.

For example:

```text
Session 1:
Robot position = (100, 100, 100)

Logger stopped

Robot moves to:
(500, 500, 500)

Session 2 starts
```

The logger does not incorrectly count:

```text
distance from (100,100,100) → (500,500,500)
```

as movement during Session 2.

---

# Daily File Handling

The logger automatically checks the current date:

```python
date_string = wall_datetime.strftime("%Y-%m-%d")
```

When the date changes, it closes the previous CSV file and opens a new one.

For example:

```text
23:59:59
    ↓
robot_feedback_2026-10-08.csv

00:00:00
    ↓
robot_feedback_2026-10-09.csv
```

If the new file does not exist, the CSV header is automatically created.

If the file already exists, the logger appends to it without writing another header.

---

# Data Safety

The logger explicitly flushes data to disk after each sample:

```python
csv_file.flush()
os.fsync(csv_file.fileno())
```

This reduces the amount of data that may remain only in the operating system's file buffers if the computer unexpectedly loses power or the process terminates.

The persistent state file is also written using a temporary file:

```text
robot_logger_state.json.tmp
```

and then replaced using:

```python
os.replace(...)
```

This reduces the risk of leaving a partially written JSON state file.

---

# Robot Feedback Packet

The logger expects a fixed packet size:

```python
PACKET_SIZE = 1440
```

The script receives the complete packet before decoding it.

The relevant offsets currently used are:

| Data                  | Offset | Format        |
| --------------------- | -----: | ------------- |
| Digital Inputs        |      8 | `uint64`      |
| Digital Outputs       |     16 | `uint64`      |
| Robot Mode            |     24 | `uint64`      |
| Actual Joint Position |    432 | 6 × `float64` |
| Actual Joint Velocity |    480 | 6 × `float64` |
| Actual TCP Pose       |    624 | 6 × `float64` |
| Actual TCP Speed      |    672 | 6 × `float64` |

The script uses little-endian decoding:

```python
"<6d"
```

and:

```python
"<Q"
```

These offsets and data types are **protocol-specific**.

If the Dobot feedback protocol changes, these values may need to be updated.

---

# Timing

The robot may send feedback much faster than the CSV logging rate.

The logger therefore separates:

```text
Robot feedback frequency
```

from:

```text
CSV logging frequency
```

For example:

```text
Robot feedback
      ↓
many packets / second
      ↓
latest feedback stored
      ↓
CSV sample every 1 second
```

At shutdown, the program reports the approximate received feedback frequency:

```text
Feedback packets received : 12345
CSV samples written       : 600
Feedback frequency        : 125.42 Hz
```

The actual frequency depends on the robot feedback interface and network conditions.

---

# Timing Drift Prevention

The logger intentionally does not use:

```python
next_log_time = now + LOG_INTERVAL
```

because repeatedly scheduling from the current time can introduce cumulative timing drift.

Instead, the logger maintains a fixed timing grid:

```python
while next_log_time <= now:
    next_log_time += LOG_INTERVAL
```

This keeps the logging schedule aligned with the original start time.

---

# Project Structure

A recommended repository structure is:

```text
dobot-nova5-data-logger/
│
├── robot_logger.py
├── README.md
├── LICENSE
├── .gitignore
│
└── robot_logs/
    └── .gitkeep
```

The runtime-generated files should generally **not** be committed to GitHub.

---

# Recommended `.gitignore`

Create a file named:

```text
.gitignore
```

with:

```gitignore
# Python cache
__pycache__/
*.py[cod]

# Virtual environments
.venv/
venv/
env/

# Robot logger output
robot_logs/*.csv

# Persistent logger state
robot_logger_state.json
robot_logger_state.json.tmp

# Operating system files
.DS_Store
Thumbs.db

# IDE/editor files
.vscode/
.idea/
```

This prevents potentially large experimental datasets and runtime state files from being accidentally committed to the repository.

---

# Configuration

The most important configuration parameters are at the top of the script:

```python
ROBOT_IP = "192.168.6.3"
FEEDBACK_PORT = 30004
PACKET_SIZE = 1440

LO
```
[robot_feedback_persec.py](https://github.com/user-attachments/files/33209318/robot_feedback_persec.py)



