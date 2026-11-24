package main

import (
    "log"
    "net"
		"fmt"
		"flag"
		"github.com/armon/go-socks5"
    "github.com/hashicorp/yamux"
)


// main connects to the tunnel server over TCP, opens a yamux client session
// on that connection, and serves a SOCKS5 proxy on every stream the server
// opens through the session.
func main() {
    server := flag.String("server", "127.0.0.1", "server address")
    port := flag.Int("port", 8080, "server port")
    flag.Parse()
    saddr := fmt.Sprintf("%s:%d", *server, *port)
    rawConn, err := net.Dial("tcp", saddr)
    if err != nil {
        log.Fatalf("[E] Connection to the tunnel server failed: %w", err)
    }
    session, err:= yamux.Client(rawConn, nil)
        if err!=nil {
            rawConn.Close()
            return
        }
            defer session.Close()
        socksSrv, _ := socks5.New(&socks5.Config{})
        for {
            stream, err := session.Accept()
            if err != nil {
                break
            }
            go socksSrv.ServeConn(stream)
        }
}
