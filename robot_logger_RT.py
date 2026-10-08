import socket
import struct
import time
import csv
import datetime
import math

# ============================================================
# DOBOT NOVA 5 SETTINGS
# ============================================================

ROBOT_IP = "192.168.5.1"
FEEDBACK_PORT = 30004
PACKET_SIZE = 1440

# ------------------------------------------------------------
# Byte offsets inside the 1440-byte feedback packet.
# These match Dobot's official MyType struct (TCP-IP-Python-V3 / dobot_api.py).
# ------------------------------------------------------------
OFF_ROBOT_MODE        = 24   # uint64
OFF_DIGITAL_INPUTS    = 8    # uint64
OFF_DIGITAL_OUTPUTS   = 16   # uint64
OFF_Q_ACTUAL          = 432  # 6 x float64  -> actual joint angles j1..j6
OFF_QD_ACTUAL         = 480  # 6 x float64  -> actual joint velocities
OFF_TOOL_VECTOR_ACTUAL = 624 # 6 x float64  -> actual TCP pose x,y,z,rx,ry,rz
OFF_TCP_SPEED_ACTUAL  = 672  # 6 x float64  -> actual TCP velocity (vx,vy,vz,wx,wy,wz)

# ============================================================
# USER-DEFINED / EXPERIMENT-TRACKING FIELDS
# These are NOT part of the raw Dobot packet. Wire these up to
# your own move-command / experiment logic as needed.
# ============================================================

RUN_ID = "Observer_" + datetime.datetime.now().strftime("%Y%m%d")
cycle_id = 0   # increment this yourself when a new pick-place cycle starts
seg_id = 0     # increment this yourself when a new segment within a cycle starts
set_vel = ""   # set this from the speed value you pass to MovL/MovJ/SpeedL etc.
               # (the feedback packet only exposes speed_scaling, not the commanded speed)

# Running totals used for moved_mi / moved_de (best-guess interpretation:
# cumulative TCP distance traveled in mm, and cumulative joint rotation in degrees).
# CONFIRM this matches what you actually want.
moved_mi_total = 0.0
moved_de_total = 0.0
prev_xyz = None
prev_joints = None


# ============================================================
# CONNECT TO ROBOT
# ============================================================

print("Connecting to Dobot Nova 5...")
print(f"IP: {ROBOT_IP}")
print(f"Port: {FEEDBACK_PORT}")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.connect((ROBOT_IP, FEEDBACK_PORT))
    print("CONNECTED!")
    print("Receiving real-time feedback...")
    print("Press Ctrl+C to stop.\n")

except Exception as e:
    print("Connection failed!")
    print(e)
    sock.close()
    raise SystemExit(1)


# ============================================================
# RECEIVE DATA
# ============================================================

packet_counter = 0
start_time = time.perf_counter()

csv_file = open("robot_feedback.csv", mode="w", newline="")
csv_writer = csv.writer(csv_file)

HEADER = [
    "run_id", "cycle_id", "seg_id", "t", "wall", "set_vel",
    "x", "y", "z", "rx", "ry", "rz",
    "j1", "j2", "j3", "j4", "j5", "j6",
    "moved_mi", "moved_de",
    "vel_j1", "vel_j2", "vel_j3", "vel_j4", "vel_j5", "vel_j6",
    "vel_tcp1", "vel_tcp2", "vel_tcp3", "vel_tcp4", "vel_tcp5", "vel_tcp6",
]
csv_writer.writerow(HEADER)

try:
    while True:

        # ----------------------------------------------------
        # Receive exactly 1440 bytes
        # ----------------------------------------------------

        data = b""

        while len(data) < PACKET_SIZE:

            chunk = sock.recv(PACKET_SIZE - len(data))

            if not chunk:
                print("Robot closed the connection.")
                raise ConnectionError("Connection closed")

            data += chunk

        packet_counter += 1

        # ----------------------------------------------------
        # TIMESTAMP
        # ----------------------------------------------------

        timestamp_seconds = time.perf_counter() - start_time
        wall_clock = datetime.datetime.now().isoformat(timespec="seconds")

        # ----------------------------------------------------
        # READ VALUES FROM PACKET
        # ----------------------------------------------------

        robot_mode = struct.unpack_from("<Q", data, OFF_ROBOT_MODE)[0]
        digital_inputs = struct.unpack_from("<Q", data, OFF_DIGITAL_INPUTS)[0]
        digital_outputs = struct.unpack_from("<Q", data, OFF_DIGITAL_OUTPUTS)[0]

        joints = struct.unpack_from("<6d", data, OFF_Q_ACTUAL)
        vel_joints = struct.unpack_from("<6d", data, OFF_QD_ACTUAL)
        tcp_pose = struct.unpack_from("<6d", data, OFF_TOOL_VECTOR_ACTUAL)
        tcp_vel = struct.unpack_from("<6d", data, OFF_TCP_SPEED_ACTUAL)

        x, y, z, rx, ry, rz = tcp_pose
        j1, j2, j3, j4, j5, j6 = joints
        vel_j1, vel_j2, vel_j3, vel_j4, vel_j5, vel_j6 = vel_joints
        vel_tcp1, vel_tcp2, vel_tcp3, vel_tcp4, vel_tcp5, vel_tcp6 = tcp_vel

        # ----------------------------------------------------
        # RUNNING TOTALS: moved_mi (mm), moved_de (deg)
        # ----------------------------------------------------

        if prev_xyz is not None:
            dx = x - prev_xyz[0]
            dy = y - prev_xyz[1]
            dz = z - prev_xyz[2]
            moved_mi_total += math.sqrt(dx * dx + dy * dy + dz * dz)

        if prev_joints is not None:
            moved_de_total += sum(
                abs(joints[i] - prev_joints[i]) for i in range(6)
            )

        prev_xyz = (x, y, z)
        prev_joints = joints

        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            f"Packet: {packet_counter:6d} | "
            f"Time: {timestamp_seconds:10.4f} s | "
            f"Mode: {robot_mode:2d} | "
            f"DI: {digital_inputs:016X} | "
            f"DO: {digital_outputs:016X}"
        )

        # ----------------------------------------------------
        # WRITE TO CSV
        # ----------------------------------------------------

        csv_writer.writerow([
            RUN_ID, cycle_id, seg_id,
            f"{timestamp_seconds:.4f}", wall_clock, set_vel,
            x, y, z, rx, ry, rz,
            j1, j2, j3, j4, j5, j6,
            moved_mi_total, moved_de_total,
            vel_j1, vel_j2, vel_j3, vel_j4, vel_j5, vel_j6,
            vel_tcp1, vel_tcp2, vel_tcp3, vel_tcp4, vel_tcp5, vel_tcp6,
        ])

except KeyboardInterrupt:
    print("\n\nStopped by user.")

except Exception as e:
    print("\nERROR:")
    print(e)

finally:
    sock.close()
    csv_file.close()


print("\nConnection closed.")

if packet_counter > 0:
    elapsed = time.perf_counter() - start_time
    frequency = packet_counter / elapsed

    print(f"Packets received: {packet_counter}")
    print(f"Elapsed time: {elapsed:.3f} s")
    print(f"Average frequency: {frequency:.2f} Hz")