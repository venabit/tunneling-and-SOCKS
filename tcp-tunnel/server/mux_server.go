package main

import (
    "io"
    "log"
    "net"
    "fmt"
    "flag"
    "github.com/hashicorp/yamux"
)


// main listens for incoming tunnel connections and dispatches each one to
// handleTunnelSession in its own goroutine.
func main() {
	bind := flag.String("bind", "127.0.0.1", "bind address")
	port := flag.Int("port", 8080, "server port")
	flag.Parse()
	laddr := fmt.Sprintf("%s:%d", *bind, *port)
	listener, err := net.Listen("tcp", laddr)
	if err != nil {
		log.Fatalf("[E] Error setting up the server: %w",err)
	}
	defer listener.Close()
	log.Printf("[i] Server listening on %s\n", laddr)
	for {
		rawConn, err := listener.Accept()
		if err != nil {
			log.Println("[E] Connection error:", err)
			continue
		}
		log.Printf("[i] Connection from %s established \n", rawConn.RemoteAddr())
		go handleTunnelSession(rawConn)
	}
}


// handleTunnelSession wraps rawConn in a yamux server session, then starts a
// local SOCKS5 entry point (127.0.0.1:1080) and relays every connection
// accepted there through a new stream on that session.
func handleTunnelSession(rawConn net.Conn) {
	tunnel, err := yamux.Server(rawConn, nil)
	if err != nil {
		log.Printf("[E] Error starting the tunnel: %v", err)
		rawConn.Close()
		return
	}
	defer tunnel.Close()

	socksEntry, err := net.Listen("tcp", "127.0.0.1:1080")
	if err != nil {
		log.Printf("[E] Error listening on 127.0.0.1:1080: %v", err)
		return
	}
	defer socksEntry.Close()

	for {
		client, err := socksEntry.Accept()
		if err != nil {
			log.Println("[E] Accept error:", err)
			return
		}
		go relay(client, tunnel)
	}
}

// relay opens a new stream in the tunnel and copies data bidirectionally
// between client stream and that stream until either side closes.
func relay(client net.Conn, tunnel *yamux.Session) {
	defer client.Close()

	stream, err := tunnel.Open()
	if err != nil {
		log.Printf("[E] Error opening stream: %v", err)
		return
	}
	defer stream.Close()

	go io.Copy(stream, client)
	io.Copy(client, stream)
}
