#!/bin/env python

from request import Request
import requests
import select
import socket
import sys
import re

HOST = 'localhost'
PORT = 8887
BUFFER_SIZE = 8192
inputs, outputs = ([], [])
request_regex = re.compile(r'^(\w+) (.*) (.*)[\n|\r|\n\r]')
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
relay_connections_clients = {}
relay_connections_servers = {}


def handle_https_data(server, incoming_socket, data):
    global inputs, outputs, relay_connections_clients, relay_connections_servers
    print('Handling HTTPS data')
    if incoming_socket in relay_connections_clients.keys():
        print('Data from client')
        active_connection = relay_connections_clients[incoming_socket]
        active_connection['remote_socket'].send(data)
    elif incoming_socket in relay_connections_servers.keys():
        print('Data from server')
        active_connection = relay_connections_servers[incoming_socket]
        active_connection['client_socket'].send(data)
    else:
        print('Error: socket not in active_connection')
        print(incoming_socket)

def handle_http_request(server, incoming_socket, data):
    global inputs, outputs, relay_connections_clients, relay_connections_servers
    raw_request = data
    print('Raw: \n%s' % data)
    match = request_regex.match(raw_request)
    if match:
        request = Request(match, raw_request)
        print(request)
        url = f'{request.scheme}://{request.destination}' if 'http' not in request.destination else request.destination
        print('URL: ', url)
        r = requests.get(url, headers=request.headers, stream=True)
        if request.scheme == 'http':
            response = r.content
            print('Sending response : %s' % response)
            incoming_socket.send(response)
            incoming_socket.close()
        else:
            if request.method == 'CONNECT':
                response = b'HTTP/1.1 200 Connection established\r\n\r\n'
                print('Sending response : %s' % response)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((request.destination.replace(':443', ''), 443))
                relay_connections_clients[incoming_socket] = {
                    "request": request,
                    "remote_socket": s
                }
                relay_connections_servers[s] = {
                    "request": request,
                    "client_socket": incoming_socket
                }
                print('Created socket %s for %s' %(s, incoming_socket))
                outputs.append(s)
                inputs.append(s)
                incoming_socket.send(response)
                return
            else:
                response = b'HTTP/1.0 301 Moved Permanently\r\nLocation: http://monip.org/\r\n\r\n'
                print('Sending response : %s' % response)
                incoming_socket.send(response)
                incoming_socket.close()
        if incoming_socket in outputs:
            outputs.remove(incoming_socket)
        if incoming_socket in inputs:
            inputs.remove(incoming_socket)


def handle_readable(server, readable):
    global inputs, outputs
    for s in readable:
        if s is server:
            connection, client_address = s.accept()
            print("[%s] connected" % client_address[0])
            connection.setblocking(0)
            inputs.append(connection)
        else:
            try:
                data = s.recv(BUFFER_SIZE)
                try:
                    decoded = data.decode()
                    if decoded:
                        handle_http_request(server, s, decoded)
                except Exception as e:
                    print(e)
                    if data:
                        handle_https_data(server, s, data)
            except Exception as e:
                print(e)
                if s in outputs:
                    outputs.remove(s)
                    inputs.remove(s)
                    s.close()


def handle_exceptional(server, exceptional):
    global inputs, outputs
    for s in exceptional:
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()


def main():
    global inputs, outputs, server
    server.setblocking(0)
    server.bind((HOST, PORT))
    server.listen(5)
    inputs.append(server)
    print('Proxy listening on %s:%s' % (HOST, PORT))

    while inputs:
        readable, writable, exceptional = select.select(
            inputs, outputs, inputs)
        handle_readable(server, readable)
        # handle_writable(server, writable)
        handle_exceptional(server, exceptional)
    return 0


if __name__ == '__main__':
    try:
        exit(main())
    except KeyboardInterrupt as e:
        print('Closing server...')
        server.close()
        exit(0)
