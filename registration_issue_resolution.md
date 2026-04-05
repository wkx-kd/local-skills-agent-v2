# 注册失败问题处理与解决流程总结

本文档总结了在开发/运行过程中，后端处理前端“注册”请求连发两次报错的根本原因及解决流程。主要包含两个连续的严重故障：数据库表缺失与密码哈希库兼容性错误。

---

## 阶段一：数据库核心表未创建

### ❌ 错误现象
在触发注册接口 `/api/auth/register` 时，FastAPI 报出 500 内部服务器错误。查看终端日志，核心错误栈指向：
`sqlalchemy.exc.ProgrammingError: ... relation "users" does not exist`

### 🔍 问题排查
数据库引擎 `psycopg/asyncpg` 在向 PostgresSQL 插入用户数据时找不到 `users` 表。经检查发现，虽然项目中配置了 Alembic 作为数据库迁移工具，且定义了全套的模型（Models），但**尚未生成迁移脚本将这些模型同步到实际的 Postgres 数据库中**。

### ✅ 解决步骤
需要运行 Alembic 来初始化数据库：
1. **生成迁移脚本**：
   通过虚拟环境（`agent`）运行 Alembic，自动检测 `models` 中的表结构并生成初始化脚本。
   ```bash
   PYTHONPATH=. /Users/wukaixuan/software/anaconda3/envs/agent/bin/python -m alembic revision --autogenerate -m "Initial migration"
   ```
2. **应用迁移**：
   将生成的表结构升级应用到 Postgres 数据库。
   ```bash
   PYTHONPATH=. /Users/wukaixuan/software/anaconda3/envs/agent/bin/python -m alembic upgrade head
   ```
这一阶段执行完毕后，`users` 等核心表格均被成功创建。

---

## 阶段二：`passlib` 与 `bcrypt` 的高版本兼容冲突

### ❌ 错误现象
在解决表格缺失问题后再次点击注册，出现以下双重报错：
1. `AttributeError: module 'bcrypt' has no attribute '__about__'`
2. `ValueError: password cannot be longer than 72 bytes, truncate manually if necessary`

### 🔍 问题排查
原代码 `app/core/security.py` 使用了 `passlib` 配合 `CryptContext` 来做加密：
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```
- **依赖冲突**：`passlib` 已经停止维护多年。当环境中的 `bcrypt` 库版本自动升级到了 `>4.0.0` 时，`bcrypt` 移除了内部变量 `__about__`，导致 `passlib` 在底层校验时发生崩溃。
- **长度限制**：`bcrypt` 算法要求输入哈希的密码文本不能超过 `72` 字节，`passlib` 在崩溃时的降级处理机制会传入非预期的格式从而触发超长报错。

### ✅ 解决步骤
为了根治这一兼容性问题（且避免为了兼容旧库去强制降低 `bcrypt` 的版本），放弃使用过时的 `passlib` 包装层，改为**直接使用原生 `bcrypt`** 进行加密。

1. **移除对 passlib 的导入和依赖使用**。
2. **在 `app/core/security.py` 重写哈希函数**，引入自动的 72 字节截断并直接采用 `bcrypt.hashpw` 及 `bcrypt.checkpw`：

```python
import bcrypt

def hash_password(password: str) -> str:
    # bcrypt 要求 bytes 类型，并且有 72 字节的安全截断
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain.encode('utf-8')[:72]
    return bcrypt.checkpw(plain_bytes, hashed.encode('utf-8'))
```
得益于开发服务器启用着 `--reload` 特性，保存该文件修改后服务自动重启，该兼容性问题随即解除。

---

**总结结论**：
注册功能失败本质是 `环境初始化缺失 (Database Migration)` 以及 `废弃第三方包的兼容性崩溃 (passlib vs bcrypt 4+)`，上述流程依次彻底清除了阻塞障碍。
