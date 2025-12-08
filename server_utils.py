import struct
import time
import zlib

from protocol_constants import (
    HEADER_FORMAT,
    HEADER_SIZE,
    PROTOCOL_ID,
    VERSION
)

# GLOBAL SEQ COUNTER
seq_counter = 0

def next_seq_num():
    global seq_counter
    seq_counter += 1
    return seq_counter

def current_time_ms():
    return int(time.time() * 1000)

def compute_crc32(header_without_crc, payload_bytes):
    return zlib.crc32(header_without_crc + payload_bytes) & 0xFFFFFFFF

def pack_header(msg_type, snapshot_id, seq_num, timestamp_ms, payload_bytes):
    payload_len = len(payload_bytes)

    temp_header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len,
        0
    )

    crc = compute_crc32(temp_header, payload_bytes)

    final_header = struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len,
        crc
    )
    return final_header

def parse_and_validate_header(data):
    if len(data) < HEADER_SIZE:
        return None

    header = data[:HEADER_SIZE]
    payload = data[HEADER_SIZE:]

    (
        protocol_id,
        version,
        msg_type,
        snapshot_id,
        seq_num,
        server_timestamp,
        payload_len,
        recv_checksum
    ) = struct.unpack(HEADER_FORMAT, header)

    if protocol_id != PROTOCOL_ID:
        return None
    if version != VERSION:
        return None
    if payload_len != len(payload):
        return None

    temp_header = struct.pack(
        HEADER_FORMAT,
        protocol_id,
        version,
        msg_type,
        snapshot_id,
        seq_num,
        server_timestamp,
        payload_len,
        0
    )
    computed = compute_crc32(temp_header, payload)
    if computed != recv_checksum:
        return None

    return {
        "msg_type": msg_type,
        "snapshot_id": snapshot_id,
        "seq_num": seq_num,
        "server_timestamp": server_timestamp,
        "payload": payload,
    }

def send_packet(sock, addr, msg_type, snapshot_id, payload_bytes):
    seq = next_seq_num()
    timestamp = current_time_ms()
    header = pack_header(msg_type, snapshot_id, seq, timestamp, payload_bytes)

    sock.sendto(header + payload_bytes, addr)
    print(f"[SEND] type={msg_type} seq={seq} to {addr}")
