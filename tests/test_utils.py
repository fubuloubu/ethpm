from ethpm_types.utils import compute_checksum


def test_compute_checksum():
    content = b"this is content"
    actual = compute_checksum(content)
    assert actual.startswith("0x")
