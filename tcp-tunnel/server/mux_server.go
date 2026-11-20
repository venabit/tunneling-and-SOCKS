package main

import (
    "io"
    "log"
    "net"
    "fmt"
    "flag"
    "github.com/hashicorp/yamux"
)


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


func handleTunnelSession(rawConn net.Conn) {
	session, err := yamux.Server(rawConn, nil)
	if err != nil {
		log.Printf("[E] Error starting the tunnel: %v", err)
		rawConn.Close()
		return
	}
	defer session.Close()

	socksEntry, err := net.Listen("tcp", "127.0.0.1:1080")
	if err != nil {
		log.Printf("[E] Error listening on 127.0.0.1:1080: %v", err)
		return
	}
	defer socksEntry.Close()

	for {
		conn, err := socksEntry.Accept()
		if err != nil {
			log.Println("[E] Accept error:", err)
			return
		}
		go relay(conn, session)
	}
}

func relay(conn net.Conn, session *yamux.Session) {
	defer conn.Close()

	stream, err := session.Open()
	if err != nil {
		log.Printf("[E] Error opening stream: %v", err)
		return
	}
	defer stream.Close()

	go io.Copy(stream, conn)
	io.Copy(conn, stream)
}
