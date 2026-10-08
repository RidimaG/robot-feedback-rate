import socket
import struct
import time
import csv
import datetime
import math
import os
import json

# ============================================================
# DOBOT NOVA 5 SETTINGS
# ============================================================

ROBOT_IP = "192.168.6.3"
FEEDBACK_PORT = 30004
PACKET_SIZE = 1440

# Save one CSV row every second
LOG_INTERVAL = 1.0

# Folder where all daily CSV files will be stored
LOG_FOLDER = "robot_logs"

# Persistent state file
STATE_FILE = "robot_logger_state.json"


# ============================================================
# BYTE OFFSETS
# ============================================================

OFF_ROBOT_MODE         = 24
OFF_DIGITAL_INPUTS     = 8
OFF_DIGITAL_OUTPUTS    = 16

OFF_Q_ACTUAL           = 432   # 6 x float64
OFF_QD_ACTUAL          = 480   # 6 x float64

OFF_TOOL_VECTOR_ACTUAL = 624   # x,y,z,rx,ry,rz
OFF_TCP_SPEED_ACTUAL   = 672   # vx,vy,vz,wx,wy,wz


# ============================================================
# USER / EXPERIMENT FIELDS
# ============================================================

RUN_ID = "Observer_" + datetime.datetime.now().strftime("%Y%m%d")

cycle_id = 0
seg_id = 0

# Set this manually or from your experiment logic
set_vel = ""


# ============================================================
# CREATE LOG FOLDER
# ============================================================

os.makedirs(LOG_FOLDER, exist_ok=True)


# ============================================================
# STATE FUNCTIONS
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {
            "moved_mi_total": 0.0,
            "moved_de_total": 0.0,
            "cycle_id": 0,
            "seg_id": 0
        }

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        print("Previous logger state loaded.")

        return state

    except Exception as e:

        print("Could not read state file.")
        print(e)

        return {
            "moved_mi_total": 0.0,
            "moved_de_total": 0.0,
            "cycle_id": 0,
            "seg_id": 0
        }


def save_state():

    state = {
        "moved_mi_total": moved_mi_total,
        "moved_de_total": moved_de_total,
        "cycle_id": cycle_id,
        "seg_id": seg_id
    }

    # Write to temporary file first
    # This reduces the chance of corrupting the state file
    # if the computer is interrupted during writing.

    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w") as f:
        json.dump(state, f, indent=4)

    os.replace(temp_file, STATE_FILE)


# ============================================================
# LOAD PREVIOUS STATE
# ============================================================

state = load_state()

moved_mi_total = state["moved_mi_total"]
moved_de_total = state["moved_de_total"]

cycle_id = state["cycle_id"]
seg_id = state["seg_id"]


# ============================================================
# CSV HEADER
# ============================================================

HEADER = [
    "run_id",
    "cycle_id",
    "seg_id",

    "t_s",
    "wall",

    "set_vel",

    "x_mm",
    "y_mm",
    "z_mm",

    "rx_deg",
    "ry_deg",
    "rz_deg",

    "j1_deg",
    "j2_deg",
    "j3_deg",
    "j4_deg",
    "j5_deg",
    "j6_deg",

    "moved_mi_mm",
    "moved_de_deg",

    "vel_j1_deg_s",
    "vel_j2_deg_s",
    "vel_j3_deg_s",
    "vel_j4_deg_s",
    "vel_j5_deg_s",
    "vel_j6_deg_s",

    "vel_tcp1_mm_s",
    "vel_tcp2_mm_s",
    "vel_tcp3_mm_s",

    "vel_tcp4_deg_s",
    "vel_tcp5_deg_s",
    "vel_tcp6_deg_s"
]


# ============================================================
# DAILY CSV MANAGEMENT
# ============================================================

current_csv_date = None
csv_file = None
csv_writer = None


def get_csv_filename(date_string):

    return os.path.join(
        LOG_FOLDER,
        f"robot_feedback_{date_string}.csv"
    )


def open_daily_csv(date_string):

    global csv_file
    global csv_writer
    global current_csv_date

    filename = get_csv_filename(date_string)

    file_exists = os.path.exists(filename)
    file_has_data = file_exists and os.path.getsize(filename) > 0

    # Close previous day's file
    if csv_file is not None:
        csv_file.flush()
        os.fsync(csv_file.fileno())
        csv_file.close()

    # Append if file already exists
    # Otherwise create a new file.
    csv_file = open(
        filename,
        mode="a",
        newline="",
        buffering=1
    )

    csv_writer = csv.writer(csv_file)

    # Only write header if this is a new/empty file
    if not file_has_data:
        csv_writer.writerow(HEADER)

        csv_file.flush()
        os.fsync(csv_file.fileno())

        print(f"Created new CSV file:")
        print(f"  {filename}")

    else:
        print(f"Continuing existing CSV file:")
        print(f"  {filename}")

    current_csv_date = date_string


# ============================================================
# CONNECT TO ROBOT
# ============================================================

print("==============================================")
print(" DOBOT NOVA 5 - 1 Hz DATA LOGGER")
print("==============================================")
print()
print(f"Robot IP : {ROBOT_IP}")
print(f"Port     : {FEEDBACK_PORT}")
print(f"CSV rate : {LOG_INTERVAL} second")
print()

print("Connecting to Dobot Nova 5...")

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
# LOGGER VARIABLES
# ============================================================

packet_counter = 0
csv_counter = 0

start_time = time.perf_counter()

# First sample occurs immediately
next_log_time = start_time

# Previous position used ONLY for calculating movement
#
# IMPORTANT:
# This starts as None after a restart.
# Therefore we do NOT calculate the distance between the
# last sample before shutdown and the first sample after restart.

prev_xyz = None
prev_joints = None

# Latest robot feedback
latest_data = None


# ============================================================
# MAIN RECEIVE LOOP
# ============================================================

try:

    while True:

        # ----------------------------------------------------
        # RECEIVE EXACTLY ONE 1440-BYTE PACKET
        # ----------------------------------------------------

        data = b""

        while len(data) < PACKET_SIZE:

            chunk = sock.recv(PACKET_SIZE - len(data))

            if not chunk:

                print("Robot closed the connection.")

                raise ConnectionError(
                    "Robot feedback connection closed"
                )

            data += chunk

        packet_counter += 1

        # ----------------------------------------------------
        # CURRENT COMPUTER TIME
        # ----------------------------------------------------

        now = time.perf_counter()

        timestamp_seconds = now - start_time

        wall_datetime = datetime.datetime.now()

        wall_clock = wall_datetime.isoformat(
            timespec="milliseconds"
        )

        date_string = wall_datetime.strftime("%Y-%m-%d")


        # ----------------------------------------------------
        # OPEN / CHANGE DAILY CSV
        # ----------------------------------------------------

        if current_csv_date != date_string:

            open_daily_csv(date_string)


        # ----------------------------------------------------
        # READ ROBOT FEEDBACK
        # ----------------------------------------------------

        robot_mode = struct.unpack_from(
            "<Q",
            data,
            OFF_ROBOT_MODE
        )[0]

        digital_inputs = struct.unpack_from(
            "<Q",
            data,
            OFF_DIGITAL_INPUTS
        )[0]

        digital_outputs = struct.unpack_from(
            "<Q",
            data,
            OFF_DIGITAL_OUTPUTS
        )[0]


        # ----------------------------------------------------
        # JOINT POSITION
        # ----------------------------------------------------

        joints = struct.unpack_from(
            "<6d",
            data,
            OFF_Q_ACTUAL
        )


        # ----------------------------------------------------
        # JOINT VELOCITY
        # ----------------------------------------------------

        vel_joints = struct.unpack_from(
            "<6d",
            data,
            OFF_QD_ACTUAL
        )


        # ----------------------------------------------------
        # TCP POSITION
        # ----------------------------------------------------

        tcp_pose = struct.unpack_from(
            "<6d",
            data,
            OFF_TOOL_VECTOR_ACTUAL
        )


        # ----------------------------------------------------
        # TCP VELOCITY
        # ----------------------------------------------------

        tcp_vel = struct.unpack_from(
            "<6d",
            data,
            OFF_TCP_SPEED_ACTUAL
        )


        # ----------------------------------------------------
        # UNPACK VALUES
        # ----------------------------------------------------

        x, y, z, rx, ry, rz = tcp_pose

        j1, j2, j3, j4, j5, j6 = joints

        vel_j1, vel_j2, vel_j3, vel_j4, vel_j5, vel_j6 = vel_joints

        vel_tcp1, vel_tcp2, vel_tcp3, vel_tcp4, vel_tcp5, vel_tcp6 = tcp_vel


        # ----------------------------------------------------
        # STORE LATEST FEEDBACK
        # ----------------------------------------------------

        latest_data = {
            "robot_mode": robot_mode,
            "digital_inputs": digital_inputs,
            "digital_outputs": digital_outputs,

            "x": x,
            "y": y,
            "z": z,

            "rx": rx,
            "ry": ry,
            "rz": rz,

            "joints": joints,
            "vel_joints": vel_joints,
            "tcp_vel": tcp_vel
        }


        # ====================================================
        # WRITE ONLY ONCE PER SECOND
        # ====================================================

        if now >= next_log_time:

            # ------------------------------------------------
            # MOVEMENT CALCULATION
            # ------------------------------------------------

            if prev_xyz is not None:

                dx = x - prev_xyz[0]
                dy = y - prev_xyz[1]
                dz = z - prev_xyz[2]

                distance = math.sqrt(
                    dx * dx +
                    dy * dy +
                    dz * dz
                )

                moved_mi_total += distance


            if prev_joints is not None:

                joint_rotation = sum(
                    abs(
                        joints[i] -
                        prev_joints[i]
                    )
                    for i in range(6)
                )

                moved_de_total += joint_rotation


            # Save current position for next 1-second sample
            prev_xyz = (x, y, z)
            prev_joints = joints


            # ------------------------------------------------
            # WRITE CSV ROW
            # ------------------------------------------------

            csv_writer.writerow([

                RUN_ID,

                cycle_id,

                seg_id,

                f"{timestamp_seconds:.4f}",

                wall_clock,

                set_vel,

                # TCP position
                f"{x:.6f}",
                f"{y:.6f}",
                f"{z:.6f}",

                # TCP orientation
                f"{rx:.6f}",
                f"{ry:.6f}",
                f"{rz:.6f}",

                # Joint positions
                f"{j1:.6f}",
                f"{j2:.6f}",
                f"{j3:.6f}",
                f"{j4:.6f}",
                f"{j5:.6f}",
                f"{j6:.6f}",

                # Cumulative movement
                f"{moved_mi_total:.6f}",
                f"{moved_de_total:.6f}",

                # Joint velocities
                f"{vel_j1:.6f}",
                f"{vel_j2:.6f}",
                f"{vel_j3:.6f}",
                f"{vel_j4:.6f}",
                f"{vel_j5:.6f}",
                f"{vel_j6:.6f}",

                # TCP linear velocity
                f"{vel_tcp1:.6f}",
                f"{vel_tcp2:.6f}",
                f"{vel_tcp3:.6f}",

                # TCP rotational velocity
                f"{vel_tcp4:.6f}",
                f"{vel_tcp5:.6f}",
                f"{vel_tcp6:.6f}"
            ])


            csv_counter += 1


            # ------------------------------------------------
            # FORCE DATA TO DISK
            # ------------------------------------------------

            csv_file.flush()

            os.fsync(
                csv_file.fileno()
            )


            # ------------------------------------------------
            # SAVE LOGGER STATE
            # ------------------------------------------------

            save_state()


            # ------------------------------------------------
            # PRINT STATUS
            # ------------------------------------------------

            print(
                f"LOG #{csv_counter:6d} | "
                f"t={timestamp_seconds:10.3f}s | "
                f"X={x:9.3f} mm | "
                f"Y={y:9.3f} mm | "
                f"Z={z:9.3f} mm | "
                f"J1={j1:8.3f}°"
            )


            # ------------------------------------------------
            # SCHEDULE NEXT SAMPLE
            # ------------------------------------------------

            #
            # Do NOT simply use:
            #
            # next_log_time = now + 1
            #
            # because small timing errors would accumulate.
            #
            # Instead, keep the schedule locked to the original
            # 1-second grid.
            #

            while next_log_time <= now:

                next_log_time += LOG_INTERVAL


# ============================================================
# STOPPED BY USER
# ============================================================

except KeyboardInterrupt:

    print("\n")
    print("==============================================")
    print(" Logger stopped by user")
    print("==============================================")


# ============================================================
# OTHER ERRORS
# ============================================================

except Exception as e:

    print("\n")
    print("==============================================")
    print(" LOGGER ERROR")
    print("==============================================")

    print(e)


# ============================================================
# CLEANUP
# ============================================================

finally:

    print("\nSaving final data...")

    try:

        if csv_file is not None:

            csv_file.flush()

            os.fsync(
                csv_file.fileno()
            )

            csv_file.close()

    except Exception:
        pass


    try:

        sock.close()

    except Exception:
        pass


print("\n==============================================")
print("Connection closed.")
print("==============================================")

print(f"Feedback packets received : {packet_counter}")
print(f"CSV samples written       : {csv_counter}")

if packet_counter > 0:

    elapsed = time.perf_counter() - start_time

    feedback_frequency = (
        packet_counter / elapsed
    )

    print(
        f"Feedback frequency       : "
        f"{feedback_frequency:.2f} Hz"
    )

print(f"Cumulative TCP distance   : {moved_mi_total:.3f} mm")
print(f"Cumulative joint rotation : {moved_de_total:.3f} deg")
print()
print(f"CSV folder: {LOG_FOLDER}")
print(f"State file: {STATE_FILE}")
