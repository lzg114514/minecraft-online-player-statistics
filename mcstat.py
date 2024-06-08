import socket
import struct
import json


def unpack_varint(s: socket.socket) -> int:
    d: int = 0
    for i in range(5):
        b: int = ord(s.recv(1))
        d |= (b & 0x7F) << 7 * i
        if not b & 0x80:
            break
    return d


def pack_varint(d: int) -> bytes:
    o = b""
    while True:
        b = d & 0x7F
        d >>= 7
        o += struct.pack("B", b | (0x80 if d > 0 else 0))
        if d == 0:
            break
    return o


def pack_data(d: bytes) -> bytes:
    return pack_varint(len(d)) + d


def pack_port(i: int) -> bytes:
    return struct.pack('>H', i)


def get_info(host: str, port: int = 25565) -> dict:
    # Connect
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    # Send handshake + status request
    s.send(pack_data(b"\x00\x00" + pack_data(host.encode('utf8')) + pack_port(port) + b"\x01"))
    s.send(pack_data(b"\x00"))

    # Read response
    unpack_varint(s)  # Packet length
    unpack_varint(s)  # Packet ID
    l = unpack_varint(s)  # String length

    d = b""
    while len(d) < l:
        d += s.recv(1024)

    # Close our socket
    s.close()

    # Load json and return
    return json.loads(d.decode('utf8'))
