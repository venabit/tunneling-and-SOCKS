package main

import (
    "io"
    "log"
    "net"

    "github.com/hashicorp/yamux"
)

func main() {
    saddr := fmt.Sprintf("%s:%d", *bind, *port)
    rawConn, err := net.Dial("tcp", saddr)
    if err != nil {
        log.Fatal("[E] Connection to the tunnel server failed", err)
    }

    session, err := yamux.Client(rawConn, nil)
    if err != nil {
        log.Fatal(err)
    }
    defer session.Close()
    log.Println("Túnel establecido hacia :9000")

    // 3. Abrir puerto local :8080 para recibir tráfico de aplicaciones locales
    localListener, err := net.Listen("tcp", ":8080")
    if err != nil {
        log.Fatal(err)
    }
    defer localListener.Close()
    log.Println("Escuchando tráfico local en :8080")

    for {
        localConn, err := localListener.Accept()
        if err != nil {
            log.Println("Error aceptando conexión local:", err)
            continue
        }

        go handleLocalConnection(session, localConn)
    }
}

func handleLocalConnection(session *yamux.Session, localConn net.Conn) {
    defer localConn.Close()

    // 4. Abrir un nuevo stream virtual dentro del túnel existente (sin hacer handshake TCP nuevo)
    stream, err := session.Open()
    if err != nil {
        log.Println("Error abriendo stream en el túnel:", err)
        return
    }
    defer stream.Close()

    // 5. Puente bidireccional entre el socket local y el stream de yamux
    go io.Copy(stream, localConn)
    io.Copy(localConn, stream)
}
