from urllib.parse import urlunparse, urljoin
import re
import pandas as pd
import json
import base64

"""
From connection settings in MindsDB to an EventStoreDB AtomPub HTTP URL
#https://python.readthedocs.io/en/stable/library/urllib.parse.html#urllib.parse.urlunparse
"""


def build_basic_url(scheme, host, port):
    netloc = host + ":" + str(port)
    url = urlunparse([
        scheme,
        netloc,
        "", "", "", ""])
    return url


def build_health_url(basic_url):
    return urljoin(basic_url, "/health/live")


def build_streams_url(basic_url):
    return urljoin(basic_url, "streams/%24streams")


def build_stream_url(basic_url, stream_name):
    return urljoin(basic_url, "streams/" + stream_name)  # TODO: quote stream_name?


def build_stream_url_last_event(basic_url, stream_name):
    return urljoin(basic_url, "streams/" + stream_name + "/head/backward/1")


def build_next_url(link_url, read_batch_size):
    return re.sub(r"/(\d+)$", "/" + str(read_batch_size), link_url)


def entry_to_df(entry):
    # All events in EventStoreDB have the following:
    # Combine event fields directly after normalizing data for efficiency
    data = pd.json_normalize(json.loads(entry['data']), sep='_')
    data.insert(0, 'eventNumber', entry['eventNumber'])
    data.insert(0, 'eventType', entry['eventType'])
    data.insert(0, 'eventId', entry['eventId'])
    return data


def get_auth_string(username, password):
    credentials = username + ':' + password
    return 'Basic ' + str(base64.b64encode(credentials.encode('utf-8')).decode('utf-8'))
