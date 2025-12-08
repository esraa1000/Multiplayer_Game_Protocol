import socket
import struct
import time
import zlib

HEADER_FORMAT = "!4s B B I I Q H I"
PROTOCOL_ID = b"CCLP"
VERSION = 2

HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

MSG_INIT = 0x01
MSG_INIT_ACK = 0x02

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_addr = ("127.0.0.1", 9999)

seq_num = 1
payload = b"\x01"   # client_id=1
snapshot_id = 0

# IMPORTANT: Use the SAME timestamp for both headers
timestamp_ms = int(time.time() * 1000)

# 1) Build the temporary header with checksum = 0
temp_header = struct.pack(
    HEADER_FORMAT,
    PROTOCOL_ID,
    VERSION,
    MSG_INIT,
    snapshot_id,
    seq_num,
    timestamp_ms,
    len(payload),
    0
)

# 2) Compute checksum
checksum = zlib.crc32(temp_header + payload) & 0xFFFFFFFF

# 3) Build final header with correct checksum
final_header = struct.pack(
    HEADER_FORMAT,
    PROTOCOL_ID,
    VERSION,
    MSG_INIT,
    snapshot_id,
    seq_num,
    timestamp_ms,
    len(payload),
    checksum
)

packet = final_header + payload
client_socket.sendto(packet, server_addr)

print("[CLIENT] INIT sent")

# Receive response
data, _ = client_socket.recvfrom(2048)
recv_header = data[:HEADER_SIZE]
recv_payload = data[HEADER_SIZE:]

(
    protocol_id,
    version,
    msg_type,
    snapshot_id,
    seq_num,
    server_timestamp,
    payload_len,
    checksum
) = struct.unpack(HEADER_FORMAT, recv_header)

print(f"[CLIENT] Received msg_type={msg_type} seq={seq_num} payload={recv_payload}")
