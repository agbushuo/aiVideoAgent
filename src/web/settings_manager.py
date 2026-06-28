"""用户设置管理器

持久化到 data/settings.json，优先级高于 config.yaml。
保存时同步写入 config.yaml 的 llm 段，确保全系统一致。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path(__file__).parent.parent.parent / "data" / "settings.json"
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"

DEFAULT_SETTINGS: dict[str, Any] = {
    "modelType": "online",
    "localLlm": {
        "url": "http://localhost:11434",
        "model": "",
        "temperature": 0.7,
        "maxTokens": 8192,
    },
    "onlineLlm": {
        "provider": "openai",
        "apiKey": "",
        "baseUrl": "https://api.openai.com/v1",
        "model": "claude-sonnet-4-6",
        "temperature": 0.7,
        "maxTokens": 8192,
    },
    "theme": "dark",
    "accentColor": "#6366f1",
}


def load_settings() -> dict[str, Any]:
    """加载用户设置，不存在则返回默认值"""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            # 合并默认值
            merged = {**DEFAULT_SETTINGS}
            if "localLlm" in user:
                merged["localLlm"] = {**merged["localLlm"], **user["localLlm"]}
            if "onlineLlm" in user:
                merged["onlineLlm"] = {**merged["onlineLlm"], **user["onlineLlm"]}
            for k in ("modelType", "theme", "accentColor"):
                if k in user:
                    merged[k] = user[k]
            return merged
        except (json.JSONDecodeError, KeyError):
            return {**DEFAULT_SETTINGS}
    return {**DEFAULT_SETTINGS}


def save_settings(settings: dict[str, Any]) -> None:
    """保存用户设置并同步到 config.yaml"""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    # 同步更新 config.yaml 的 llm 段
    _sync_config_yaml(settings)


def _sync_config_yaml(settings: dict[str, Any]) -> None:
    """将用户 LLM 设置写入 config.yaml 的 llm 段"""
    if not CONFIG_PATH.exists():
        return

    active = get_active_llm_config_from(settings)
    try:
        content = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return

    # 构建 key-value 映射（key 是 YAML 字段名，value 是新值）
    new_values = {
        "provider": active["provider"],
        "model": active["model"],
        "endpoint": active["endpoint"],
        "api_key": active["api_key"],
        "temperature": active["temperature"],
        "max_tokens": active["max_tokens"],
    }

    in_llm_section = False
    new_lines = []
    for line in content.splitlines():
        # 检测是否进入 llm 段
        if re.match(r'^llm:\s*$', line.strip()):
            in_llm_section = True
            new_lines.append(line)
            continue
        # 检测是否离开 llm 段（遇到新的顶级段）
        if in_llm_section and re.match(r'^[a-z_]+:', line) and not line.startswith((' ', '\t')):
            in_llm_section = False
            new_lines.append(line)
            continue

        if in_llm_section:
            matched = False
            for key, value in new_values.items():
                pattern = rf'^([ \t]*{re.escape(key)}:[ \t]*)'
                m = re.match(pattern, line)
                if m:
                    prefix = m.group(1)
                    # 判断原值是否有引号
                    rest = line[m.end():].strip()
                    has_quotes = rest.startswith(('"', "'"))
                    # 提取原值的闭合引号（如果有）
                    if has_quotes:
                        quote_char = rest[0]
                        close_quote = quote_char
                    else:
                        close_quote = ""

                    # 构建新值
                    if isinstance(value, str) and (has_quotes or ' ' in value):
                        new_lines.append(f'{prefix}"{value}"')
                    else:
                        new_lines.append(f'{prefix}{value}')
                    matched = True
                    break
            if not matched:
                new_lines.append(line)
        else:
            new_lines.append(line)

    CONFIG_PATH.write_text('\n'.join(new_lines), encoding="utf-8")


def get_active_llm_config_from(settings: dict[str, Any]) -> dict[str, Any]:
    """从给定的 settings 字典获取当前选中的 LLM 配置（不读文件）"""
    model_type = settings.get("modelType", "online")

    if model_type == "local":
        llm = settings.get("localLlm", {})
        return {
            "provider": "openai",
            "model": llm.get("model", ""),
            "endpoint": llm.get("url", "http://localhost:11434"),
            "api_key": "",
            "temperature": llm.get("temperature", 0.7),
            "max_tokens": llm.get("maxTokens", 8192),
            "timeout": 1800,
            "context_size": 131072,
        }
    else:
        llm = settings.get("onlineLlm", {})
        provider_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "deepseek": "openai",
            "zhipu": "openai",
            "custom": "openai",
        }
        return {
            "provider": provider_map.get(llm.get("provider", "openai"), "openai"),
            "model": llm.get("model", ""),
            "endpoint": llm.get("baseUrl", "https://api.openai.com/v1"),
            "api_key": llm.get("apiKey", ""),
            "temperature": llm.get("temperature", 0.7),
            "max_tokens": llm.get("maxTokens", 8192),
            "timeout": 1800,
            "context_size": 131072,
        }


def get_active_llm_config() -> dict[str, Any]:
    """获取当前选中的 LLM 配置（映射到后端 config.yaml 格式）

    返回格式与 config.yaml 的 llm 段一致：
    {provider, model, endpoint, api_key, temperature, max_tokens, timeout, context_size}
    """
    settings = load_settings()
    model_type = settings.get("modelType", "online")

    if model_type == "local":
        llm = settings.get("localLlm", {})
        return {
            "provider": "openai",  # Ollama/vLLM 都是 OpenAI 兼容
            "model": llm.get("model", ""),
            "endpoint": llm.get("url", "http://localhost:11434"),
            "api_key": "",
            "temperature": llm.get("temperature", 0.7),
            "max_tokens": llm.get("maxTokens", 8192),
            "timeout": 1800,
            "context_size": 131072,
        }
    else:
        llm = settings.get("onlineLlm", {})
        provider_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "deepseek": "openai",
            "zhipu": "openai",
            "custom": "openai",
        }
        return {
            "provider": provider_map.get(llm.get("provider", "openai"), "openai"),
            "model": llm.get("model", ""),
            "endpoint": llm.get("baseUrl", "https://api.openai.com/v1"),
            "api_key": llm.get("apiKey", ""),
            "temperature": llm.get("temperature", 0.7),
            "max_tokens": llm.get("maxTokens", 8192),
            "timeout": 1800,
            "context_size": 131072,
        }


def merge_llm_into_config(config: dict[str, Any]) -> dict[str, Any]:
    """将用户设置合并到 config.yaml 配置中（用户设置优先级更高）

    返回新的 config 字典，llm 段被用户设置覆盖。
    """
    active = get_active_llm_config()
    if active.get("model"):  # 只有用户设置了模型名才覆盖
        config["llm"] = {**config.get("llm", {}), **active}
    return config
