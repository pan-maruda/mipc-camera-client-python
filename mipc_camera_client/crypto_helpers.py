"""
"cryptography" to talk to MIPC webcams

most of this is re-implementing stuff I think the JS code on web UI does:
do NOT take this as an example, this is not secure, but it's necessary to talk to the cameras :/
"""
import hashlib
import logging
import random
from typing import Any, Union
from Crypto.Cipher import DES

# hardcoded in the js client
DH_PRIME = 791658605174853458830696113306796803
DH_ROOT = 5

BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
ALT_BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"


def dh_gen_private() -> int:
    return random.randint(0, 2**63)


def dh_gen_public(private) -> int:
    return pow(DH_ROOT, private, mod=DH_PRIME)


def dh_shared_secret(c, a) -> str:
    return str(pow(int(c), int(a), mod=DH_PRIME))


def dh_req_data(public_key, tid):
    return {
        "dbnum_prime": str(DH_PRIME),
        "droot_num": str(DH_ROOT),
        "dkey_a2b": str(public_key),
        "dtid": tid,
    }


LOGGER = logging.getLogger(__name__)


def _js_ternary(cond, a, b):
    """sorry python (a if cond else b) was making my head spin"""
    if cond:
        return a
    else:
        return b


def _magic_e(a):
    """
    probably hex ascii to int conversion?
    """
    return _js_ternary(
        48 <= a and 57 >= a,
        a - 48,
        _js_ternary(
            65 <= a and 71 >= a, a - 55, _js_ternary(97 <= a and 102 >= a, a - 87, 0)
        ),
    )


def _encode_magic(string_or_int: Union[str, int], left_pad_to_lenth: int = 0) -> str:
    """who knows. reversed from js :)"""
    f = ""
    if isinstance(string_or_int, str):
        if string_or_int.startswith("0x"):
            l = str(string_or_int)
            b = len(l) - 1
            while 1 < b:
                d, g = 0, 0
                while 8 > d and 1 < b:
                    g += _js_lsh(_magic_e(_js_charCodeAt(l, b)), d)
                    b -= 1
                    d += 4
                f = chr(g) + f
    elif isinstance(string_or_int, int):
        a = string_or_int
        b = 24

        while 0 <= b:
            if a >= 1 << b:
                f += chr(_js_rsh(a, b) & 255)
            b -= 8
    else:
        raise TypeError(f"{type(string_or_int)} only string or int are supported")

    while len(f) < left_pad_to_lenth:
        f = chr(0) + f
    return f


def _crappy_md5(s):
    """emulating minified js md5-ish"""
    bs = bytes(ord(c) & ((1 << 8) - 1) for c in s)
    return hashlib.md5(bs).hexdigest()


def format_nid(a: int, c: str, e: str, g: int, f, l):
    """
    some magic formatting for the nid, it's "not really base64", based on minified js
    """
    hash = _crappy_md5
    s = lambda code: chr(code & 0xFFFF)

    a = _encode_magic(a)
    r = _encode_magic(c) if c else ""
    c = _encode_magic(g) if c else ""
    l = _encode_magic("0x" + hash(l)) if l else ""
    f = (
        (s(64 + len(a)) + a if a else "")
        + (s(96 + len(r)) + r if r else "")
        + (s(128 + len(c)) + c if c else "")
        + (s(160 + len(f)) + f if f else "")
    )
    e = f + (s(0 + len(e)) + e if e else "") + (s(0 + len(l)) + l if l else "")
    calculated_md5 = "0x" + hash(e)
    s_md5 = _encode_magic(calculated_md5)

    return str_2_b64(s(32 + len(s_md5)) + s_md5 + f, 1)


def _js_lsh(a, b):
    return (a & 0xFFFFFFFF) << ((b & 0xFFFFFFFF) & 0x1F)


def _js_rsh(a, b):
    return (a & 0xFFFFFFFF) >> ((b & 0xFFFFFFFF) & 0x1F)


def _js_charCodeAt(s: str, idx):
    utf16_bytes = s.encode("utf-16-le")
    lower = utf16_bytes[idx * 2]
    upper = utf16_bytes[idx * 2 + 1]
    return (upper << 8) + lower


def str_2_b64(inputStr, altChars=None):
    """reversed from minified js. some kind of variation on base64 but weird"""
    b = 0
    e = 0
    index = 0
    l = ""
    str_len = len(inputStr)
    b64Chars = ALT_BASE64_CHARS if altChars else BASE64_CHARS
    while index < str_len:
        d = 0
        while 24 > d and index < str_len:
            ccode = _js_charCodeAt(inputStr, index)
            b = _js_lsh(b, 8) + ccode
            d += 8
            index += 1
        g = 0
        while 24 > g:
            # for loop body
            e = d - g - 6
            b64_char_idx = _js_lsh(b, -e) if e < 0 else _js_rsh(b, e)
            l += b64Chars[b64_char_idx] if g < d else ""
            # for incr part
            g += 6
            b &= _js_lsh(1, d - g) - 1

    return l


def des_encrypt_password_hash(pass_md5_hex_str: str, secret: str):
    """some serious cryptography, i think. emulating js again"""
    pass_md5_bytes = bytes.fromhex(pass_md5_hex_str)
    des_iv = bytes.fromhex("0000000000000000")

    des_key = hashlib.md5(secret.encode("utf-8")).digest()[0:8]
    des = DES.new(key=des_key, IV=des_iv, mode=DES.MODE_CBC)
    return des.encrypt(pass_md5_bytes).hex()


def hash_password(password):
    return _crappy_md5(password)
