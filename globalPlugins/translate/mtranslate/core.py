#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2016 Arnaud Aliès

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
import urllib.parse
import http.client
import json
from html import unescape


class PersistentConnectionManager:
    def __init__(self):
        self.conn = None
        self.last_timeout = None

    def get_conn(self, timeout=5):
        if self.conn is None or self.last_timeout != timeout:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
            self.conn = http.client.HTTPSConnection("translate.googleapis.com", timeout=timeout)
            self.last_timeout = timeout
        return self.conn

    def request_translate(self, to_translate, to_language="auto", from_language="auto", timeout=5):
        to_translate_quoted = urllib.parse.quote(to_translate)
        path = "/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t&q=%s" % (from_language, to_language, to_translate_quoted)
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Connection": "keep-alive"
        }
        
        for attempt in range(2):
            try:
                connection = self.get_conn(timeout=timeout)
                connection.request("GET", path, headers=headers)
                resp = connection.getresponse()
                if resp.status == 200:
                    data_bytes = resp.read()
                    data = json.loads(data_bytes.decode("utf-8"))
                    parts = []
                    if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        for chunk in data[0]:
                            if chunk and isinstance(chunk, list) and len(chunk) > 0 and chunk[0]:
                                parts.append(chunk[0])
                    return "".join(parts)
                else:
                    resp.read()  # Consume response body to clear socket
            except Exception:
                # Reset connection on any exception (like closed socket due to idle timeout) and retry once
                if self.conn:
                    try:
                        self.conn.close()
                    except Exception:
                        pass
                self.conn = None
        return ""

_manager = PersistentConnectionManager()

def translate(to_translate, to_language="auto", from_language="auto", timeout=5):
    # Split text by lines to prevent context skipping/failures on multi-line text
    lines = to_translate.splitlines()
    translated_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            translated_lines.append(line)
            continue
        
        line_result = _manager.request_translate(stripped, to_language, from_language, timeout=timeout)
        if not line_result:
            return ""
        translated_lines.append(line_result)
        
    if "\r\n" in to_translate:
        return "\r\n".join(translated_lines)
    return "\n".join(translated_lines)
