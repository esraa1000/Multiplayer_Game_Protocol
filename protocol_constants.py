# protocol_constants.py
PROTO_ID = b'CCLP'
VERSION = 1

# Message types
MSG_INIT = 0x01
MSG_INIT_ACK = 0x02
MSG_SNAPSHOT = 0x03
MSG_EVENT = 0x04
MSG_ACK = 0x05
MSG_GAME_OVER = 0x06

# Header format (for struct.pack/unpack)
HEADER_FMT = '!4s B B I I Q H I'   # 28 bytes
HEADER_SIZE = 28

# Default behavior / limits
MAX_PACKET_BYTES = 1200
DEFAULT_REdundancy_K = 2
DEFAULT_SNAPSHOT_RATE_HZ = 20
