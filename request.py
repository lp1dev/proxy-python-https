class Request():
    def __init__(self, match, raw_request):
      self.method = match.group(1)
      self.scheme = 'https' if self.method == 'CONNECT' else 'http'
      self.destination = match.group(2)
      self.protocol = match.group(3)
      self.headers = self.parse_headers(match, raw_request)

    def parse_headers(self, match, raw_request):
        raw_headers = raw_request.replace(match.group(0), '')
        headers_list = [header.replace('\r', '').replace(':', '', 1).split(
            ' ', 1) for header in raw_headers.split('\n')]
        headers = {}
        for header in headers_list:
          if len(header) > 1 and header[0]:
            headers[header[0]] = header[1]
        print('headers', headers)
        return headers

    def __str__(self):
      return f'{self.method} {self.scheme}://{self.destination}'
