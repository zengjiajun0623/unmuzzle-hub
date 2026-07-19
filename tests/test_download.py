import hashlib
import os

import pytest

from unmuzzle.download import DownloadError, download_file, sha256_file

from helpers import serve


@pytest.fixture
def server(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    payload = os.urandom(300_000)  # spans multiple chunks at test chunk size
    (src / "weights.bin").write_bytes(payload)
    srv, base = serve(src)
    yield base, payload
    srv.shutdown()


def test_download_multichunk(server, tmp_path):
    base, payload = server
    dest = tmp_path / "out" / "weights.bin"
    sha = hashlib.sha256(payload).hexdigest()
    download_file([base], "weights.bin", dest, len(payload), sha,
                  jobs=4, chunk_size=64 * 1024)
    assert dest.read_bytes() == payload
    assert not (dest.parent / "weights.bin.parts").exists()


def test_download_resumes_from_parts(server, tmp_path):
    base, payload = server
    dest = tmp_path / "weights.bin"
    sha = hashlib.sha256(payload).hexdigest()
    chunk = 64 * 1024
    # pre-seed the first chunk as if a previous run was interrupted
    parts = tmp_path / "weights.bin.parts"
    parts.mkdir()
    (parts / "000000").write_bytes(payload[:chunk])
    download_file([base], "weights.bin", dest, len(payload), sha,
                  jobs=2, chunk_size=chunk)
    assert dest.read_bytes() == payload


def test_checksum_mismatch_raises(server, tmp_path):
    base, payload = server
    dest = tmp_path / "weights.bin"
    with pytest.raises(DownloadError, match="sha256 mismatch"):
        download_file([base], "weights.bin", dest, len(payload), "0" * 64,
                      jobs=2, chunk_size=64 * 1024)
    assert not dest.exists()


def test_mirror_failover(server, tmp_path):
    base, payload = server
    dest = tmp_path / "weights.bin"
    sha = hashlib.sha256(payload).hexdigest()
    download_file(["http://127.0.0.1:1/dead", base], "weights.bin",
                  dest, len(payload), sha, jobs=2, chunk_size=128 * 1024)
    assert dest.read_bytes() == payload


def test_existing_verified_file_skips(server, tmp_path):
    base, payload = server
    dest = tmp_path / "weights.bin"
    dest.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    assert sha256_file(dest) == sha
    download_file(["http://127.0.0.1:1/dead"], "weights.bin", dest,
                  len(payload), sha)  # would fail if it tried the network
    assert dest.read_bytes() == payload
