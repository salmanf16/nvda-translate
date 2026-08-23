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
    ENDPOINTS = [
        ("clients5.google.com", "/translate_a/t?client=dict-chrome-ex&sl=%s&tl=%s&q=%s"),
        ("clients5.google.com", "/translate_a/single?client=at&sl=%s&tl=%s&dt=t&q=%s"),
        ("translate.google.com", "/translate_a/t?client=dict-chrome-ex&sl=%s&tl=%s&q=%s"),
        ("translate.googleapis.com", "/translate_a/single?client=gtx&sl=%s&tl=%s&dt=t&q=%s"),
    ]

    def __init__(self):
        self.conns = {}
        self.last_timeout = None

    def get_conn(self, host, timeout=5):
        if self.last_timeout != timeout:
            for h, c in list(self.conns.items()):
                try:
                    c.close()
                except Exception:
                    pass
            self.conns.clear()
            self.last_timeout = timeout

        conn = self.conns.get(host)
        if conn is None:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
            self.conns[host] = conn
        return conn

    def _parse_response(self, data):
        if not data:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            # Format 1: dict-chrome-ex -> [["translated text", "detected_lang"], ...]
            if isinstance(first, list) and len(first) > 0 and isinstance(first[0], str):
                parts = []
                for item in data:
                    if isinstance(item, list) and len(item) > 0 and isinstance(item[0], str):
                        parts.append(item[0])
                    elif isinstance(item, str):
                        parts.append(item)
                if parts:
                    return "".join(parts)
            # Format 2: single?client=at / client=gtx -> [[["chunk1", "orig1", ...], ...]]
            if isinstance(first, list) and len(first) > 0 and isinstance(first[0], list):
                parts = []
                for chunk in first:
                    if isinstance(chunk, list) and len(chunk) > 0 and isinstance(chunk[0], str):
                        parts.append(chunk[0])
                    elif isinstance(chunk, str):
                        parts.append(chunk)
                if parts:
                    return "".join(parts)
        return ""

    def request_translate(self, to_translate, to_language="auto", from_language="auto", timeout=5):
        to_translate_quoted = urllib.parse.quote(to_translate)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Connection": "keep-alive"
        }

        for host, path_template in self.ENDPOINTS:
            path = path_template % (from_language, to_language, to_translate_quoted)
            for attempt in range(2):
                try:
                    conn = self.get_conn(host, timeout=timeout)
                    conn.request("GET", path, headers=headers)
                    resp = conn.getresponse()
                    if resp.status == 200:
                        data_bytes = resp.read()
                        data = json.loads(data_bytes.decode("utf-8"))
                        res = self._parse_response(data)
                        if res:
                            return res
                    else:
                        resp.read()  # Clear socket buffer
                        if resp.status == 429:
                            # Endpoint rate-limited, move immediately to next endpoint
                            break
                except Exception:
                    # Reset connection for this host on error
                    old_conn = self.conns.pop(host, None)
                    if old_conn:
                        try:
                            old_conn.close()
                        except Exception:
                            pass
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
