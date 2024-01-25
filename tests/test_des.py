from mipc_camera_client.crypto_helpers import des_encrypt_password_hash


def test_des_encrypt():
    examples = [
        {
            "password_hash": "935147339ce7ac869200843edf680e52",
            "shared_secret": "506541858342243857518660751045580499",
            "expected_output": "ee967df028d381239952f56e5449b9ae",
        },
        {
            "password_hash": "935147339ce7ac869200843edf680e52",
            "shared_secret": "289624237503866648313950369973381607",
            "expected_output": "f25305ccf732f641467ef3e42248323b",
        },
        {
            "password_hash": "935147339ce7ac869200843edf680e52",
            "shared_secret": "685352909022987075270888629610906893",
            "expected_output": "9fec308e8ee8a29426c4fd22cade4405",
        },
    ]

    for example in examples:
        assert (
            des_encrypt_password_hash(
                example["password_hash"], example["shared_secret"]
            )
            == example["expected_output"]
        )
