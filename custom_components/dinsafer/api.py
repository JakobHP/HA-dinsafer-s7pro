"""Internal DinSafer API client used by the integration."""

from __future__ import annotations

import binascii
import json
import time
from dataclasses import dataclass
from typing import Any, cast

import requests

try:
    import snappy  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency in runtime environment
    snappy = None

APP_ID = "naimo8Faeshoori5hooshieng6iedong"
APP_SECRET = "Zee1weereth9phooD4yi5pheifeecoow"
BASE_URL = "https://api-nx.plutomen.com"
DEFAULT_TIMEOUT = 20


class DinsaferError(RuntimeError):
    """Raised when the DinSafer API returns an error."""


class DinsaferProtocolError(DinsaferError):
    """Raised when the DinSafer API response cannot be decoded."""


class DinsaferDecodeError(DinsaferProtocolError):
    """Raised when encrypted DinSafer payloads cannot be decoded."""


@dataclass
class RequestResult:
    """Container for a decoded API response."""

    endpoint: str
    mode: str
    body_text: str
    payload: dict[str, Any] | list[Any] | str | int | float | bool | None


def java_gmtime() -> int:
    """Mirror the gmtime format used by the mobile app."""

    return (time.time_ns() // 1_000_000) * 1_000_000


def rc4_crypt(key: bytes, data: bytes) -> bytes:
    """Encrypt or decrypt bytes with RC4."""

    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]

    i = 0
    j = 0
    output = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        output.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(output)


def rc4_encrypt_hex(key: str, data: bytes) -> str:
    """RC4-encrypt bytes and return the hex payload."""

    return binascii.hexlify(rc4_crypt(key.encode("utf-8"), data)).decode("ascii")


def rc4_decrypt_hex(key: str, hex_data: str) -> bytes:
    """Decode an RC4-encrypted hex payload."""

    encrypted = binascii.unhexlify(hex_data.strip())
    return rc4_crypt(key.encode("utf-8"), encrypted)


def looks_like_hex(value: str) -> bool:
    """Return whether a string is valid even-length hex."""

    if not value or len(value) % 2 != 0:
        return False

    try:
        binascii.unhexlify(value)
    except (binascii.Error, ValueError):
        return False
    return True


def _decode_json_bytes(data: bytes) -> dict[str, Any] | list[Any] | str:
    """Decode UTF-8 bytes into JSON, falling back to raw text."""

    text = data.decode("utf-8")
    try:
        return cast(dict[str, Any] | list[Any], json.loads(text))
    except json.JSONDecodeError:
        return text


class DinsaferClient:
    """Minimal DinSafer HTTP client used by the integration."""

    def __init__(self, *, email: str, password: str, debug: bool = False) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "DinSafer-PoC/1.0",
                "X-Online-Host": "api-nx.plutomen.com",
            }
        )
        self.email = email
        self.password = password
        self.debug = debug
        self.token: str | None = None

    def _build_json_field(self, payload: dict[str, Any]) -> str:
        """Build the encrypted form payload expected by the API."""

        payload_with_gmtime = dict(payload)
        payload_with_gmtime["gmtime"] = java_gmtime()
        plain = json.dumps(payload_with_gmtime, separators=(",", ":"), ensure_ascii=False)
        return rc4_encrypt_hex(APP_SECRET, plain.encode("utf-8"))

    def _build_token_field(self, token: str, include_suffix: bool) -> str:
        """Build the encrypted token form field."""

        logical_token = f"{token}_{java_gmtime()}" if include_suffix else token
        return rc4_encrypt_hex(APP_SECRET, logical_token.encode("utf-8"))

    def _decode_response(self, response_text: str) -> tuple[str, dict[str, Any] | list[Any] | str]:
        """Decode a response body from the DinSafer API."""

        body = response_text.strip()
        if not body:
            raise DinsaferProtocolError("Empty response body")

        if body.startswith("{") or body.startswith("["):
            try:
                return "plain-json", cast(dict[str, Any] | list[Any], json.loads(body))
            except json.JSONDecodeError as exc:
                raise DinsaferDecodeError(f"Invalid JSON response: {exc}") from exc

        decrypted = rc4_decrypt_hex(APP_SECRET, body)
        if snappy is not None:
            try:
                decompressed = snappy.decompress(decrypted)
                if isinstance(decompressed, str):
                    decompressed = decompressed.encode("utf-8")
                return "rc4+snappy", cast(dict[str, Any] | list[Any] | str, _decode_json_bytes(decompressed))
            except Exception:
                pass

        try:
            return "rc4", cast(dict[str, Any] | list[Any] | str, _decode_json_bytes(decrypted))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DinsaferDecodeError(f"Unable to decode encrypted response: {exc}") from exc

    def _decode_embedded_result(self, payload: dict[str, Any] | list[Any] | str) -> dict[str, Any] | list[Any] | str:
        """Decode encrypted Result payloads returned inside JSON responses."""

        if not isinstance(payload, dict):
            return payload

        result = payload.get("Result")
        if not isinstance(result, str) or not looks_like_hex(result):
            return payload

        decoded = rc4_decrypt_hex(APP_SECRET, result.upper())
        if snappy is not None:
            try:
                decompressed = snappy.decompress(decoded)
                if isinstance(decompressed, str):
                    decompressed = decompressed.encode("utf-8")
                payload["Result"] = _decode_json_bytes(decompressed)
                return payload
            except Exception:
                pass

        try:
            payload["Result"] = _decode_json_bytes(decoded)
        except UnicodeDecodeError as exc:
            raise DinsaferDecodeError(f"Unable to decode embedded Result payload: {exc}") from exc
        return payload

    def post(
        self,
        endpoint: str,
        *,
        json_payload: dict[str, Any] | None = None,
        token: str | None = None,
        include_token_suffix: bool = True,
    ) -> RequestResult:
        """POST to the DinSafer API and return the decoded response."""

        url = f"{BASE_URL}{endpoint}"
        form_data: dict[str, str] = {"gm": "1"}

        if json_payload is not None:
            form_data["json"] = self._build_json_field(json_payload)

        if token is not None:
            form_data["token"] = self._build_token_field(token, include_token_suffix)

        try:
            response = self.session.post(url, data=form_data, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise DinsaferError(f"Network failure calling {endpoint}: {exc}") from exc

        if response.status_code >= 400:
            raise DinsaferError(f"HTTP {response.status_code} calling {endpoint}: {response.text[:500]}")

        try:
            mode, payload = self._decode_response(response.text)
            payload = self._decode_embedded_result(payload)
        except (DinsaferDecodeError, binascii.Error, ValueError) as exc:
            raise DinsaferProtocolError(f"Failed to decode {endpoint} response: {exc}") from exc

        return RequestResult(endpoint=endpoint, mode=mode, body_text=response.text, payload=payload)

    def login(self) -> dict[str, Any]:
        """Authenticate and store the returned token."""

        result = self.post(
            f"/user/login/{APP_ID}",
            json_payload={"email": self.email, "password": self.password},
        )

        data = result.payload
        status = data.get("Status") if isinstance(data, dict) else None
        token = None
        if isinstance(data, dict):
            result_obj = data.get("Result")
            if isinstance(result_obj, dict):
                token_value = result_obj.get("token")
                if isinstance(token_value, str):
                    token = token_value

        if status != 1 or not token:
            raise DinsaferError(f"Login failed: status={status}, response={data}")

        self.token = token
        return cast(dict[str, Any], data)

    def list_homes(self) -> list[dict[str, Any]]:
        """Return the homes available to the authenticated account."""

        if not self.token:
            raise DinsaferError("Cannot list homes without a login token")

        result = self.post(
            f"/home/list-homes/{APP_ID}",
            json_payload={},
            token=self.token,
            include_token_suffix=True,
        )

        data = result.payload
        status = data.get("Status") if isinstance(data, dict) else None
        if status != 1:
            raise DinsaferError(f"list_homes failed: status={status}, response={data}")

        if isinstance(data, dict):
            result_obj = data.get("Result")
            if isinstance(result_obj, dict):
                homes = result_obj.get("list_homes")
                if isinstance(homes, list):
                    return [home for home in homes if isinstance(home, dict)]

        return []


class DinsaferWebSocketClient:
    """Minimal credential/state container kept for integration compatibility."""

    def __init__(self, email: str, password: str, debug: bool = False) -> None:
        self.email = email
        self.password = password
        self.debug = debug
        self.token: str | None = None
        self.user_id: str | None = None
        self.home_id: str | None = None
        self.device_id: str | None = None
        self.device_token: str | None = None
        self._http_client = DinsaferClient(email=email, password=password, debug=debug)

    @property
    def http_client(self) -> DinsaferClient:
        """Return the shared HTTP client instance."""

        return self._http_client
