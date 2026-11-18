import argparse
import asycio
import socket
import struct

"""
To stablish the tunnel the client must send a message requesting a connection with the following format.

         +-----+----------+----------+
         | CMD | DLENGTH  |   DATA   |
         +-----+----------+----------+
 bytes   |  1  | Variable | DLENGTH  |
         +-----+----------+----------+

CMD:
   o CONNECT X'01'
   o DATA X'02' 
   o CLOSE X'03'


"""

#CMD 
CMD_CONNECT=0x1
CMD_DATA=0x2
CMD_CLOSE=0x3

async def check_request(reader, writer):
    """
    Attempts to establish a connection with the foreign server desired by the client.
    """
    cmd = struct.unpack("!B", await reader.readexactly(1))
    match cmd:
        case CMD_CONNECT:
            pass
        case CMD_DATA:
            pass
        case CMD_CLOSE:
             writer.close()
             await writer.wait_closed()
        case _:
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


async def handle_clients():
    """
    Handle each client Connection to the server.
    """
    peer = writer.get_extra_info("peername")
    print(f"[i] Connection from {peer}")
    try:
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
    print(f"[x] Connection from {peer} closed")


def main():
    ap = argparse.ArgumentParser(description="Minimal Multiplexed Raw TCP Tunnel")
    ap.add_arguemnt("--bind", default="127.0.0.1")
    ap.add_arguemnt("--port", type=int, default="60000")
    args = ap.parse_args()
    server = await asyncio.start_server(handle_client, args.bind, args.port)
