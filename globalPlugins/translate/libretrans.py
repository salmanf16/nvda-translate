# *-* coding: utf-8 *-*
import json
import urllib.parse
import http.client


class LibreConnectionManager:
	def __init__(self):
		self.conn = None
		self.last_host = None

	def get_conn(self, host, scheme):
		if self.conn is None or self.last_host != host:
			if self.conn:
				try:
					self.conn.close()
				except Exception:
					pass
			if scheme == "http":
				self.conn = http.client.HTTPConnection(host, timeout=5)
			else:
				self.conn = http.client.HTTPSConnection(host, timeout=5)
			self.last_host = host
		return self.conn

	def request_translate(self, text, to_language, source_language="auto", url="http://localhost:5000", api_key=""):
		parsed = urllib.parse.urlparse(url)
		host = parsed.netloc
		scheme = parsed.scheme
		path = parsed.path.rstrip("/") + "/translate"

		payload = {
			"q": text,
			"source": source_language,
			"target": to_language,
		}
		if api_key:
			payload["api_key"] = api_key

		data = json.dumps(payload).encode("utf-8")
		headers = {
			"Content-Type": "application/json",
			"Connection": "keep-alive"
		}

		for attempt in range(2):
			try:
				conn = self.get_conn(host, scheme)
				conn.request("POST", path, body=data, headers=headers)
				resp = conn.getcall_resp = conn.getcall_resp = conn.getresponse()
				if resp.status == 200:
					result_data = resp.read().decode("utf-8")
					result = json.loads(result_data)
					return result.get("translatedText", "")
				else:
					resp.read()
			except Exception:
				if self.conn:
					try:
						self.conn.close()
					except Exception:
						pass
				self.conn = None
		return ""


_manager = LibreConnectionManager()


def translate(text, to_language, source_language="auto", url="http://localhost:5000", api_key=""):
	return _manager.request_translate(text, to_language, source_language, url, api_key)
