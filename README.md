# tunneling-and-SOCKS5
  ## Programs

  This repo contains three small tools used throughout the talk to demonstrate pivoting, port forwarding, and tunneling.

  ### `socks5.py`

  A minimal SOCKS5 server (CONNECT command only, no authentication). It accepts client connections, reads the target address/port from the SOCKS5 request, opens a connection to that target,
  and relays traffic bidirectionally between client and target.
  **Usage:**
  ```bash
  python3 socks5.py [--bind ADDRESS] [--port PORT]
  - --bind — address to listen on (default: 127.0.0.1)
  - --port — port to listen on (default: 1080)
  ```
  Example:
  ```bash
  python3 socks5.py --bind 0.0.0.0 --port 1080
  ```
  mux_server (tcp-tunnel/server)

  The tunnel endpoint that runs on the attacker's machine. It listens for an incoming tunnel connection, wraps it in a yamux server session, and exposes a local SOCKS5 entry point on
  127.0.0.1:1080. Every connection accepted there is relayed through a new multiplexed stream inside the tunnel.

  Usage:
  ```bash
  ./mux_server [--bind ADDRESS] [--port PORT]
  - --bind — address to listen on for the incoming tunnel connection (default: 127.0.0.1)
  - --port — port to listen on for the incoming tunnel connection (default: 8080)
  ```
  Example:
  ```bash
  ./mux_server --bind 0.0.0.0 --port 443
  ```
  mux_client (tcp-tunnel/client)

  The tunnel endpoint that runs on the pivot host. It dials out to mux_server, establishes a yamux client session over that connection, and serves a real SOCKS5 backend (via go-socks5) on
  every stream the server opens through the session — so the pivot host ends up acting as the actual SOCKS5 server, reachable through the tunnel.

  Usage:
  ```bash
  ./mux_client [--server ADDRESS] [--port PORT]
  - --server — address of the mux_server to connect to (default: 127.0.0.1)
  - --port — port of the mux_server to connect to (default: 8080)
  ```
  Example:
  ```bash
  ./mux_client --server 203.0.113.99 --port 443
  ```
