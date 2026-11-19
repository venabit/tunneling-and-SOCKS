package main

import (
    "os"
    "io"
    "log"
    "net"
    "fmt"
    "flag"
    "github.com/hashicorp/yamux"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Subcomando requerido: 'server' o 'client'")
		os.Exit(1)
	}

	switch os.Args[1] {
	case "server":
        serverFlags := flag.NewFlagSet("server", flag.ExitOnError)
        bind := flag.String("bind", "127.0.0.1", "bind address")
    	port := flag.Int("port", 8080, "server port")
		serverFlags.Parse(os.Args[2:])
        laddr := fmt.Sprintf("%s:%d", *bind, *port)
        handleClients(laddr)
	case "client":
		clientFlags := flag.NewFlagSet("client", flag.ExitOnError)
        server := flag.String("server", "127.0.0.1", "server address")
        port := flag.Int("port", 8080, "server port")
		clientFlags.Parse(os.Args[2:])
        saddr := fmt.Sprintf("%s:%d", *bind, *port)
        connect(saddr)
	default:
		fmt.Fprintf(os.Stderr, "Subcomando desconocido: %q (usa 'server' o 'client')\n", os.Args[1])
		os.Exit(1)
	}
}


func handleClients(string laddr) {
	listener, err := net.Listen("tcp", laddr)
	if err != nil {
		log.Fatal(err)
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


func connect(string saddr) {
    rawConn, err := net.Dial("tcp", saddr)
    if err != nil {
        log.Fatal("[E] Connection to the tunnel server failed", err)
    }
}

func handleTunnelSession(rawConn net.Conn) {
    session, err := yamux.Server(rawConn, nil)
    if err != nil {
        log.Println("[E] Error starting the yamux session ", err)
        rawConn.Close()
        return
    }
    defer session.Close()
    for {
        stream, err := session.Accept()
        if err != nil {
            log.Println("Session closed", err)
            return
        }

        // Por cada stream, conectamos al destino final (ej. puerto 8000)
        go forwardToTarget(stream, "127.0.0.1:8000")
    }
}

func forwardToTarget(stream net.Conn, targetAddr string) {
    defer stream.Close()

    targetConn, err := net.Dial("tcp", targetAddr)
    if err != nil {
        log.Println("No se pudo conectar al destino:", err)
        return
    }
    defer targetConn.Close()

    // 5. Copia bidireccional: todo lo que entra por el stream va al destino y viceversa
    go io.Copy(targetConn, stream)
    io.Copy(stream, targetConn)
}
