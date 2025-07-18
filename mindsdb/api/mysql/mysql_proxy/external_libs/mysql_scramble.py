"""
MIT License
============
Copyright (c) 2010, 2013 PyMySQL contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import hashlib
from functools import partial
import struct
import sys

"""
MIT License
============
Copyright (c) 2010, 2013 PyMySQL contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

PYPY = hasattr(sys, "pypy_translation_info")
JYTHON = sys.platform.startswith("java")
IRONPYTHON = sys.platform == "cli"
CPYTHON = not PYPY and not JYTHON and not IRONPYTHON

range_type = range
text_type = str
long_type = int
str_type = str
unichr = chr

sha_new = partial(hashlib.new, "sha1")


def scramble(password, message):
    SCRAMBLE_LENGTH = 20
    stage1 = sha_new(password.encode("utf-8")).digest()
    stage2 = sha_new(stage1).digest()
    s = sha_new()
    s.update(message[:SCRAMBLE_LENGTH].encode("utf-8"))
    s.update(stage2)
    result = s.digest()
    return _my_crypt(result, stage1)


def _my_crypt(message1, message2):
    length = len(message1)
    result = b""
    for i in range_type(length):
        x = struct.unpack("B", message1[i : i + 1])[0] ^ struct.unpack("B", message2[i : i + 1])[0]
        result += struct.pack("B", x)
    return result


# old_passwords support ported from libmysql/password.c
SCRAMBLE_LENGTH_323 = 8


class RandStruct_323(object):
    def __init__(self, seed1, seed2):
        self.max_value = 0x3FFFFFFF
        self.seed1 = seed1 % self.max_value
        self.seed2 = seed2 % self.max_value

    def my_rnd(self):
        self.seed1 = (self.seed1 * 3 + self.seed2) % self.max_value
        self.seed2 = (self.seed1 + self.seed2 + 33) % self.max_value
        return self.seed1 / self.max_value  # remove redundant float()


def scramble_323(password, message):
    hash_pass = _hash_password_323(password)
    hash_message = _hash_password_323(message[:SCRAMBLE_LENGTH_323])
    hash_pass_n = struct.unpack(">LL", hash_pass)
    hash_message_n = struct.unpack(">LL", hash_message)

    rand_st = RandStruct_323(hash_pass_n[0] ^ hash_message_n[0], hash_pass_n[1] ^ hash_message_n[1])
    scramble_len = min(SCRAMBLE_LENGTH_323, len(message))
    out = bytearray(scramble_len)
    for i in range_type(scramble_len):
        out[i] = int(rand_st.my_rnd() * 31) + 64
    extra = int(rand_st.my_rnd() * 31)
    # XOR with extra
    for i in range(len(out)):
        out[i] ^= extra
    return bytes(out)


def _hash_password_323(password):
    nr = 1345345333
    add = 7
    nr2 = 0x12345671

    # hash bytes that are not space (' ', '\t', 32, 9)
    for x in password:
        b = byte2int(x)
        if b not in (32, 9):  # 32=' ', 9='\t'
            nr ^= (((nr & 63) + add) * b) + (nr << 8)
            nr &= 0xFFFFFFFF
            nr2 = (nr2 + ((nr2 << 8) ^ nr)) & 0xFFFFFFFF
            add = (add + b) & 0xFFFFFFFF

    r1 = nr & ((1 << 31) - 1)  # kill sign bits
    r2 = nr2 & ((1 << 31) - 1)
    return struct.pack(">LL", r1, r2)


def byte2int(b):
    if isinstance(b, int):
        return b
    else:
        return struct.unpack("!B", b)[0]


def int2byte(i):
    return struct.pack("!B", i)


def join_bytes(bs):
    if len(bs) == 0:
        return ""
    else:
        rv = bs[0]
        for b in bs[1:]:
            rv += b
        return rv
