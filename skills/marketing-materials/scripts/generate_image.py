# ============================================================================
# Copyright (c) 2026 深维大模型（DeepDimension AI）
# All Rights Reserved. 版权所有，盗版必究。
#
# 本软件及其相关文档受版权法保护。未经深维大模型书面授权，
# 任何单位和个人不得擅自复制、修改、分发或以其他方式使用本软件
# 的全部或部分内容。违者将依法追究法律责任。
# ============================================================================
"""
营销素材图片生成脚本
调用阿里云百炼 qwen-image-2.0-pro 文生图API

用法:
    # 单张生成
    python generate_image.py --prompt "提示词" --output "输出路径.png"

    # 批量并发生成（传入JSON文件）
    python generate_image.py --batch tasks.json

    tasks.json 格式:
    [
        {"prompt": "提示词1", "output": "out1.png", "size": "1536*2688"},
        {"prompt": "提示词2", "output": "out2.png", "size": "2048*2048"}
    ]
"""

import argparse
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# DashScope API 配置
API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
MODEL = "qwen-image-2.0-pro"

DEFAULT_NEGATIVE = (
    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，"
    "人脸无细节，过度光滑，画面具有AI感，构图混乱，文字模糊扭曲，"
    "廉价感，塑料质感"
)


def generate_one(prompt, output_path, size="2048*2048", negative_prompt=None, prompt_extend=True, max_retries=3):
    """调用API生成单张图片并下载保存，带自动重试（处理429限流）"""
    if not API_KEY:
        return (output_path, False, "未设置 DASHSCOPE_API_KEY")

    payload = {
        "model": MODEL,
        "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
        "parameters": {
            "size": size.replace("x", "*"),
            "negative_prompt": negative_prompt or DEFAULT_NEGATIVE,
            "prompt_extend": prompt_extend,
            "watermark": False,
        }
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    # 带重试的API调用
    import time
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            image_url = result["output"]["choices"][0]["message"]["content"][0]["image"]
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = (attempt + 1) * 15  # 15s, 30s, 45s
                print(f"  {os.path.basename(output_path)}: 限流，{wait}s后重试...")
                time.sleep(wait)
                continue
            return (output_path, False, f"HTTP {e.code}: {e.read().decode('utf-8')[:100]}")
        except Exception as e:
            return (output_path, False, str(e)[:200])

    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        urllib.request.urlretrieve(image_url, output_path)
        file_size = os.path.getsize(output_path)
        return (output_path, True, f"{file_size:,} bytes")
    except Exception as e:
        return (output_path, False, f"下载失败: {e}")


def batch_generate(tasks, max_workers=5):
    """并发批量生成，tasks 为 list[dict]，每个 dict 含 prompt/output/size"""
    print(f"批量生成: {len(tasks)} 张图片，并发数: {min(max_workers, len(tasks))}")
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, task in enumerate(tasks):
            f = executor.submit(
                generate_one,
                prompt=task["prompt"],
                output_path=task["output"],
                size=task.get("size", "2048*2048"),
                negative_prompt=task.get("negative"),
                prompt_extend=task.get("prompt_extend", True),
            )
            futures[f] = i

        for future in as_completed(futures):
            idx = futures[future]
            path, success, msg = future.result()
            status = "OK" if success else "FAIL"
            print(f"  [{idx+1}/{len(tasks)}] {status} {os.path.basename(path)} - {msg}")
            results.append({"index": idx, "path": path, "success": success, "message": msg})

    # 按原始顺序排序
    results.sort(key=lambda r: r["index"])
    ok = sum(1 for r in results if r["success"])
    print(f"\n完成: {ok}/{len(tasks)} 张成功")
    return results


def main():
    parser = argparse.ArgumentParser(description="营销素材图片生成")
    parser.add_argument("--prompt", help="正向提示词（单张模式）")
    parser.add_argument("--negative", default=None, help="反向提示词")
    parser.add_argument("--size", default="2048*2048", help="图片尺寸 宽*高")
    parser.add_argument("--output", help="输出文件路径（单张模式）")
    parser.add_argument("--no-extend", action="store_true", help="关闭提示词智能改写")
    parser.add_argument("--batch", help="批量模式：传入JSON文件路径")
    parser.add_argument("--workers", type=int, default=2, help="并发数（默认2，避免限流）")
    args = parser.parse_args()

    if args.batch:
        # 批量并发模式
        with open(args.batch, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        results = batch_generate(tasks, max_workers=args.workers)
        # 输出结果JSON供调用方解析
        print(json.dumps(results, ensure_ascii=False))
    elif args.prompt and args.output:
        # 单张模式
        size = args.size.replace("x", "*")
        path, success, msg = generate_one(
            prompt=args.prompt,
            output_path=args.output,
            size=size,
            negative_prompt=args.negative,
            prompt_extend=not args.no_extend,
        )
        if success:
            print(f"图片已保存: {path} ({msg})")
        else:
            print(f"生成失败: {msg}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
