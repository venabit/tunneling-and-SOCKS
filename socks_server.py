import argparse
import asyncio
import socket
import struct

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


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Handle each client Connection to the server.
    """
    peer = writer.get_extra_info("peername")
    print(f"[i] Connection from {peer}")
    try:
        await auth(reader, writer)
        print("[S] Authentication method accepted")
        treader, twriter, taddr = await check_request(reader, writer)
    except Exception as e:
        print(f"[E] {peer}: {e}")
        writer.close()
        return

    print(f"[i] Connection {peer} -> {taddr} stablished")
    await asyncio.gather(
        relay(reader, twriter),
        relay(treader, writer),
    )
    print(f"[x] Connection to {peer} closed")


async def auth(reader, writer):
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


async def reply(writer, rep, atyp=ATYP_IPV4):
    """
    Send the corresponding response code to the client
    """
    addr, port = writer.get_extra_info("sockname")[:2]
    addr_bytes = socket.inet_pton(socket.AF_INET, addr)
    response = struct.pack("!BBBB4sH", SOCKS_VERSION, rep, 0x00, atyp, addr_bytes, port)
    writer.write(response)
    await writer.drain()


async def check_request(reader, writer):
    """
    Attempts to establish a connection with the foreign server desired by the client.
    """
    ver, cmd = struct.unpack("!BB", await reader.readexactly(2))
    await reader.readexactly(2)
    if ver != SOCKS_VERSION:
        raise ValueError("bad version in request")

    raw = await reader.readexactly(4)
    taddr = socket.inet_ntop(socket.AF_INET, raw)
    tport = struct.unpack("!H", await reader.readexactly(2))[0]

    try:
        treader, twriter = await asyncio.open_connection(taddr, tport)
    except OSError as e:
        await reply(writer, REP_CONN_REFUSED)
        raise ValueError(f"connect to {taddr}:{tport} failed: {e}")

    await reply(writer, REP_SUCCESS)

    return treader, twriter, f"{taddr}:{tport}"


async def main():
    ap = argparse.ArgumentParser(description="SOCKS5 server (CONNECT only and no auth)")
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1080)
    args = ap.parse_args()

    server = await asyncio.start_server(handle_client, args.bind, args.port)
    print(f"[i] SOCKS5 server listening on {args.bind}:{args.port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
