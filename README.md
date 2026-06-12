---

# Computer Network FTP Client

基于 Python Socket 编程、严格遵循 RFC 959 规范实现的 FTP（File Transfer Protocol）客户端，支持 FTPS 加密传输与断点续传，配套 Tkinter 图形界面与 PostgreSQL 持久化存储。本项目为计算机网络课程实验作品，从 TCP 三次握手到应用层 FTP 命令交互实现了完整的协议栈链路。

---

## 项目背景与目标

FTP 是互联网最经典的应用层协议之一，其"控制连接与数据连接分离"的设计思想对理解 TCP/IP 协议栈具有重要的教学价值。本项目的核心目标有三：

1. **从零构建协议栈**——不使用 ftplib 等高层封装库，仅依赖 Python 内置的 `socket` 和 `ssl` 标准库，从创建 Socket、建立 TCP 连接、封装/解析 FTP 命令等基础操作开始，实现包括 PASV/PORT 双模式、AUTH TLS 加密、REST 断点续传在内的完整 FTP 协议对话。

2. **工程化三层架构**——将系统解耦为通信层（`ftp_core.py`）、界面层（`gui.py`）和持久化层（`database.py`）三个独立模块，各层之间通过明确的接口交互，便于独立测试与功能扩展。

3. **生产级容错设计**——采用延时数据库连接策略，即使 PostgreSQL 不可用，核心 FTP 传输功能仍可正常运行；同时通过断点偏移量的双路径记录（本地文件大小 + 数据库 resume_points 表）实现传输中断后的鲁棒恢复。

---

## 技术架构

项目整体架构划分为三个层次：

### 通信层 — `ftp_core.py`

直接基于 `socket.socket(AF_INET, SOCK_STREAM)` 构建，封装了完整的 FTP 协议对话：

- **连接管理**：`connect()` 创建控制 Socket → 三次握手建立 TCP 连接 → 接收 220 服务就绪响应。断开时先发送 QUIT 命令再关闭 Socket，确保 TCP 四次挥手的正常完成。
- **命令封装**：`_send_command(command) → (success, response)` 统一接口，所有 FTP 命令（USER/PASS/PASV/PORT/LIST/RETR/STOR/REST 等 20+ 条）均通过该接口发送，以 CRLF（`\r\n`）结尾，自动处理多行响应解析（以响应码第 4 字符是否为空格判断命令完成）。
- **数据连接路由**：`_setup_data_connection()` 根据 `is_passive` 标志动态路由到被动模式或主动模式。被动模式解析 PASV 响应的 `(h1,h2,h3,h4,p1,p2)` 六元组重建 IP (`h1.h2.h3.h4`) 和端口 (`p1*256+p2`)；主动模式绑定 `0.0.0.0:0` 由系统分配端口，通过 PORT 命令告知服务器，然后调用 `accept()` 等待服务器连接。
- **TLS 加密**：`enable_tls()` 发送 AUTH TLS 命令，收到 234 响应后使用 `ssl.create_default_context().wrap_socket()` 包裹控制 Socket，随后发送 PBSZ 0 和 PROT P 将数据通道也设为加密模式。`_wrap_socket_tls()` 为数据连接包裹 TLS。
- **传输引擎**：下载/上传均采用 8192 字节分块循环读写，每块传输后回调进度函数以驱动 GUI 进度条更新。暂停通过线程间共享的 `transfer_paused` 布尔标志实现——每传输一块后检查标志，检测到暂停时立即关闭数据连接，保留 `last_transferred_bytes` 偏移量供恢复使用。
- **完整性校验**：下载完成后，通过 SIZE 命令获取远程文件总大小，与本地文件实际大小比对，确保传输完整。

### 界面层 — `gui.py`

基于 Python Tkinter 标准库构建，无需额外安装：

- **连接面板**：弹出式对话框提供主机/端口/用户名/密码输入，支持匿名登录一键切换、被动模式/主动模式选择、TLS 加密复选框、以及收藏服务器快速填充。连接操作在后台线程中执行，避免阻塞 GUI 主线程事件循环。
- **双栏文件浏览器**：左侧本地、右侧远程各使用 Treeview 组件展示文件列表（文件名、大小/类型、修改时间/信息）。支持双击进入目录、按 Backspace 返回上级、路径栏直接输入路径回车跳转。远程列表通过 LIST 命令获取原始输出，解析权限位的第一个字符（`d`）区分目录与文件。
- **传输控制**：提供上传 ⬆ / 下载 ⬇ / 暂停 ⏸ / 继续 ▶ 四按钮，状态机由 `transfer_active` 和 `transfer_paused` 两个标志协同管理。暂停时即时调用 `db.pause_transfer()` 保存断点偏移量到 `resume_points` 表；继续时重新启动传输线程并传入 `resume=True` 参数触发 REST 续传逻辑。
- **辅助功能**：菜单栏提供传输历史查看、传输统计聚合（成功/失败次数、上传/下载总字节数）、收藏服务器管理（CRUD）、FTP 协议说明（ABOUT 对话框）、使用帮助。
- **状态栏**：实时显示连接状态（● 已连接/● 未连接）、当前服务器地址、传输进度百分比。

### 持久化层 — `database.py`

通过 psycopg2 连接 PostgreSQL，设计四张核心表：

| 表名 | 职责 | 关键字段 |
|------|------|---------|
| `connection_history` | 每次连接会话的完整日志 | host, port, username, connection_time, disconnect_time, status |
| `transfer_records` | 每次传输的详细记录 | transfer_type, remote_file, local_path, file_size, transferred_bytes, status |
| `resume_points` | 与传输记录一一对应的断点偏移量 | transfer_id (UNIQUE), byte_offset, saved_at |
| `favorite_servers` | 用户收藏的服务器地址 | host, port, username (组合 UNIQUE 约束) |

关键设计：
- `resume_points` 使用 `ON CONFLICT (transfer_id) DO UPDATE` 实现幂等写入。
- `get_incomplete_transfers()` 联表查询 `transfer_records` LEFT JOIN `resume_points`，获取所有 `in_progress` 或 `paused` 状态的传输及其断点偏移量，为程序重启后的恢复提供数据基础。
- GUI 初始化时采用 **延时连接策略**——调用 `db.connect()` 失败后仅静默降级（控制台输出提示），不阻断程序启动，此时所有 FTP 核心功能正常可用，仅历史记录、断点数据库恢复等功能受限。

---

## 核心协议流程

```
客户端                                    服务器
  |                                         |
  |------- TCP SYN (port 21) ------------>  |
  |<------ TCP SYN-ACK ------------------   |
  |------- TCP ACK --------------------->   |
  |                                         |
  |<------ 220 Service ready ------------   |
  |------- AUTH TLS -------------------->   |  (可选)
  |<------ 234 Proceed ------------------   |
  |     [ TLS 握手加密控制通道 ]            |
  |                                       |
  |------- USER anonymous --------------->  |
  |<------ 331 Password required --------   |
  |------- PASS guest@ ----------------->   |
  |<------ 230 User logged in -----------   |
  |                                       |
  |------- PASV ------------------------->  |
  |<------ 227 (h1,h2,h3,h4,p1,p2) ------  |
  |------- TCP 连接 data_host:data_port ->  |
  |------- LIST ------------------------->  |
  |<------ 150 Opening data ------------    |
  |<===== (数据连接) 目录列表 ===========   |
  |                                       |
  |------- TYPE I ----------------------->  |
  |------- REST 1024 -------------------->  |  (断点续传)
  |<------ 350 Restart at 1024 ----------   |
  |------- PASV ------------------------->  |
  |<------ 227 Entering Passive --------    |
  |------- TCP 连接 data_host:data_port ->  |
  |------- RETR file.zip -------------->    |
  |<------ 150 Opening BINARY ----------    |
  |<===== (数据连接) 文件数据 ===========   |
  |<------ 226 Transfer complete --------   |
  |                                       |
  |----- QUIT ---><--- 221 Goodbye -------  |
  | [TCP 四次挥手]                         |
```


## 断点续传机制

**下载场景流程**
1. 用户选择远程文件点击下载，检查本地目标路径是否存在同名文件。
2. 若文件存在且大小 > 0，弹出对话框询问"是否续传"。
3. 用户确认后，以 `os.path.getsize(local_path)` 获取本地已有字节数作为偏移量。
4. 向服务器发送 `REST <offset>`，收到 350 响应后发送 `RETR <filename>`。
5. 以 `ab` 追加二进制模式打开本地文件，从文件末尾写入新接收数据。
6. 传输过程中用户点击"暂停"→ `transfer_paused` 置为 True → 下一次循环检查后退出，关闭数据连接 → 调用 `db.pause_transfer()` 将当前 `transferred_bytes` 写入 `resume_points` 表，传输记录状态更新为 `paused`。
7. 用户点击"继续"→ 重新启动传输线程，传入 `resume=True` → 重复步骤 3-5。
8. 下载完成后比对 `os.path.getsize(local_path)` 与 `SIZE` 命令获取的远程文件大小，不一致则报错。

**上传场景流程**
与下载对称，区别在于：
- 先通过 `SIZE` 命令查询服务器端已存在的文件大小作为 REST 偏移量。
- 以 `rb` 模式打开本地文件，`f.seek(offset)` 跳转到断点位置开始读取。

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

**7. 测试清单**

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
| T13 | 下载完整性校验 | 本地文件大小 = 远程文件大小 |
| T14 | 远程新建/删除/重命名 | MKD/RMD/RNFR+RNTO 执行成功 |
| T15 | 连接历史 / 传输统计查看 | 数据库记录完整 |
| T16 | 数据库不可用时的容错 | 核心 FTP 功能正常，仅历史功能受限 |



---
