"""Small HTTP service that exposes a TIFF member of a public ZIP as HTTPS.

The service never downloads the complete archive. It discovers the ZIP central
directory with HTTP Range requests and then streams only the selected member.
It is intentionally limited to public AWS S3 HTTPS objects to reduce SSRF risk.

Deploy this service somewhere publicly reachable by OAM, then set
OAM_ARCHIVE_PROXY_BASE_URL in the Streamlit app environment.
"""

from __future__ import annotations

import io
import os
import struct
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

import requests

MAX_TAIL_BYTES = 4 * 1024 * 1024
MAX_DIRECTORY_BYTES = 16 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
REQUEST_TIMEOUT = 60
ALLOWED_S3_HOST_RE = __import__("re").compile(
    r"^[a-z0-9][a-z0-9.-]*\\.s3(?:[.-][a-z0-9-]+)?\\.amazonaws\\.com$",
    __import__("re").IGNORECASE,
)


class ArchiveError(Exception):
    pass


def validate_archive_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not ALLOWED_S3_HOST_RE.fullmatch(parsed.netloc):
        raise ArchiveError("archive_url must be a public HTTPS AWS S3 object URL")


def _range_get(url: str, start: int, end: int) -> requests.Response:
    response = requests.get(
        url,
        headers={"Range": f"bytes={start}-{end}"},
        timeout=REQUEST_TIMEOUT,
        stream=True,
    )
    if response.status_code != 206:
        response.close()
        raise ArchiveError(f"S3 object did not honor HTTP Range request ({response.status_code})")
    return response


def _head(url: str) -> int:
    validate_archive_url(url)
    response = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    response.raise_for_status()
    length = response.headers.get("Content-Length")
    if not length:
        raise ArchiveError("S3 object did not provide Content-Length")
    return int(length)


def _find_eocd(tail: bytes, absolute_start: int) -> tuple[int, int]:
    signature = b"PK\\x05\\x06"
    pos = tail.rfind(signature)
    if pos < 0 or len(tail) - pos < 22:
        raise ArchiveError("ZIP end-of-central-directory record not found")
    comment_len = struct.unpack_from("<H", tail, pos + 20)[0]
    if len(tail) - pos < 22 + comment_len:
        raise ArchiveError("Incomplete ZIP end-of-central-directory record")
    disk, cd_disk, entries_disk, entries, cd_size, cd_offset = struct.unpack_from(
        "<HHHHII", tail, pos + 4
    )
    if disk or cd_disk or entries_disk != entries:
        raise ArchiveError("Multi-disk ZIP archives are not supported")
    # ZIP64 has sentinel values here. Fail explicitly instead of guessing.
    if entries == 0xFFFF or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF:
        raise ArchiveError("ZIP64 archives are not supported by this endpoint")
    return cd_offset, cd_size


def _central_directory(url: str, size: int) -> bytes:
    tail_size = min(size, MAX_TAIL_BYTES)
    tail_response = _range_get(url, size - tail_size, size - 1)
    try:
        tail = tail_response.content
    finally:
        tail_response.close()
    cd_offset, cd_size = _find_eocd(tail, size - tail_size)
    if cd_size > MAX_DIRECTORY_BYTES:
        raise ArchiveError("ZIP central directory exceeds configured limit")
    response = _range_get(url, cd_offset, cd_offset + cd_size - 1)
    try:
        return response.content
    finally:
        response.close()


def find_member(url: str, member_name: str) -> dict:
    size = _head(url)
    directory = _central_directory(url, size)
    stream = io.BytesIO(directory)
    wanted = member_name.lstrip("/").replace("\\", "/")
    while True:
        signature = stream.read(4)
        if not signature:
            break
        if signature != b"PK\\x01\\x02":
            raise ArchiveError("Malformed ZIP central directory")
        fixed = stream.read(42)
        if len(fixed) != 42:
            raise ArchiveError("Truncated ZIP central-directory entry")
        (
            _made_by,
            _needed,
            flags,
            method,
            _mtime,
            _mdate,
            _crc,
            compressed_size,
            uncompressed_size,
            name_len,
            extra_len,
            comment_len,
            _disk,
            _internal_attr,
            _external_attr,
            local_offset,
        ) = struct.unpack("<HHHHHHIIIHHHHHII", fixed)
        name = stream.read(name_len).decode("utf-8", "replace")
        stream.seek(extra_len + comment_len, io.SEEK_CUR)
        if name == wanted:
            return {
                "archive_size": size,
                "method": method,
                "flags": flags,
                "compressed_size": compressed_size,
                "uncompressed_size": uncompressed_size,
                "local_offset": local_offset,
                "name": name,
            }
    raise ArchiveError(f"ZIP member not found: {wanted}")


def member_data_offset(url: str, member: dict) -> int:
    response = _range_get(url, member["local_offset"], member["local_offset"] + 29)
    try:
        header = response.content
    finally:
        response.close()
    if len(header) != 30 or header[:4] != b"PK\\x03\\x04":
        raise ArchiveError("Invalid ZIP local-file header")
    name_len, extra_len = struct.unpack_from("<HH", header, 26)
    return member["local_offset"] + 30 + name_len + extra_len


def iter_stored(url: str, offset: int, size: int):
    if size == 0:
        return
    response = _range_get(url, offset, offset + size - 1)
    try:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:
                yield chunk
    finally:
        response.close()


def iter_deflated(url: str, offset: int, compressed_size: int):
    decompressor = zlib.decompressobj(-15)
    response = _range_get(url, offset, offset + compressed_size - 1)
    try:
        for chunk in response.iter_content(CHUNK_SIZE):
            if not chunk:
                continue
            data = decompressor.decompress(chunk)
            if data:
                yield data
        tail = decompressor.flush()
        if tail:
            yield tail
    finally:
        response.close()


def stream_member(url: str, member: dict):
    offset = member_data_offset(url, member)
    method = member["method"]
    if method == 0:
        yield from iter_stored(url, offset, member["compressed_size"])
    elif method == 8:
        yield from iter_deflated(url, offset, member["compressed_size"])
    else:
        raise ArchiveError(f"Unsupported ZIP compression method: {method}")


class Handler(BaseHTTPRequestHandler):
    server_version = "OAMArchiveProxy/0.1"

    def _params(self):
        params = parse_qs(urlsplit(self.path).query)
        archive_url = params.get("archive_url", [None])[0]
        member = params.get("member", [None])[0]
        if not archive_url or not member:
            raise ArchiveError("archive_url and member query parameters are required")
        validate_archive_url(archive_url)
        if not member.lower().endswith((".tif", ".tiff")):
            raise ArchiveError("member must be a TIFF path")
        return archive_url, member

    def do_HEAD(self):
        try:
            archive_url, member_name = self._params()
            member = find_member(archive_url, member_name)
            if member["method"] not in (0, 8):
                raise ArchiveError(f"Unsupported ZIP compression method: {member['method']}")
            self.send_response(200)
            self.send_header("Content-Type", "image/tiff")
            self.send_header("Content-Length", str(member["uncompressed_size"]))
            self.send_header("Content-Disposition", f'inline; filename="{quote(member_name.rsplit("/", 1)[-1])}"')
            self.end_headers()
        except Exception as exc:
            self.send_error(400, str(exc))

    def do_GET(self):
        try:
            archive_url, member_name = self._params()
            member = find_member(archive_url, member_name)
            if member["method"] not in (0, 8):
                raise ArchiveError(f"Unsupported ZIP compression method: {member['method']}")
            self.send_response(200)
            self.send_header("Content-Type", "image/tiff")
            self.send_header("Content-Length", str(member["uncompressed_size"]))
            self.send_header("Cache-Control", "public, max-age=300")
            self.end_headers()
            for chunk in stream_member(archive_url, member):
                self.wfile.write(chunk)
        except Exception as exc:
            if not self.wfile.closed:
                try:
                    self.send_error(400, str(exc))
                except Exception:
                    pass

    def log_message(self, format: str, *args):
        print(format % args)


def main() -> None:
    host = os.getenv("OAM_ARCHIVE_PROXY_HOST", "0.0.0.0")
    port = int(os.getenv("OAM_ARCHIVE_PROXY_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"OAM archive proxy listening on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
