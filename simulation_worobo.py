import csv
import time
import datetime
import math
import random

# ============================================================
# SIMULATION SETTINGS
# ============================================================

CSV_PATH = "robot_feedback_simulation.csv"
UPDATE_HZ = 5          # how many rows per second to write (real robot = ~125 Hz / 8ms)
RUN_SECONDS = None     # set to a number to auto-stop, or leave None to run until Ctrl+C

RUN_ID = "Sim_" + datetime.datetime.now().strftime("%Y%m%d")
cycle_id = 0
seg_id = 0
set_vel = 100  # fake commanded speed, %

HEADER = [
    "run_id", "cycle_id", "seg_id", "t", "wall", "set_vel",
    "x", "y", "z", "rx", "ry", "rz",
    "j1", "j2", "j3", "j4", "j5", "j6",
    "moved_mi", "moved_de",
    "vel_j1", "vel_j2", "vel_j3", "vel_j4", "vel_j5", "vel_j6",
    "vel_tcp1", "vel_tcp2", "vel_tcp3", "vel_tcp4", "vel_tcp5", "vel_tcp6",
]


def fake_packet(t):
    """
    Generates plausible-looking robot values as smooth functions of time,
    so you can visually confirm the CSV is updating with sensible, moving numbers
    (rather than random noise that's hard to eyeball).
    """
    # Cartesian pose: slow circular-ish motion
    x = 250 + 80 * math.sin(0.2 * t)
    y = -150 + 80 * math.cos(0.2 * t)
    z = 100 + 20 * math.sin(0.1 * t)
    rx = 178.0 + 2 * math.sin(0.3 * t)
    ry = -90.0 + 2 * math.cos(0.3 * t)
    rz = -72.0 + math.sin(0.15 * t)

    # Joint angles: gentle oscillation around a home pose
    home = [104.0, -90.0, 130.0, -90.0, -72.0, -0.1]
    amps = [30, 15, 25, 10, 5, 2]
    freqs = [0.15, 0.12, 0.18, 0.1, 0.2, 0.05]
    joints = [
        home[i] + amps[i] * math.sin(freqs[i] * t + i)
        for i in range(6)
    ]

    # Joint velocities: derivative-ish, just for plausible non-zero numbers
    vel_joints = [
        amps[i] * freqs[i] * math.cos(freqs[i] * t + i)
        for i in range(6)
    ]

    # TCP velocity: small random jitter around a base value
    tcp_vel = [round(random.uniform(-5, 5), 4) for _ in range(6)]

    return x, y, z, rx, ry, rz, joints, vel_joints, tcp_vel


# ============================================================
# RUN SIMULATION
# ============================================================

print(f"Simulating robot feedback -> {CSV_PATH}")
print(f"Writing ~{UPDATE_HZ} rows/sec. Press Ctrl+C to stop.\n")

csv_file = open(CSV_PATH, mode="w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(HEADER)
csv_file.flush()

packet_counter = 0
start_time = time.perf_counter()

moved_mi_total = 0.0
moved_de_total = 0.0
prev_xyz = None
prev_joints = None

interval = 1.0 / UPDATE_HZ

try:
    while True:
        loop_start = time.perf_counter()
        t = time.perf_counter() - start_time

        if RUN_SECONDS is not None and t >= RUN_SECONDS:
            break

        packet_counter += 1
        wall_clock = datetime.datetime.now().isoformat(timespec="seconds")

        x, y, z, rx, ry, rz, joints, vel_joints, tcp_vel = fake_packet(t)
        j1, j2, j3, j4, j5, j6 = joints
        vel_j1, vel_j2, vel_j3, vel_j4, vel_j5, vel_j6 = vel_joints
        vel_tcp1, vel_tcp2, vel_tcp3, vel_tcp4, vel_tcp5, vel_tcp6 = tcp_vel

        if prev_xyz is not None:
            dx, dy, dz = x - prev_xyz[0], y - prev_xyz[1], z - prev_xyz[2]
            moved_mi_total += math.sqrt(dx * dx + dy * dy + dz * dz)

        if prev_joints is not None:
            moved_de_total += sum(abs(joints[i] - prev_joints[i]) for i in range(6))

        prev_xyz = (x, y, z)
        prev_joints = joints

        print(
            f"Packet: {packet_counter:6d} | t: {t:8.2f}s | "
            f"x={x:8.2f} y={y:8.2f} z={z:8.2f} | j1={j1:7.2f}"
        )

        csv_writer.writerow([
            RUN_ID, cycle_id, seg_id,
            f"{t:.4f}", wall_clock, set_vel,
            round(x, 4), round(y, 4), round(z, 4),
            round(rx, 4), round(ry, 4), round(rz, 4),
            round(j1, 4), round(j2, 4), round(j3, 4),
            round(j4, 4), round(j5, 4), round(j6, 4),
            round(moved_mi_total, 4), round(moved_de_total, 4),
            round(vel_j1, 4), round(vel_j2, 4), round(vel_j3, 4),
            round(vel_j4, 4), round(vel_j5, 4), round(vel_j6, 4),
            vel_tcp1, vel_tcp2, vel_tcp3, vel_tcp4, vel_tcp5, vel_tcp6,
        ])
        # Flush + fsync after every row so you can watch the file grow live
        # (e.g. tail the file, or reopen it in VS Code / Excel) without waiting
        # for the program to exit.
        csv_file.flush()

        # keep a steady update rate
        elapsed = time.perf_counter() - loop_start
        time.sleep(max(0.0, interval - elapsed))

except KeyboardInterrupt:
    print("\n\nStopped by user.")

finally:
    csv_file.close()

print("\nSimulation ended.")
if packet_counter > 0:
    elapsed = time.perf_counter() - start_time
    print(f"Rows written: {packet_counter}")
    print(f"Elapsed time: {elapsed:.2f} s")
    print(f"Average rate: {packet_counter / elapsed:.2f} rows/sec")