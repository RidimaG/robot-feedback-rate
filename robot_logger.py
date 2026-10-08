import socket
import struct
import time
import csv
# ============================================================
# DOBOT NOVA 5 SETTINGS
# ============================================================

ROBOT_IP = "192.168.5.1"
FEEDBACK_PORT = 30004

PACKET_SIZE = 1440


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

csv_writer.writerow(["Time_s","Packet","Robot_Mode","Digital_Inputs","Digital_Outputs"])

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


        # ----------------------------------------------------
        # READ BASIC VALUES
        # ----------------------------------------------------

        # First 2 bytes = message size
        message_size = struct.unpack_from("<H", data, 0)[0]

        # Bytes 24-31 = Robot Mode
        robot_mode = struct.unpack_from("<Q", data, 24)[0]

        # Bytes 8-15 = Digital Inputs
        digital_inputs = struct.unpack_from("<Q", data, 8)[0]

        # Bytes 16-23 = Digital Outputs
        digital_outputs = struct.unpack_from("<Q", data, 16)[0]


        # ----------------------------------------------------
        # PRINT
        # ----------------------------------------------------

        print(
            f"Packet: {packet_counter:6d} | "
            f"Time: {timestamp_seconds:10.0f} s | "
            f"Size: {message_size:4d} | "
            f"Mode: {robot_mode:2d} | "
            f"DI: {digital_inputs:016X} | "
            f"DO: {digital_outputs:016X}"
        )

        # ----------------------------------------------------
        # WRITE TO CSV
        # ----------------------------------------------------

        csv_writer.writerow([
            f"{timestamp_seconds:10.0f}",
            f"{packet_counter:6d}",
            f"{robot_mode:2d}",
            f"{digital_inputs:016X}",
            f"{digital_outputs:016X}"
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