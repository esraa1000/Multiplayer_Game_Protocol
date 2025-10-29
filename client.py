import socket
import struct

HEADER_FORMAT = "!4s B B I H"
PROTOCOL_ID = b"GCLH"
VERSION = 1
MSG_INIT = 0

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_addr = ("127.0.0.1", 9999)

seq_num = 1
payload = b"\x01"  # client_id = 1

header = struct.pack(HEADER_FORMAT, PROTOCOL_ID, VERSION, MSG_INIT, seq_num, len(payload))
packet = header + payload
client_socket.sendto(packet, server_addr)

print("INIT sent")

data, _ = client_socket.recvfrom(2048)
header = data[:12]
protocol_id, version, msg_type, seq_num, payload_len = struct.unpack(HEADER_FORMAT, header)
payload = data[12:12+payload_len]
print(f"Received msg_type={msg_type} seq={seq_num} payload={payload}")
