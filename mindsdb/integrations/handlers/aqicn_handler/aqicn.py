import requests


class AQIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.params = {"token": api_key}
        self.base_endpoint = "https://api.waqi.info/feed"

    def make_request(self, url, additionalParams={}):
        # Avoid using mutable default argument
        if additionalParams:
            # Only create a new dict when needed
            newParams = self.params.copy()
            newParams.update(additionalParams)
        else:
            newParams = self.params
        resp = requests.get(url, params=newParams)
        res_json = resp.json()
        if res_json["status"] == "ok":
            return {"content": res_json, "code": 200}
        else:
            return {"content": res_json, "code": 404}

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
