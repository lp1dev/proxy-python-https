#!/bin/env python

from request import Request
import requests
import select
import socket
import sys
import re

HOST = 'localhost' if not len(sys.argv) > 1 else sys.argv[1]
PORT = 8887 if not len(sys.argv) > 2 else int(sys.argv[2])
BUFFER_SIZE = 8192
inputs, outputs = ([], [])
request_regex = re.compile(r'^(\w+) (.*) (.*)[\n|\r|\n\r]')
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
relay_connections_clients = {}
relay_connections_servers = {}

def handle_https_data(server, incoming_socket, data):
    if incoming_socket in relay_connections_clients.keys():
        active_connection = relay_connections_clients[incoming_socket]
        active_connection['remote_socket'].send(data)
        print('[%s] -> [%s] (https-stream)' %(incoming_socket.getsockname()[0], active_connection['request'].destination))
    elif incoming_socket in relay_connections_servers.keys():
        active_connection = relay_connections_servers[incoming_socket]
        active_connection['client_socket'].send(data)
        print('[%s] -> [%s] (https-stream)' %(active_connection['request'].destination, incoming_socket.getsockname()[0]))        

def handle_http_request(server, incoming_socket, data):
    raw_request = data
    match = request_regex.match(raw_request)
    if match:
        request = Request(match, raw_request)
        if request.scheme == 'http':
            url = f'{request.scheme}://{request.destination}' if 'http' not in request.destination else request.destination
            r = requests.get(url, headers=request.headers, stream=True, allow_redirects=False)
            response = r.content
            incoming_socket.send(response)
            incoming_socket.close()
            inputs.remove(incoming_socket)            
            if incoming_socket in outputs:
                outputs.remove(incoming_socket)
            print('[%s] -> %s [%s] (http)' %(incoming_socket.getsockname()[0], request.method, url))
        elif request.scheme == 'https' and request.method == 'CONNECT':
            response = b'HTTP/1.1 200 Connection established\r\n\r\n'
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((request.destination.replace(':443', ''), 443))
            relay_connections_clients[incoming_socket] = {"request": request, "remote_socket": s}
            relay_connections_servers[s] = {"request": request, "client_socket": incoming_socket}
            outputs.append(s)
            inputs.append(s)
            incoming_socket.send(response)
            print('[%s] -> %s [%s] (https)' %(incoming_socket.getsockname()[0], request.method, request.destination))
                

def handle_readable(server, readable):
    for s in readable:
        if s is server:
            connection, client_address = s.accept()
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
                    if data and 'codec can\'t decode byte' in str(e):
                        handle_https_data(server, s, data)
                    else:
                        print(e)
            except Exception as e:
                print(e)
                if s in outputs:
                    outputs.remove(s)
                    inputs.remove(s)
                    s.close()

def handle_exceptional(server, exceptional):
    for s in exceptional:
        inputs.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()

def main():
    server.setblocking(0)
    server.bind((HOST, PORT))
    server.listen(5)
    inputs.append(server)
    print('Proxy server listening on %s:%s' % (HOST, PORT))
    while inputs:
        readable, writable, exceptional = select.select(
            inputs, outputs, inputs)
        handle_readable(server, readable)
        handle_exceptional(server, exceptional)
    return 0

if __name__ == '__main__':
    try:
        exit(main())
    except KeyboardInterrupt as e:
        print('Closing server...')
        server.close()
        exit(0)
