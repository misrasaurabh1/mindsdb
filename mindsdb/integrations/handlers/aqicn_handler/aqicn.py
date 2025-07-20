import requests


class AQIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.params = {"token": api_key}
        self.base_endpoint = "https://api.waqi.info/feed"

    def make_request(self, url, additionalParams={}):
        # Avoid mutable default argument
        if additionalParams is None:
            additionalParams = {}
        combined_params = self.params.copy()
        combined_params.update(additionalParams)
        resp = requests.get(url, params=combined_params)
        res = resp.json()
        # Only call .json() once
        if res["status"] == "ok":
            return {"content": res, "code": 200}
        else:
            return {"content": res, "code": 404}

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
