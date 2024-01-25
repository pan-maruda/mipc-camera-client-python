import pytest

from mipc_camera_client.crypto_helpers import format_nid, str_2_b64, _encode_magic

b64_examples = [
    ("abcde", "YWJjZGU"),
    (
        "1234567890qwertyuiop[asdfghjklxcvbnm,",
        "MTIzNDU2Nzg5MHF3ZXJ0eXVpb3BbYXNkZmdoamtseGN2Ym5tLA",
    ),
    ("dupa gowno xD", "ZHVwYSBnb3dubyB4RA"),
]


@pytest.mark.parametrize("input,expected", b64_examples)
def test_str_2_b64(input, expected):
    assert str_2_b64(input) == expected


nid_examples = [
    {
        "args": {
            "a": "\u0003Z",
            "c": "",
            "e": "B\u0003Za\u0003$575577999316286149171440385503499294",
            "g": 0,
            "f": "B\u0003Za\u0003",
            "l": "",
        },
        "out": "MPOL2S4EWHJMGgDnbmy.0mmlQgNaYQM",
    },
    {
        "args": {
            "a": "\u0003[",
            "c": "",
            "e": "B\u0003[a\u0003$575577999316286149171440385503499294",
            "g": 0,
            "f": "B\u0003[a\u0003",
            "l": "",
        },
        "out": "MMFqdAf6h7hJUU2I2KEsf7WlQgNbYQM",
    },
    {
        "args": {
            "a": "\u0003\\",
            "c": "",
            "e": "B\u0003\\a\u0003$575577999316286149171440385503499294",
            "g": 0,
            "f": "B\u0003\\a\u0003",
            "l": "",
        },
        "out": "MELTIskn44eG7hjSnP9ViEGlQgNcYQM",
    },
    {
        "args": {
            "a": "\u0003]",
            "c": "",
            "e": "B\u0003]a\u0003$575577999316286149171440385503499294",
            "g": 0,
            "f": "B\u0003]a\u0003",
            "l": "",
        },
        "out": "MOp5oXUi.p5TtyTEuATEtaylQgNdYQM",
    },
    {
        "args": {
            "a": 1,
            "c": "0x4c",
            "e": "703713319380997337899942106288320558",
            "g": 2,
            "f": None,
            "l": None,
        },
        "out": "MJWmqRxu9aPNYxEC4eM2SIhBAWFMgQI",
    },
    {
        "args": {
            "a": 492,
            "c": "0x1e",
            "e": "703713319380997337899942106288320558",
            "g": 0,
            "f": None,
            "l": None,
        },
        "out": "MMIDV4iPq89YTLcaU7x.9XNCAexhHg",
    },
    {
        "args": {
            "a": 1,
            "c": "0x56",
            "e": "592275261678845367857716440229997215",
            "g": 2,
            "f": None,
            "l": None,
        },
        "out": "MEzMeLwVc7uJmDkHM7jcZ_tBAWFWgQI",
    },
]


@pytest.mark.parametrize(
    "e", nid_examples, ids=lambda e: ", ".join(map(repr, e["args"].values()))
)
def test_nid(e):
    assert format_nid(**e["args"]) == e["out"]


encode_examples = [
    (1, "\x01"),
    ("0x4c", "L"),
    ("0x4C", "L"),
    (2, "\x02"),
    ("", ""),
    (492, "\x01ì"),
    ("0x1e", "\x1E"),
    ("0x56", "V"),
]


@pytest.mark.parametrize(
    "input,out",
    encode_examples,
)
def test_encode(input, out):
    assert _encode_magic(input) == out
