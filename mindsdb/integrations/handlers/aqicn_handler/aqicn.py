import requests


class AQIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.params = {"token": api_key}
        self.base_endpoint = "https://api.waqi.info/feed"

    def make_request(self, url, additionalParams={}):
        # Avoid mutable default; prepare merged params efficiently.
        if additionalParams:
            merged_params = self.params.copy()
            merged_params.update(additionalParams)
        else:
            merged_params = self.params
        resp = requests.get(url, params=merged_params)
        res = resp.json()
        # Use parsed result, avoid repeated json parsing
        if res["status"] == "ok":
            content = {"content": res, "code": 200}
        else:
            content = {"content": res, "code": 404}
        return content

    def air_quality_city(self, city):
        url = f"{self.base_endpoint}/{city}/"
        return self.make_request(url)

    def air_quality_lat_lng(self, lat, lng):
        url = f"{self.base_endpoint}/geo:{lat};{lng}/"
        return self.make_request(url)

    def air_quality_user_location(self):
        url = f"{self.base_endpoint}/here/"
        return self.make_request(url)

    def air_quality_station_by_name(self, name):
        url = "https://api.waqi.info/search/"
        return self.make_request(url, {"keyword": name})
