#!/usr/bin/env python3
"""Bridge Claude Desktop to JEB MCP Server on localhost:8851"""
import socket
import sys
import threading

PORT = 8851

def stdin_to_socket(sock):
    try:
        sock_file = sock.makefile('w')
        for line in sys.stdin:
            print(f"[Bridge] -> {line.strip()[:100]}", file=sys.stderr)
            sock_file.write(line)
            sock_file.flush()
    except Exception as e:
        print(f"stdin error: {e}", file=sys.stderr)
    finally:
        sock.shutdown(socket.SHUT_WR)

def socket_to_stdout(sock):
    try:
        sock_file = sock.makefile('r')
        for line in sock_file:
            print(f"[Bridge] <- {line.strip()[:100]}", file=sys.stderr)
            sys.stdout.write(line)
            sys.stdout.flush()
    except Exception as e:
        print(f"socket error: {e}", file=sys.stderr)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(('localhost', PORT))
        print(f"Connected to JEB on port {PORT}", file=sys.stderr)
    except Exception as e:
        print(f"Can't connect to JEB on port {PORT}: {e}", file=sys.stderr)
        print("Make sure JEB is running with the MCP server script loaded!", file=sys.stderr)
        sys.exit(1)

    # bidirectional bridge
    t1 = threading.Thread(target=stdin_to_socket, args=(sock,))
    t2 = threading.Thread(target=socket_to_stdout, args=(sock,))
    t1.daemon = t2.daemon = True
    t1.start()
    t2.start()

    try:
        t1.join()
        t2.join()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()

if __name__ == "__main__":
    main()