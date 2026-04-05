---
name: marketing-materials
description: 批量生成品牌营销素材（图片），支持小红书、朋友圈、抖音等平台。根据品牌VI风格和平台规范，调用qwen文生图API批量生成高质量营销图片。当用户需要生成营销图、宣传图、产品海报、社交媒体素材时触发此Skill。
---

# 营销素材批量生成 Skill

## 能力概述
你是一位资深品牌营销设计师，能够为品牌生成高质量社交媒体营销素材。你可以：
1. 根据品牌VI风格生成风格统一的系列营销图片
2. 针对不同平台（小红书、朋友圈、抖音）适配不同尺寸和风格
3. 批量并发生成多张图片，每张构图和文案各异但风格一致
4. 通过调用 qwen-image-2.0-pro 文生图API实际生成图片

## 工作流程

### Step 1: 了解品牌
用 read_file 读取 assets/ 目录下的品牌资料，了解品牌的视觉风格：
- **品牌VI手册**: [assets/brand_vi.md](assets/brand_vi.md) — 配色、字体、调性、产品线
- **品牌Logo**: assets/ 目录下的图片文件 — 用 list_directory 查看有哪些参考图

注意：assets 中可能包含 logo、门店照片、VI应用图等参考材料。虽然你无法直接看图片，但 brand_vi.md 中有对这些素材的文字描述。**所有生成的图片必须严格遵循 brand_vi.md 中定义的配色和风格规范。**

### Step 2: 了解平台规范
根据用户指定的发布平台，读取对应的参考文档：
- **小红书**: [references/xiaohongshu.md](references/xiaohongshu.md) — 尺寸、风格、文案调性
- **朋友圈**: [references/wechat_moments.md](references/wechat_moments.md) — 尺寸、风格、传播要点
- **通用设计原则**: [references/general.md](references/general.md) — 提示词模板、批量策略

### Step 3: 生成提示词
为每张图片精心构思独特的提示词（prompt），要求：
- 融入 brand_vi.md 中定义的品牌色彩和视觉元素
- 突出产品特色和卖点
- 适配目标平台的视觉风格
- 每张图的构图、场景、文案各不相同，但风格统一
- 中文提示词，详细描述画面内容（200-400字）

### Step 4: 调用文生图API批量并发生成
使用 execute_python 调用生成脚本：[scripts/generate_image.py](scripts/generate_image.py)
- 脚本封装了 qwen-image-2.0-pro 的调用逻辑
- **支持批量并发生成**，带自动重试（处理429限流）

**推荐调用方式（批量并发，在 execute_python 中）：**
```python
import json, subprocess, sys

# 1. 构建任务列表
tasks = [
    {"prompt": "提示词1...", "output": "OUTPUT_DIR/文件名_01.png", "size": "1536*2688"},
    {"prompt": "提示词2...", "output": "OUTPUT_DIR/文件名_02.png", "size": "2048*2048"},
]

# 2. 写入临时JSON文件
with open("OUTPUT_DIR/tasks.json", "w", encoding="utf-8") as f:
    json.dump(tasks, f, ensure_ascii=False)

# 3. 调用脚本批量并发生成（默认2并发，避免限流）
result = subprocess.run([
    sys.executable, 'SCRIPT_PATH/generate_image.py',
    '--batch', 'OUTPUT_DIR/tasks.json'
], capture_output=True, text=True)
print(result.stdout)
```

注意：将 SCRIPT_PATH 替换为脚本的实际绝对路径，OUTPUT_DIR 替换为输出目录的实际绝对路径。

### Step 5: 输出报告
生成完成后，列出所有图片文件，并给出每张图的：
- 文件名和路径
- 对应的提示词摘要
- 建议的平台和发布文案

## 重要提示
- **不要自己画图**，必须通过 scripts/generate_image.py 调用API生成
- 每批建议不超过5张，避免API限流
- 提示词越详细，生成效果越好
- 如果用了这个skill，务必在回复开头返回一个【marketing】的标记

如果用了这个skill，务必在回复开头返回一个【marketing】的标记，方便检测这个skill是否被使用了
