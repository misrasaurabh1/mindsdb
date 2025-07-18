import json
import requests


class LumaClient:
    def __init__(self, api_key):
        self.auth_token = api_key
        self.luma_base_endpoint = "https://api.lu.ma/"
        self._base_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-luma-api-key": self.auth_token,
        }
        self.validate_api_key()

    def make_request(self, url, method="GET", payload=None):
        if method not in ("GET", "POST"):
            raise ValueError("Invalid HTTP request method")
        # Use base headers directly (dictionary reuse, faster than recreating each call)
        request_method = requests.get if method == "GET" else requests.post
        resp = request_method(url, json=payload, headers=self._base_headers)
        code = resp.status_code
        content = resp.json()
        return {"content": content, "code": code}

    def validate_api_key(self):
        url = f"{self.luma_base_endpoint}public/v1/user/get-self"
        content = self.make_request(url)
        if content["code"] != 200:
            raise Exception("User Authentication failed - " + json.dumps(content["content"]))
        return content

    def create_event(self, data):
        url = f"{self.luma_base_endpoint}public/v1/event/create"
        content = self.make_request(url, method="POST", payload=data)
        if content["code"] != 200:
            raise Exception("Create failed - " + json.dumps(content["content"]))
        return content

    def get_event(self, event_api_id):
        url = f"{self.luma_base_endpoint}public/v1/event/get?api_id={event_api_id}"
        content = self.make_request(url)
        if content["code"] != 200:
            raise Exception("Get event failed - " + json.dumps(content["content"]))
        return content

    def list_events(self):
        url = f"{self.luma_base_endpoint}public/v1/calendar/list-events?series_mode=sessions"
        content = self.make_request(url)
        if content["code"] != 200:
            raise Exception("Get event failed - " + json.dumps(content["content"]))
        return content
