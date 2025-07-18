import os
from typing import Any

import pandas as pd
import requests
from mindsdb_sql_parser import parse_sql
from mindsdb_sql_parser import ast

from mindsdb.api.executor.data_types.response_type import RESPONSE_TYPE
from mindsdb.integrations.utilities.handlers.query_utilities import SELECTQueryParser, SELECTQueryExecutor
from mindsdb.integrations.libs.api_handler import APIHandler, APITable
from mindsdb.integrations.libs.response import HandlerResponse, HandlerStatusResponse
from mindsdb.integrations.utilities.sql_utils import extract_comparison_conditions
from mindsdb.utilities.config import Config


class PirateWeatherAPIBaseTable(APITable):
    allowed_select_keys = {}
    columns = []
    table_name = ""

    def __init__(self, handler: "PirateWeatherAPIHandler"):
        super().__init__(handler)

    def select(self, query: ast.Select) -> pd.DataFrame:
        """Select data from the collected weather data and return it as a pandas DataFrame.

        Args:
            query (ast.Select): The SQL query to be executed.

        Returns:
            pandas.DataFrame: A pandas DataFrame containing the selected data.
        """
        conditions = extract_comparison_conditions(query.where)

        params = {}
        for op, arg1, arg2 in conditions:
            if arg1 in self.allowed_select_keys:
                if op == "=":
                    params[arg1] = arg2
                else:
                    raise NotImplementedError(f"Operator for argument {arg1} is not supported: {op}")

        if "latitude" not in params or "longitude" not in params:
            raise ValueError("Latitude and longitude are required")

        result = self.handler.call_application_api(method_name=self.table_name, params=params)

        # Reparse the query and run through SELECTQueryExecutor
        query_parser = SELECTQueryParser(query, table=self.table_name, columns=self.get_columns())
        selected_columns, where_conditions, order_by_conditions, result_limit = query_parser.parse_query()

        # Remove request parameters from where conditions
        where_conditions = [c for c in where_conditions if c[1] not in self.allowed_select_keys]

        query_executor = SELECTQueryExecutor(
            result, selected_columns, where_conditions, order_by_conditions, result_limit
        )

        return query_executor.execute_query()

    def get_columns(self) -> list:
        return self.columns


class PiratePirateWeatherAPIHourlyTable(PirateWeatherAPIBaseTable):
    allowed_select_keys = {"latitude", "longitude", "time", "units"}
    columns = [
        "localtime",
        "icon",
        "summary",
        "precipAccumulation",
        "precipType",
        "temperature",
        "apparentTemperature",
        "dewPoint",
        "pressure",
        "windSpeed",
        "windBearing",
        "cloudCover",
        "latitude",
        "longitude",
        "timezone",
        "offset",
    ]
    table_name = "hourly"


class PiratePirateWeatherAPIDailyTable(PirateWeatherAPIBaseTable):
    allowed_select_keys = {"latitude", "longitude", "time", "units"}

    columns = [
        "localtime",
        "icon",
        "summary",
        "sunriseTime",
        "sunsetTime",
        "moonPhase",
        "precipAccumulation",
        "precipType",
        "temperatureHigh",
        "temperatureHighTime",
        "temperatureLow",
        "temperatureLowTime",
        "apparentTemperatureHigh",
        "apparentTemperatureHighTime",
        "apparentTemperatureLow",
        "apparentTemperatureLowTime",
        "dewPoint",
        "pressure",
        "windSpeed",
        "windBearing",
        "cloudCover",
        "temperatureMin",
        "temperatureMinTime",
        "temperatureMax",
        "temperatureMaxTime",
        "apparentTemperatureMin",
        "apparentTemperatureMinTime",
        "apparentTemperatureMax",
        "apparentTemperatureMaxTime",
        "latitude",
        "longitude",
        "timezone",
        "offset",
    ]
    table_name = "daily"


class PirateWeatherAPIHandler(APIHandler):
    query_string_template = "https://timemachine.pirateweather.net/forecast/{api_key}/{latitude},{longitude}"

    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self._tables = {}

        args = kwargs.get("connection_data", {})
        handler_config = Config().get("weather_handler", {})

        connection_args = {}

        for k in ["api_key"]:
            if k in args:
                connection_args[k] = args[k]
            elif f"WEATHER_{k.upper()}" in os.environ:
                connection_args[k] = os.environ[f"WEATHER_{k.upper()}"]
            elif k in handler_config:
                connection_args[k] = handler_config[k]

        self._api_key = connection_args["api_key"]

        # Register tables
        self._register_table("hourly", PiratePirateWeatherAPIHourlyTable(self))
        self._register_table("daily", PiratePirateWeatherAPIDailyTable(self))

    def _register_table(self, table_name: str, table_class: Any):
        self._tables[table_name] = table_class

    def connect(self) -> HandlerStatusResponse:
        return HandlerStatusResponse(success=True)

    def check_connection(self) -> HandlerStatusResponse:
        # Avoid unnecessary allocations and use a prebuilt params dict, don't recreate object or string formatting
        response = HandlerStatusResponse(False)
        try:
            # Use a literal for params, avoiding dict constructor cost
            daily_params = {"latitude": 51.507351, "longitude": -0.127758, "time": "1672578052"}
            self.call_application_api(method_name="daily", params=daily_params)
            response.success = True
        except Exception as e:
            response.error_message = str(e)
        return response

    def native_query(self, query: Any):
        ast = parse_sql(query)
        table = str(ast.from_table)
        data = self._tables[table].select(ast)
        return HandlerResponse(RESPONSE_TYPE.TABLE, data_frame=data)

    def call_application_api(self, method_name: str = None, params: dict = None) -> pd.DataFrame:
        # Fast checks
        if method_name not in ("hourly", "daily"):
            raise NotImplementedError(f"Method {method_name} is not implemented")
        if "latitude" not in params or "longitude" not in params:
            raise ValueError("Latitude and longitude are required")

        # Avoid constructing and replacing exclude string on every call - precompute exclude map
        exclude_param = {
            "hourly": "currently,minutely,alerts,daily",
            "daily": "currently,minutely,alerts,hourly",
        }
        _exclude_val = exclude_param[method_name]
        opt_params = {"exclude": _exclude_val}
        units = params.get("units")
        if units:
            opt_params["units"] = units

        # Efficient query building - avoid string concatenation in loop
        base_url = self.query_string_template.format(
            api_key=self._api_key, latitude=params["latitude"], longitude=params["longitude"]
        )
        if "time" in params:
            base_url = f"{base_url},{params['time']}"
        # Filter opt_params that have a value and build the query string directly
        query_args = "&".join([f"{k}={v}" for k, v in opt_params.items() if v])
        query = f"{base_url}?{query_args}"

        # Call the API
        resp = requests.get(query)
        resp.raise_for_status()
        data = resp.json()

        if method_name not in data:
            raise ValueError(
                f"API response did not contain {method_name} data. Check your API key. Got response: {data}"
            )

        # Fast DataFrame construction: avoid DataFrame.assign (copies each time), use constructor directly.
        # Add all fields in the dict at construction, then assign localtime in-place.
        extra_cols = {
            "latitude": params["latitude"],
            "longitude": params["longitude"],
            "timezone": data["timezone"],
            "offset": data["offset"],
        }
        wx_data = data[method_name]["data"]
        nrows = len(wx_data)
        # Pre-extend dicts
        if nrows > 0:
            # Avoid slow assign; build DataFrame with all known columns at once for best performance
            # Convert each dict to a single extended dict (shallow copy, include extra_cols)
            def _add_extra(row, extra=extra_cols):
                r = row.copy()
                r.update(extra)
                return r

            rows = [_add_extra(row) for row in wx_data]
            df = pd.DataFrame(rows)
            times = df["time"].values
            tz = data["timezone"]
            # Use pd.to_datetime vectorized and assign in one go, avoid creating intermediate Series
            localtime = pd.to_datetime(times, utc=True, unit="s").tz_convert(tz)
            df["localtime"] = localtime
            # Use inplace drop without errors if "time" is not present
            df.drop(columns="time", inplace=True, errors="ignore")
        else:
            # Handle empty data case: construct empty DataFrame with expected columns for compatibility
            df = pd.DataFrame(columns=["localtime", "latitude", "longitude", "timezone", "offset"])
        return df
