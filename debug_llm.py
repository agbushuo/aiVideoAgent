"""调试 LLM 连接

用法:
    conda activate ai-video
    python debug_llm.py
"""
import httpx
import json

endpoint = "http://localhost:8080/v1"

# 1. 测试连接
print("=== 测试连接 ===")
try:
    r = httpx.get(f"{endpoint}/models", timeout=10)
    print(f"状态码: {r.status_code}")
    print(f"响应: {r.text[:500]}")

    if r.status_code == 200:
        models = r.json()
        if isinstance(models, list) and models:
            for m in models[:3]:
                model_id = m.get("id", "unknown")
                print(f"\n模型: {model_id}")
                print(f"  内容: {json.dumps(m, indent=2)[:300]}")

except Exception as e:
    print(f"连接失败: {e}")
    print("\n请确认 llama.cpp 服务是否正在运行")
    print("启动命令示例:")
    cmd = (
        "llama-server "
        "-m D:\\AI\\LLM\\ollama\\models\\blobs\\Qwen3.6-27B-Q4_K_M.gguf "
        "--port 8080 --ctx-size 131072 --n-predictor 16384"
    )
    print(cmd)

# 2. 测试发送长文本
print("\n=== 测试长文本处理 ===")
try:
    sample_segments = []
    for i in range(50):
        seg = (
            f"[{i*2:.1f}s-{i*2+2:.1f}s] #{i}: "
            f"这是第{i}段测试字幕内容，包含一些游戏解说的典型用语"
        )
        sample_segments.append(seg)
    transcript_text = "\n".join(sample_segments)
    text_len = len(transcript_text)
    print(f"测试文本长度: {text_len} 字符 (约 {int(text_len * 1.5)} tokens)")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的视频内容分析专家。"
                "输出必须是严格的 JSON 格式。"
            ),
        },
        {
            "role": "user",
            "content": (
                "基于以下视频字幕，请用 1-2 句话概括内容，"
                "并选出 2-3 个最值得保留的片段。\n\n"
                "输出 JSON 格式: "
                "{\"summary\": \"...\", \"highlights\": [...]}\n\n"
                f"字幕内容:\n{transcript_text}"
            ),
        },
    ]

    r = httpx.post(
        f"{endpoint}/chat/completions",
        json={
            "model": "Qwen3.6-27B-Q4_K_M.gguf",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 16384,
        },
        headers={"Content-Type": "application/json"},
        timeout=300,
    )
    print(f"状态码: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        print(f"响应长度: {len(content)} 字符")
        print(f"响应预览: {content[:300]}...")

        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [
                    l for l in lines
                    if not l.strip().startswith("```")
                ]
                cleaned = "\n".join(lines)
            parsed = json.loads(cleaned)
            print("\nJSON 解析成功!")
            summary = parsed.get("summary", "")
            print(f"  summary: {summary[:100]}...")
            hl_count = len(parsed.get("highlights", []))
            print(f"  highlights 数量: {hl_count}")
        except json.JSONDecodeError as e:
            print(f"\nJSON 解析失败: {e}")
            print(f"响应全文:\n{content}")
    else:
        print(f"错误响应: {r.text[:500]}")

except Exception as e:
    print(f"长文本测试失败: {e}")
