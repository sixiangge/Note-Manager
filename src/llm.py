"""Optional SDK adapters. Credentials are read only from the environment."""

from contextlib import contextmanager
from collections.abc import Iterator
import json
from urllib.parse import urlsplit

from src.teaching_config import TeachingConfig


@contextmanager
def _client(config: TeachingConfig) -> Iterator[object]:
    config.validate()
    # Never route local course material through a globally configured proxy.
    trust_env = urlsplit(config.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}
    try:
        if config.provider == "local":
            import ollama
            import httpx
            # Own the transport so both adapters release sockets deterministically.
            with httpx.Client(base_url=config.base_url, timeout=config.timeout,
                              follow_redirects=False, trust_env=trust_env) as transport:
                client = ollama.Client(host=config.base_url, timeout=config.timeout)
                client._client.close()
                client._client = transport
                yield client
        else:
            from openai import OpenAI, DefaultHttpxClient
            with OpenAI(base_url=config.base_url, timeout=config.timeout, max_retries=0,
                        http_client=DefaultHttpxClient(follow_redirects=False, trust_env=trust_env)) as client:
                yield client
    except ImportError as exc:
        raise RuntimeError("教学依赖未安装，请安装 requirements-phase3.txt。") from exc


def generate(config: TeachingConfig, messages: list[dict]) -> dict:
    """Ask the configured model for a JSON teaching answer.

    Args:
        config: Validated, non-secret connection preferences.
        messages: System instructions and bounded question/context data.

    Returns:
        A JSON object, validated further by the teaching engine.

    Raises:
        RuntimeError: Connection, model or output-format failure (no raw secrets).
    """
    config.validate()
    try:
        with _client(config) as client:
            if config.provider == "local":
                response = client.chat(model=config.model, messages=messages,
                                       format="json", stream=False,
                                       options={"num_predict": 4096})
                raw = response.message.content
            else:
                response = client.chat.completions.create(
                    model=config.model, messages=messages,
                    response_format={"type": "json_object"}, max_completion_tokens=4096)
                raw = response.choices[0].message.content
        if not isinstance(raw, str) or len(raw) > 100_000:
            raise ValueError("empty or oversized response")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("JSON object required")
        return result
    except ImportError as exc:
        raise RuntimeError("教学依赖未安装，请安装 requirements-phase3.txt。") from exc
    except Exception as exc:
        raise RuntimeError(
            f"模型请求失败（{type(exc).__name__}）。请检查服务、模型名、密钥、超时及 JSON 输出支持；"
            "未自动重试，也未修改笔记。") from exc


def test_connection(config: TeachingConfig) -> str:
    """List models only; never send questions, notes or attachments.

    Args:
        config: Connection preferences, including the requested model.

    Returns:
        A status message after verifying the model appears in the service list.
    """
    config.validate()
    try:
        with _client(config) as client:
            if config.provider == "local":
                names = {item.model for item in client.list().models}
                available = config.model in names or config.model + ":latest" in names
            else:
                names = {item.id for item in client.models.list().data}
                available = config.model in names
        if not available:
            return "服务可连接，但模型列表中没有指定模型。请检查模型名称（部分兼容服务不完整公开列表）。"
        return "连接成功，已找到指定模型。未发送笔记或问题；实际生成仍取决于模型权限和 JSON 支持。"
    except Exception as exc:
        raise RuntimeError(f"连接检查失败（{type(exc).__name__}），请检查服务地址、密钥和模型。") from exc
