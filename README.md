根据对项目全部源代码的审查，我计划按以下结构撰写 README.md：

---

## FTP_Client

**1. 项目概述**
- 简介：基于 Python Socket 编程实现的 FTP 客户端，计算机网络课程实验
- 技术栈：Python 3.13 + Tkinter + PostgreSQL (psycopg2) + SSL/TLS
- 参考标准：RFC 959

**2. 功能特性**
- FTP 协议完整实现（USER/PASS/PASV/PORT/LIST/RETR/STOR/REST/DELE/MKD/RMD/RNFR/RNTO/SIZE/SYST/PWD/CWD/CDUP/NOOP/QUIT/AUTH TLS）
- 主动模式 (PORT) 与被动模式 (PASV)，界面实时切换
- 二进制传输 + 分块读写 (8192 字节/块)
- 断点续传（暂停/恢复 + PostgreSQL 断点记录）
- TLS/SSL 加密传输 (AUTH TLS → PBSZ 0 → PROT P)
- 双栏文件浏览器（本地/远程 Treeview）
- 连接历史日志 + 传输记录追踪 + 传输统计
- 收藏服务器管理
- 数据库故障容错（PostgreSQL 不可用时核心功能仍可用）

**3. 项目结构**
```
├── main.py              # 程序入口
├── ftp_core.py          # FTP 协议核心层（Socket/TLS/REST）
├── gui.py               # Tkinter 图形界面层
├── database.py          # PostgreSQL 持久化层
├── init_db.sql          # 数据库初始化 SQL 脚本
├── requirements.txt     # Python 依赖
├── debug_ftp.py         # 调试工具
└── test_raw.py          # 原始测试脚本
```

**4. 环境要求**
- Python 3.8+
- PostgreSQL 12+（可选，不安装则历史记录等功能不可用）
- 依赖安装：`pip install -r requirements.txt`

**5. 快速启动**
- 方式一：直接运行 `python main.py`
- 方式二：先手动建库 `psql -U postgres -c "CREATE DATABASE ftp_client;"` 再执行 `psql -U postgres -d ftp_client -f init_db.sql`
- 数据库配置修改：编辑 `database.py` 第16行密码

**6. 操作说明**
- 连接：工具栏"连接"按钮 → 填写主机/端口/用户名/密码 → 可选 PASV/TLS
- 浏览：双击目录进入，双击文件下载
- 上传：左侧选中本地文件 → 点击"上传"
- 下载：右侧选中远程文件 → 点击"下载"
- 暂停/继续：传输中点击"暂停"，再点击"继续"恢复断点
- 模式切换：工具栏下拉框实时切换 PASV/PORT
- 收藏：菜单 → 收藏 → 收藏当前服务器

**7. 测试清单**（勾选式，覆盖报告中的所有测试场景）

| 编号 | 测试项 | 预期结果 |
|------|--------|----------|
| T01 | 匿名登录（anonymous） | 230 登录成功 |
| T02 | 密码认证登录 | 230 登录成功 |
| T03 | 错误密码登录 | 530 认证失败 |
| T04 | 被动模式 LIST 列目录 | 正确显示文件/目录 |
| T05 | 主动模式 LIST 列目录 | PORT 模式下正确列出 |
| T06 | PASV ↔ PORT 运行时切换 | 切换后刷新正常 |
| T07 | 小文件下载（< 1MB） | 下载完成，文件完整 |
| T08 | 大文件下载（> 10MB） | 进度条正常，文件完整 |
| T09 | 小文件上传 | 上传完成，远程可见 |
| T10 | 大文件上传 | 进度条正常，远程文件完整 |
| T11 | 下载暂停 → 继续 | REST 偏移量正确，文件拼接完整 |
| T12 | 上传暂停 → 继续 | 断点继续写入，文件完整 |
| T13 | 数据库断点记录 | resume_points 表写入正确偏移量 |
| T14 | AUTH TLS 加密连接 | 234 响应，控制+数据通道均加密 |
| T15 | 强制 TLS 服务器（如 vsftpd） | 自动检测 503 并启用 TLS |
| T16 | 下载完整性校验 | 本地文件大小 = 远程文件大小 |
| T17 | 远程新建/删除/重命名 | MKD/RMD/RNFR+RNTO 执行成功 |
| T18 | 收藏服务器 | 收藏后可快速填充连接信息 |
| T19 | 连接历史 / 传输统计查看 | 数据库记录完整 |
| T20 | 数据库不可用时的容错 | 核心 FTP 功能正常，仅历史功能受限 |


---

这个结构是否符合你的需求？是否有需要增减的章节？确认后请切换到 **ACT MODE**，我来生成完整的 README.md。
