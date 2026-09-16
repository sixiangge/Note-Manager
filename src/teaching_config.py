"""Non-secret settings for the optional teaching engine."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from src.api_credentials import CredentialStorageError, get_api_key


TEACHING_DEFAULTS = {
    "teach_provider": "disabled",
    "teach_model": "",
    "teach_base_url": "http://localhost:11434",
    "teach_timeout": 60,
    "teach_top_k": 5,
    "teach_chunk_size": 500,
    "teach_external_first": True,
    "teach_include_samples": False,
    "teach_use_system_proxy": False,
    "teach_max_file_mb": 20,
    "teach_allowed_types": ".pdf,.pptx,.docx,.txt",
}


@dataclass(frozen=True)
class TeachingConfig:
    """Connection and retrieval preferences; never holds an API key."""

    provider: str = "disabled"
    model: str = ""
    base_url: str = "http://localhost:11434"
    timeout: int = 60
    top_k: int = 5
    chunk_size: int = 500
    external_first: bool = True
    include_samples: bool = False
    use_system_proxy: bool = False
    max_file_mb: int = 20
    allowed_types: str = ".pdf,.pptx,.docx,.txt"

    @classmethod
    def from_settings(cls, settings: dict) -> "TeachingConfig":
        """Read only allowlisted, non-secret teaching preferences."""
        return cls(**{key.removeprefix("teach_"): settings.get(key, default)
                      for key, default in TEACHING_DEFAULTS.items()})

    def validate(self) -> None:
        """Reject disabled, unsafe or incomplete preferences."""
        if self.provider not in {"local", "api"}:
            raise ValueError("请先在设置 → 教学与模型中启用模型提供方。")
        if not self.model.strip():
            raise ValueError("请填写模型名称。")
        url = urlsplit(self.base_url)
        if url.scheme not in {"http", "https"} or not url.hostname:
            raise ValueError("服务地址必须为 HTTP(S) URL。")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("服务地址不能包含凭据、查询参数或片段。")
        if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("非本机服务必须使用 HTTPS，以保护资料与密钥。")
        if not 1 <= self.top_k <= 20 or not 100 <= self.chunk_size <= 2000:
            raise ValueError("片段数量应为 1–20，分块长度应为 100–2000。")
        if not 5 <= self.timeout <= 300 or not 1 <= self.max_file_mb <= 100:
            raise ValueError("超时应为 5–300 秒，单文件上限应为 1–100 MB。")
        suffixes = set(self.allowed_types.lower().replace(" ", "").split(","))
        if not suffixes or not suffixes <= {".pdf", ".pptx", ".docx", ".txt"}:
            raise ValueError("允许类型仅支持 .pdf,.pptx,.docx,.txt，以逗号分隔。")
        if self.provider == "api":
            try:
                configured = bool(get_api_key())
            except CredentialStorageError as exc:
                raise ValueError(str(exc)) from exc
            if not configured:
                raise ValueError("请在设置 → 教学与模型中填写 API Key。")
