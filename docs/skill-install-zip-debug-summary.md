# Skill ZIP 安装失败问题排查总结

## 问题现象

通过前端上传 ZIP 文件安装 Skill 时，返回错误：

```
SKILL.md 文件不存在或格式错误
```

后端日志只显示：

```
POST /api/skills/install/upload HTTP/1.1" 400 Bad Request
```

---

## 排查步骤

### 第一步：确认错误来源

查看后端路由 `backend/app/routers/skills.py`，400 的 `detail` 字段来自 `SkillInstaller.install_from_zip()` 的返回值：

```python
if not result.success:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=result.error,
    )
```

错误消息 `"SKILL.md 不存在或格式错误"` 来自 `backend/app/services/skill_installer.py` 第 255 行。

---

### 第二步：阅读 ZIP 解压逻辑

定位到 `install_from_zip()` 中的解压代码（原始版本，第 218-238 行）：

```python
def _unzip():
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        if names and names[0].endswith('/'):   # ← 问题所在
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extractall(tmpdir)
                subdirs = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
                if len(subdirs) == 1:
                    shutil.move(str(subdirs[0]), str(target_dir))
                else:
                    target_dir.mkdir()
                    for item in Path(tmpdir).iterdir():
                        shutil.move(str(item), str(target_dir / item.name))
        else:
            target_dir.mkdir()
            zf.extractall(str(target_dir))   # ← 直接解压，路径错误
```

---

### 第三步：分析根本原因

该逻辑**只检查第一个条目**是否以 `/` 结尾来判断 ZIP 是否包含顶级目录，存在三种失败场景：

#### 场景 A：`zip -r` 命令生成的 ZIP（无显式目录条目）

```
my-skill/SKILL.md       ← names[0]，不以 / 结尾
my-skill/scripts/run.py
```

`names[0].endswith('/')` 为 `False`，走 else 分支直接 `extractall(target_dir)`，结果：

```
skills/<name>/my-skill/SKILL.md   ← SKILL.md 被埋入子目录
```

验证时查找 `skills/<name>/SKILL.md` → 不存在 → 报错。

#### 场景 B：macOS Finder 压缩生成的 ZIP

```
__MACOSX/              ← names[0]，以 / 结尾，被误认为顶级目录
__MACOSX/._SKILL.md
my-skill/
my-skill/SKILL.md
```

走 if 分支，但 `extractall` 将 `__MACOSX/` 也提取到临时目录，`iterdir()` 找到两个子目录，触发 else 分支将 `__MACOSX/` 和 `my-skill/` 都移入 `target_dir`，导致 `target_dir/SKILL.md` 不在预期位置。

#### 场景 C：ZIP 仅包含文件（无任何目录结构）

```
SKILL.md
scripts/run.py
```

走 else 分支直接 `extractall`，结果正确（`target_dir/SKILL.md` 存在），这是唯一能成功的场景。

---

## 根本原因

**用单个条目的路径格式来判断 ZIP 结构**，忽略了：

1. 不同工具生成的 ZIP 目录条目格式不同（有无显式目录条目）
2. macOS 生成的 ZIP 会混入 `__MACOSX/` 元数据目录

---

## 修复方案

**文件**：`backend/app/services/skill_installer.py`

核心思路：过滤 macOS 元数据文件后，统计**所有条目**的顶层路径组件，如果只有一个则视为"单顶层目录结构"。

```python
def _unzip():
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 过滤 macOS 元数据文件
        all_names = [
            n for n in zf.namelist()
            if not n.startswith('__MACOSX/')
            and not n.endswith('/.DS_Store')
            and Path(n).name != '.DS_Store'
        ]
        if not all_names:
            raise Exception("ZIP 文件为空或仅包含元数据")

        # 统计所有条目的顶层路径组件
        top_levels = set()
        for name in all_names:
            first = name.split('/', 1)[0]
            if first:
                top_levels.add(first)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # 仅解压过滤后的条目
            for name in all_names:
                zf.extract(name, tmp_path)

            if len(top_levels) == 1:
                # 所有条目共享同一顶层目录：将其内容作为 skill 目录
                only_top = next(iter(top_levels))
                src = tmp_path / only_top
                if src.is_dir():
                    shutil.move(str(src), str(target_dir))
                else:
                    target_dir.mkdir()
                    shutil.move(str(src), str(target_dir / src.name))
            else:
                # 多个顶层条目：直接作为 skill 目录
                target_dir.mkdir()
                for item in tmp_path.iterdir():
                    shutil.move(str(item), str(target_dir / item.name))
```

同时优化了 SKILL.md 验证失败时的错误信息，展示目标目录实际内容，方便后续定位：

```python
if not skill_md_path.exists():
    return InstallResult(
        success=False,
        error=f"SKILL.md 不存在。目录内容: [{entries}]。请确保 SKILL.md 位于 ZIP 根目录或单一顶层子目录内",
    )
```

---

## 验证方法

```bash
# 确认新代码已进入容器
docker exec agent_backend grep -n "top_levels" /app/app/services/skill_installer.py
# 预期输出 4 行匹配
```

---

## 部署过程中遇到的额外问题

### 服务器本地修改与 git pull 冲突

**现象**：执行 `git pull` 时报错：

```
error: Your local changes to the following files would be overwritten by merge:
        frontend/src/hooks/useChat.ts
```

**原因**：上次用 `scp` 手动修改的文件未提交到服务器 git 历史。

**解决方案**：

```bash
git stash        # 暂存本地修改
git pull origin main
```

由于远程仓库已包含相同修改，stash 内容无需恢复，功能不丢失。

---

## 经验总结

| 检查项 | 方法 | 说明 |
|--------|------|------|
| 确认代码已更新 | `docker exec container grep -n "关键字" /app/...` | 直接在容器里搜索新代码的特征字符串 |
| 查看 400 错误详情 | DevTools → Network → 点击失败请求 → Response | 后端 HTTPException 的 detail 字段包含完整错误信息 |
| 判断 ZIP 结构 | `python3 -c "import zipfile; zf=zipfile.ZipFile('x.zip'); print(zf.namelist())"` | 提前确认 ZIP 内文件列表结构 |

**关键教训**：

- 不同平台/工具生成的 ZIP 结构差异很大（显式目录条目、`__MACOSX/`、单层/多层等），解压逻辑需要覆盖所有常见情况
- 部署到服务器若使用过 `scp` 手动修改文件，后续 `git pull` 前应先 `git stash`
- 当 `git pull` 因网络不通而失败时，`scp` 单文件是有效的快速替代方案
