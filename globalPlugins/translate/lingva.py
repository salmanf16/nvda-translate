# *-* coding: utf-8 *-*
import json
import urllib.parse
import http.client


class LingvaConnectionManager:
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

	def request_translate(self, text, to_language, source_language="auto", instance_url=None):
		if instance_url is None:
			instance_url = "https://lingva.ml"

		parsed = urllib.parse.urlparse(instance_url)
		host = parsed.netloc
		scheme = parsed.scheme
		base_path = parsed.path.rstrip("/")

		encoded_text = urllib.parse.quote(text)
		path = "%s/api/v1/%s/%s/%s" % (base_path, source_language, to_language, encoded_text)
		
		headers = {
			"User-Agent": "NVDATranslateAddon/1.0",
			"Connection": "keep-alive"
		}
		
		for attempt in range(2):
			try:
				conn = self.get_conn(host, scheme)
				conn.request("GET", path, headers=headers)
				resp = conn.getresponse()
				if resp.status == 200:
					data = resp.read().decode("utf-8")
					result = json.loads(data)
					return result.get("translation", "")
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


_manager = LingvaConnectionManager()


def translate(text, to_language, source_language="auto", instance_url=None):
	return _manager.request_translate(text, to_language, source_language, instance_url)
