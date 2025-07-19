from typing import Union


def strip_null_byte(x: Union[str, bytes], encoding=None):
    if type(x) == bytes:
        if encoding is None:
            encoding = "UTF-8"
        x = x.decode(encoding=encoding)
    # Use rstrip for speed instead of regex
    # remove all trailing whitespace and null bytes
    return x.rstrip("\x00 \t\r\n")
