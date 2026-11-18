import asyncio
import socket
import struct
from typing import Awaitable, Callable, Tuple

SOCKS_VERSION = 5
NO_AUTH = 0x00
NO_ACCEPTABLE = 0xFF
ATYP_IPV4 = 0x01
CMD_CONNECT = 0x01
REP_SUCCESS = 0x00
REP_GENERAL_FAILURE = 0x01
REP_CONN_REFUSED = 0x05
REP_CMD_NOT_SUPPORTED = 0x07
REP_ATYP_NOT_SUPPORTED = 0x08

Connector = Callable[[str, int], Awaitable[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]]

async def relay(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
    """
    Manage data flow between clients and server.
    """
    try:
        while True:
            data = await src.read(8192)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        dst.close()


async def auth(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Inspection of the first messages issued by the client, where the authentication method is agreed
    """
    ver, nmethods = struct.unpack("!BB", await reader.readexactly(2))
    if ver != SOCKS_VERSION:
        raise ValueError(f"unsupported SOCKS version {ver}")
    methods = await reader.readexactly(nmethods)

    if NO_AUTH not in methods:
        writer.write(struct.pack("!BB", SOCKS_VERSION, NO_ACCEPTABLE))
        await writer.drain()
        raise ValueError("client offered no acceptable auth method")

    writer.write(struct.pack("!BB", SOCKS_VERSION, NO_AUTH))
    await writer.drain()


async def reply(writer: asyncio.StreamWriter, rep: int, bind_addr: str, bind_port: int, atyp=ATYP_IPV4):
    """
    Send the corresponding response code to the client
    """
    addr_bytes = socket.inet_pton(socket.AF_INET, bind_addr)
    response = struct.pack("!BBBB4sH", SOCKS_VERSION, rep, 0x00, atyp, addr_bytes, bind_port)
    writer.write(response)
    await writer.drain()


async def check_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, connector: Connector,
                         bind_addr: str = "0.0.0.0", bind_port: int = 0):
    """
    Parses a CONNECT request and dials the target through `connector`.

    `connector` decouples "how do we reach the target" from SOCKS parsing:
    a plain server dials a real socket, a tunnel opens a logical mux stream.
    `bind_addr`/`bind_port` are only used to fill the SUCCESS reply and have
    no real meaning once the target is reached through a tunnel.
    """
    ver, cmd = struct.unpack("!BB", await reader.readexactly(2))
    await reader.readexactly(1)  # RSV
    atyp = (await reader.readexactly(1))[0]
    if ver != SOCKS_VERSION:
        raise ValueError("bad version in request")
    if cmd != CMD_CONNECT:
        await reply(writer, REP_CMD_NOT_SUPPORTED, bind_addr, bind_port)
        raise ValueError(f"unsupported command {cmd}")
    if atyp != ATYP_IPV4:
        await reply(writer, REP_ATYP_NOT_SUPPORTED, bind_addr, bind_port)
        raise ValueError(f"unsupported address type {atyp}")

    raw = await reader.readexactly(4)
    taddr = socket.inet_ntop(socket.AF_INET, raw)
    tport = struct.unpack("!H", await reader.readexactly(2))[0]

    try:
        treader, twriter = await connector(taddr, tport)
    except OSError as e:
        await reply(writer, REP_CONN_REFUSED, bind_addr, bind_port)
        raise ValueError(f"connect to {taddr}:{tport} failed: {e}")

    await reply(writer, REP_SUCCESS, bind_addr, bind_port)

    return treader, twriter, f"{taddr}:{tport}"


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, connector: Connector):
    """
    Handle one SOCKS5 client connection end to end, using `connector` to reach the target.
    """
    peer = writer.get_extra_info("peername")
    print(f"[i] Connection from {peer}")
    try:
        await auth(reader, writer)
        print("[S] Authentication method accepted")
        bind_addr, bind_port = writer.get_extra_info("sockname")[:2]
        treader, twriter, taddr = await check_request(reader, writer, connector, bind_addr, bind_port)
    except Exception as e:
        print(f"[E] {peer}: {e}")
        writer.close()
        return

    print(f"[i] Connection {peer} -> {taddr} stablished")
    await asyncio.gather(
        relay(reader, twriter),
        relay(treader, writer),
    )
    print(f"[x] Connection from {peer} closed")
