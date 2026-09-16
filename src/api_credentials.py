"""Secure API-key storage for the OpenAI-compatible teaching provider."""

from __future__ import annotations

import os
from typing import Any


_CREDENTIAL_TARGET = "NoteManager/OpenAICompatibleAPI"
_CREDENTIAL_USERNAME = "NoteManager"


class CredentialStorageError(RuntimeError):
    """Raised when Windows Credential Manager cannot be accessed."""


def _win32cred() -> Any:
    if os.name != "nt":
        raise CredentialStorageError("当前系统不支持 Windows 凭据管理器。")
    try:
        import win32cred
    except ImportError as exc:
        raise CredentialStorageError(
            "缺少 Windows 凭据支持，请安装 requirements.txt 中的 pywin32。"
        ) from exc
    return win32cred


def _is_not_found(exc: Exception) -> bool:
    code = getattr(exc, "winerror", None)
    if code is None and getattr(exc, "args", None):
        code = exc.args[0]
    return code == 1168


def _decode_blob(blob: object) -> str:
    if isinstance(blob, str):
        return blob.strip()
    if isinstance(blob, bytes):
        encoding = "utf-16-le" if b"\x00" in blob else "utf-8"
        return blob.decode(encoding).rstrip("\x00").strip()
    return ""


def load_saved_api_key() -> str | None:
    """Read the saved key without exposing it through application settings."""
    win32cred = _win32cred()
    try:
        credential = win32cred.CredRead(
            _CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0
        )
    except Exception as exc:
        if _is_not_found(exc):
            return None
        raise CredentialStorageError("无法读取 Windows 凭据管理器中的 API Key。") from exc
    key = _decode_blob(credential.get("CredentialBlob"))
    return key or None


def save_api_key(api_key: str) -> None:
    """Persist a key encrypted by Windows for the current user account."""
    key = api_key.strip()
    if not key:
        raise ValueError("API Key 不能为空。")
    if len(key) > 2048 or any(character.isspace() for character in key):
        raise ValueError("API Key 格式无效。")

    win32cred = _win32cred()
    credential = {
        "Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": _CREDENTIAL_TARGET,
        "UserName": _CREDENTIAL_USERNAME,
        "CredentialBlob": key,
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        "Comment": "NoteManager OpenAI-compatible API credential",
    }
    try:
        win32cred.CredWrite(credential, 0)
    except Exception as exc:
        raise CredentialStorageError("无法将 API Key 保存到 Windows 凭据管理器。") from exc


def delete_saved_api_key() -> bool:
    """Delete the NoteManager credential, returning whether one was removed."""
    win32cred = _win32cred()
    try:
        win32cred.CredDelete(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except Exception as exc:
        if _is_not_found(exc):
            return False
        raise CredentialStorageError("无法删除 Windows 凭据管理器中的 API Key。") from exc


def get_api_key() -> str | None:
    """Let an explicit process environment override the persisted GUI key."""
    environment = os.environ.get("OPENAI_API_KEY", "").strip()
    if environment:
        return environment
    return load_saved_api_key()


def api_key_source() -> str:
    """Return a non-secret description token for the active credential source."""
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "environment"
    if load_saved_api_key():
        return "windows"
    return "missing"


__all__ = [
    "CredentialStorageError",
    "api_key_source",
    "delete_saved_api_key",
    "get_api_key",
    "load_saved_api_key",
    "save_api_key",
]
