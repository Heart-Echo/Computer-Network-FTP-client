"""
FTP客户端图形化界面 - 使用tkinter实现
包含连接面板、文件浏览、上传下载、断点续传等功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import threading
import time
from datetime import datetime

from ftp_core import FTPClient
from database import FTDatabase


class FTPClientGUI:
    """FTP客户端主窗口"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FTP客户端 - 计算机网络实验")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        # 初始化FTP客户端和数据库
        self.ftp = FTPClient()
        self.db = FTDatabase()

        # 状态变量
        self.connection_id = None
        self.current_remote_path = "/"
        self.current_local_path = os.path.expanduser("~")
        self.is_connected = False
        self.transfer_active = False
        self.transfer_paused = False
        self.current_transfer_id = None

        # 设置主题样式
        self._setup_styles()

        # 创建界面组件
        self._create_menu_bar()
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()

        # 连接数据库
        self._init_database()

        # 定时刷新远程目录
        self._auto_refresh()

        # 处理窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        # 使用可用主题
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")
        elif "vista" in available_themes:
            style.theme_use("vista")

        # 自定义按钮样式
        style.configure("Primary.TButton", font=("Microsoft YaHei", 10, "bold"))
        style.configure("Success.TButton",
                        font=("Microsoft YaHei", 10),
                        background="#28a745")
        style.configure("Danger.TButton",
                        font=("Microsoft YaHei", 10),
                        background="#dc3545")

        # Treeview样式
        style.configure("Treeview",
                        font=("Microsoft YaHei", 10),
                        rowheight=26)
        style.configure("Treeview.Heading",
                        font=("Microsoft YaHei", 10, "bold"))

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="连接服务器", command=self._show_connect_dialog, accelerator="Ctrl+N")
        file_menu.add_command(label="断开连接", command=self._disconnect, accelerator="Ctrl+D")
        file_menu.add_separator()
        file_menu.add_command(label="创建本地目录", command=self._create_local_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_closing, accelerator="Alt+F4")
        menubar.add_cascade(label="文件", menu=file_menu)

        # 传输菜单
        transfer_menu = tk.Menu(menubar, tearoff=0)
        transfer_menu.add_command(label="上传文件", command=self._upload_file, accelerator="Ctrl+U")
        transfer_menu.add_command(label="下载文件", command=self._download_file, accelerator="Ctrl+G")
        transfer_menu.add_separator()
        transfer_menu.add_command(label="暂停传输", command=self._pause_transfer)
        transfer_menu.add_command(label="继续传输", command=self._resume_transfer)
        transfer_menu.add_command(label="取消传输", command=self._cancel_transfer)
        menubar.add_cascade(label="传输", menu=transfer_menu)

        # 远程操作菜单
        remote_menu = tk.Menu(menubar, tearoff=0)
        remote_menu.add_command(label="刷新", command=self._refresh_remote)
        remote_menu.add_command(label="新建目录", command=self._create_remote_dir)
        remote_menu.add_command(label="删除文件/目录", command=self._delete_remote)
        remote_menu.add_command(label="重命名", command=self._rename_remote)
        remote_menu.add_separator()
        remote_menu.add_command(label="返回上级目录", command=self._go_up)
        remote_menu.add_command(label="输入路径", command=self._goto_path)
        menubar.add_cascade(label="远程操作", menu=remote_menu)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        self.mode_var = tk.StringVar(value="passive")
        view_menu.add_radiobutton(label="被动模式 (PASV)", variable=self.mode_var,
                                  value="passive", command=self._switch_mode)
        view_menu.add_radiobutton(label="主动模式 (PORT)", variable=self.mode_var,
                                  value="active", command=self._switch_mode)
        view_menu.add_separator()
        view_menu.add_command(label="传输历史", command=self._show_transfer_history)
        view_menu.add_command(label="传输统计", command=self._show_statistics)
        menubar.add_cascade(label="视图", menu=view_menu)

        # 服务器菜单
        server_menu = tk.Menu(menubar, tearoff=0)
        server_menu.add_command(label="收藏当前服务器", command=self._add_favorite)
        server_menu.add_command(label="管理收藏服务器", command=self._manage_favorites)
        menubar.add_cascade(label="收藏", menu=server_menu)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于FTP协议", command=self._show_about_ftp)
        help_menu.add_command(label="使用说明", command=self._show_help)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

        # 绑定快捷键
        self.root.bind("<Control-n>", lambda e: self._show_connect_dialog())
        self.root.bind("<Control-d>", lambda e: self._disconnect())
        self.root.bind("<Control-u>", lambda e: self._upload_file())
        self.root.bind("<Control-g>", lambda e: self._download_file())

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = ttk.Frame(self.root, padding=(5, 5))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # 连接按钮
        self.connect_btn = ttk.Button(toolbar, text="连接", command=self._show_connect_dialog,
                                      style="Primary.TButton")
        self.connect_btn.pack(side=tk.LEFT, padx=2)

        self.disconnect_btn = ttk.Button(toolbar, text="断开", command=self._disconnect,
                                         state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # 上传按钮
        self.upload_btn = ttk.Button(toolbar, text="上传 ⬆", command=self._upload_file,
                                     state=tk.DISABLED)
        self.upload_btn.pack(side=tk.LEFT, padx=2)

        # 下载按钮
        self.download_btn = ttk.Button(toolbar, text="下载 ⬇", command=self._download_file,
                                       state=tk.DISABLED)
        self.download_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # 暂停/继续按钮
        self.pause_btn = ttk.Button(toolbar, text="暂停 ⏸", command=self._pause_transfer,
                                    state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=2)

        self.resume_btn = ttk.Button(toolbar, text="继续 ▶", command=self._resume_transfer,
                                     state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # 刷新按钮
        self.refresh_btn = ttk.Button(toolbar, text="🔄 刷新", command=self._refresh_remote,
                                      state=tk.DISABLED)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        # 模式切换
        ttk.Label(toolbar, text="  模式:").pack(side=tk.LEFT, padx=(10, 2))
        self.mode_combo = ttk.Combobox(toolbar, values=["被动模式 (PASV)", "主动模式 (PORT)"],
                                       state="readonly", width=15)
        self.mode_combo.current(0)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        self.mode_combo.pack(side=tk.LEFT, padx=2)

        # 右侧连接状态
        self.conn_status_label = ttk.Label(toolbar, text="● 未连接", foreground="gray")
        self.conn_status_label.pack(side=tk.RIGHT, padx=5)

    def _create_main_content(self):
        """创建主内容区域 - 本地和远程文件浏览器"""
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ============ 左侧：本地文件浏览器 ============
        left_frame = ttk.LabelFrame(main_paned, text="💻 本地文件", padding=(5, 5))
        main_paned.add(left_frame, weight=1)

        # 本地路径导航
        local_nav_frame = ttk.Frame(left_frame)
        local_nav_frame.pack(fill=tk.X, pady=(0, 5))

        self.local_path_var = tk.StringVar(value=self.current_local_path)
        local_path_entry = ttk.Entry(local_nav_frame, textvariable=self.local_path_var,
                                     font=("Microsoft YaHei", 9))
        local_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        local_path_entry.bind("<Return>", self._local_path_enter)

        ttk.Button(local_nav_frame, text="📂", width=3,
                   command=self._browse_local_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(local_nav_frame, text="⬆", width=3,
                   command=self._local_go_up).pack(side=tk.LEFT, padx=1)

        # 本地文件列表
        local_list_frame = ttk.Frame(left_frame)
        local_list_frame.pack(fill=tk.BOTH, expand=True)

        self.local_tree = ttk.Treeview(local_list_frame,
                                       columns=("name", "size", "modified"),
                                       show="headings", selectmode="browse")
        self.local_tree.heading("name", text="文件名")
        self.local_tree.heading("size", text="大小")
        self.local_tree.heading("modified", text="修改时间")
        self.local_tree.column("name", width=200, minwidth=100)
        self.local_tree.column("size", width=80, minwidth=60, anchor="e")
        self.local_tree.column("modified", width=130, minwidth=100)

        local_scrollbar = ttk.Scrollbar(local_list_frame, orient=tk.VERTICAL,
                                        command=self.local_tree.yview)
        self.local_tree.configure(yscrollcommand=local_scrollbar.set)

        self.local_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        local_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.local_tree.bind("<Double-1>", self._on_local_double_click)
        self.local_tree.bind("<BackSpace>", lambda e: self._local_go_up())

        # 本地操作按钮
        local_btn_frame = ttk.Frame(left_frame)
        local_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(local_btn_frame, text="📁 新建目录",
                   command=self._create_local_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(local_btn_frame, text="🗑 删除",
                   command=self._delete_local).pack(side=tk.LEFT, padx=2)

        # ============ 右侧：远程文件浏览器 ============
        right_frame = ttk.LabelFrame(main_paned, text="🌐 远程文件", padding=(5, 5))
        main_paned.add(right_frame, weight=1)

        # 远程路径导航
        remote_nav_frame = ttk.Frame(right_frame)
        remote_nav_frame.pack(fill=tk.X, pady=(0, 5))

        self.remote_path_var = tk.StringVar(value="/")
        remote_path_entry = ttk.Entry(remote_nav_frame, textvariable=self.remote_path_var,
                                      font=("Microsoft YaHei", 9))
        remote_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        remote_path_entry.bind("<Return>", self._remote_path_enter)

        ttk.Button(remote_nav_frame, text="🔄", width=3,
                   command=self._refresh_remote).pack(side=tk.LEFT, padx=2)
        ttk.Button(remote_nav_frame, text="⬆", width=3,
                   command=self._go_up).pack(side=tk.LEFT, padx=1)

        # 远程文件列表
        remote_list_frame = ttk.Frame(right_frame)
        remote_list_frame.pack(fill=tk.BOTH, expand=True)

        self.remote_tree = ttk.Treeview(remote_list_frame,
                                        columns=("name", "type", "info"),
                                        show="headings", selectmode="browse")
        self.remote_tree.heading("name", text="文件名")
        self.remote_tree.heading("type", text="类型")
        self.remote_tree.heading("info", text="信息")
        self.remote_tree.column("name", width=200, minwidth=100)
        self.remote_tree.column("type", width=60, minwidth=50)
        self.remote_tree.column("info", width=100, minwidth=80)

        remote_scrollbar = ttk.Scrollbar(remote_list_frame, orient=tk.VERTICAL,
                                         command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=remote_scrollbar.set)

        self.remote_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        remote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.remote_tree.bind("<Double-1>", self._on_remote_double_click)
        self.remote_tree.bind("<BackSpace>", lambda e: self._go_up())

        # 远程操作按钮
        remote_btn_frame = ttk.Frame(right_frame)
        remote_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(remote_btn_frame, text="📁 新建目录",
                   command=self._create_remote_dir).pack(side=tk.LEFT, padx=2)
        ttk.Button(remote_btn_frame, text="🗑 删除",
                   command=self._delete_remote).pack(side=tk.LEFT, padx=2)
        ttk.Button(remote_btn_frame, text="✏ 重命名",
                   command=self._rename_remote).pack(side=tk.LEFT, padx=2)

        # 加载本地目录
        self._refresh_local()

    def _create_status_bar(self):
        """创建状态栏"""
        status_frame = ttk.Frame(self.root, padding=(5, 3))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # 状态信息
        self.status_label = ttk.Label(status_frame, text="就绪",
                                      font=("Microsoft YaHei", 9))
        self.status_label.pack(side=tk.LEFT)

        # 传输进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var,
                                            maximum=100, length=250)
        self.progress_bar.pack(side=tk.RIGHT, padx=5)

        # 进度文本
        self.progress_label = ttk.Label(status_frame, text="",
                                        font=("Microsoft YaHei", 9))
        self.progress_label.pack(side=tk.RIGHT, padx=5)

        # 连接信息
        ttk.Separator(status_frame, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        self.server_label = ttk.Label(status_frame, text="",
                                      font=("Microsoft YaHei", 9))
        self.server_label.pack(side=tk.RIGHT, padx=5)

    # ==================== 数据库初始化 ====================

    def _init_database(self):
        """初始化数据库连接和表结构"""
        success, msg = self.db.connect()
        if success:
            self.db.init_tables()
            self._set_status("数据库已连接")
        else:
            # 数据库不可用不阻止程序运行，只是部分功能不可用
            print(f"数据库连接失败: {msg}")
            self._set_status("数据库未连接 - 部分功能不可用")

    # ==================== 连接管理 ====================

    def _show_connect_dialog(self):
        """显示连接对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("连接到FTP服务器")
        dialog.geometry("450x380")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 380) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding=(20, 20))
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="FTP服务器连接",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 15))

        # 服务器地址
        ttk.Label(main_frame, text="服务器地址:").pack(anchor=tk.W, pady=(5, 0))
        host_frame = ttk.Frame(main_frame)
        host_frame.pack(fill=tk.X)
        host_var = tk.StringVar(value="ftp.gnu.org")
        host_entry = ttk.Entry(host_frame, textvariable=host_var, font=("Microsoft YaHei", 10))
        host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(host_frame, text="端口:").pack(side=tk.LEFT, padx=(5, 2))
        port_var = tk.StringVar(value="21")
        port_entry = ttk.Entry(host_frame, textvariable=port_var, width=6,
                               font=("Microsoft YaHei", 10))
        port_entry.pack(side=tk.LEFT)

        # 用户名
        ttk.Label(main_frame, text="用户名:").pack(anchor=tk.W, pady=(10, 0))
        user_var = tk.StringVar(value="anonymous")
        user_entry = ttk.Entry(main_frame, textvariable=user_var,
                               font=("Microsoft YaHei", 10))
        user_entry.pack(fill=tk.X)

        # 密码
        ttk.Label(main_frame, text="密码:").pack(anchor=tk.W, pady=(10, 0))
        pass_var = tk.StringVar()
        pass_entry = ttk.Entry(main_frame, textvariable=pass_var, show="*",
                               font=("Microsoft YaHei", 10))
        pass_entry.pack(fill=tk.X)

        # 匿名登录复选框
        anon_var = tk.BooleanVar(value=True)

        def toggle_anon():
            if anon_var.get():
                user_var.set("anonymous")
                pass_var.set("")
                user_entry.config(state=tk.DISABLED)
                pass_entry.config(state=tk.DISABLED)
            else:
                user_var.set("")
                user_entry.config(state=tk.NORMAL)
                pass_entry.config(state=tk.NORMAL)

        ttk.Checkbutton(main_frame, text="匿名登录", variable=anon_var,
                        command=toggle_anon).pack(anchor=tk.W, pady=(10, 0))
        toggle_anon()

        # 被动模式复选框
        passive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="使用被动模式 (PASV)",
                        variable=passive_var).pack(anchor=tk.W, pady=(5, 0))

        # 消息标签
        msg_var = tk.StringVar()
        msg_label = ttk.Label(main_frame, textvariable=msg_var,
                              foreground="red", wraplength=400)
        msg_label.pack(pady=(5, 0))

        def do_connect():
            host = host_var.get().strip()
            if not host:
                msg_var.set("请输入服务器地址")
                return

            try:
                port = int(port_var.get().strip())
                if port < 1 or port > 65535:
                    msg_var.set("端口号必须在1-65535之间")
                    return
            except ValueError:
                msg_var.set("端口号必须为数字")
                return

            username = user_var.get().strip()
            password = pass_var.get()

            # 禁用按钮
            connect_btn.config(state=tk.DISABLED, text="连接中...")
            msg_var.set("正在连接...")
            dialog.update()

            # 在后台线程中连接
            def connect_thread():
                success, response = self.ftp.connect(host, port)
                if not success:
                    dialog.after(0, lambda: [
                        msg_var.set(f"连接失败: {response}"),
                        connect_btn.config(state=tk.NORMAL, text="连接")
                    ])
                    return

                success, response = self.ftp.login(username, password)
                if not success:
                    dialog.after(0, lambda: [
                        msg_var.set(f"登录失败: {response}"),
                        connect_btn.config(state=tk.NORMAL, text="连接")
                    ])
                    return

                # 设置模式
                self.ftp.set_passive_mode(passive_var.get())

                dialog.after(0, lambda: self._on_connected(host, port, username))
                dialog.after(0, dialog.destroy)

            threading.Thread(target=connect_thread, daemon=True).start()

        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        connect_btn = ttk.Button(btn_frame, text="连接", command=do_connect,
                                 style="Primary.TButton")
        connect_btn.pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=2)

        # 收藏服务器下拉
        ttk.Label(main_frame, text="收藏的服务器:").pack(anchor=tk.W, pady=(10, 0))
        favorites = self.db.get_favorite_servers()
        if favorites:
            fav_names = [f"{f['name']} ({f['host']}:{f['port']})" for f in favorites]
            fav_combo = ttk.Combobox(main_frame, values=fav_names, state="readonly",
                                     font=("Microsoft YaHei", 10))
            fav_combo.pack(fill=tk.X)

            def on_fav_select(event):
                idx = fav_combo.current()
                if idx >= 0 and idx < len(favorites):
                    f = favorites[idx]
                    host_var.set(f["host"])
                    port_var.set(str(f["port"]))
                    user_var.set(f["username"] or "anonymous")
                    pass_var.set("")
                    if f["username"] and f["username"] != "anonymous":
                        anon_var.set(False)
                        toggle_anon()

            fav_combo.bind("<<ComboboxSelected>>", on_fav_select)

    def _on_connected(self, host, port, username):
        """连接成功后的处理"""
        self.is_connected = True
        self.connection_id = self.db.add_connection_record(host, port, username)

        # 更新UI状态
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        self.upload_btn.config(state=tk.NORMAL)
        self.download_btn.config(state=tk.NORMAL)
        self.refresh_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.DISABLED)

        self.conn_status_label.config(text="● 已连接", foreground="green")
        self.server_label.config(text=f"{username}@{host}:{port}")

        # 设置模式显示
        if self.ftp.is_passive:
            self.mode_combo.current(0)
        else:
            self.mode_combo.current(1)

        # 刷新远程目录
        self._refresh_remote()

        self._set_status(f"已连接到 {host}:{port}")
        messagebox.showinfo("连接成功", f"已成功连接到 {host}\n用户: {username}")

    def _disconnect(self):
        """断开FTP连接"""
        if not self.is_connected:
            return

        if self.transfer_active:
            if not messagebox.askyesno("确认", "有正在进行的传输，确定要断开连接吗？"):
                return

        # 更新数据库
        if self.connection_id:
            self.db.update_disconnect(self.connection_id)

        self.ftp.close()
        self.is_connected = False
        self.transfer_active = False
        self.transfer_paused = False

        # 更新UI状态
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.upload_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.DISABLED)

        self.conn_status_label.config(text="● 未连接", foreground="gray")
        self.server_label.config(text="")

        # 清空远程列表
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)

        self._set_status("已断开连接")

    # ==================== 本地文件操作 ====================

    def _refresh_local(self):
        """刷新本地文件列表"""
        for item in self.local_tree.get_children():
            self.local_tree.delete(item)

        path = self.current_local_path
        if not os.path.exists(path):
            self.current_local_path = os.path.expanduser("~")
            path = self.current_local_path

        self.local_path_var.set(path)

        try:
            # 添加上级目录
            parent = os.path.dirname(path)
            if parent != path:
                self.local_tree.insert("", tk.END, values=("..", "<上级目录>", ""),
                                       tags=("parent",))

            items = os.listdir(path)
            # 目录排在前面
            dirs = []
            files = []
            for item in items:
                full_path = os.path.join(path, item)
                try:
                    if os.path.isdir(full_path):
                        st = os.stat(full_path)
                        dirs.append((item, "<目录>",
                                     datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")))
                    else:
                        st = os.stat(full_path)
                        size = self.db.format_bytes(st.st_size)
                        files.append((item, size,
                                      datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")))
                except OSError:
                    continue

            for d in sorted(dirs, key=lambda x: x[0].lower()):
                self.local_tree.insert("", tk.END, values=d, tags=("dir",))

            for f in sorted(files, key=lambda x: x[0].lower()):
                self.local_tree.insert("", tk.END, values=f, tags=("file",))

        except Exception as e:
            self._set_status(f"读取本地目录失败: {str(e)}")

    def _local_go_up(self):
        """本地目录返回上级"""
        parent = os.path.dirname(self.current_local_path)
        if parent != self.current_local_path:
            self.current_local_path = parent
            self._refresh_local()

    def _browse_local_dir(self):
        """浏览本地目录"""
        dir_path = filedialog.askdirectory(initialdir=self.current_local_path,
                                           title="选择本地目录")
        if dir_path:
            self.current_local_path = dir_path
            self._refresh_local()

    def _local_path_enter(self, event):
        """本地路径回车处理"""
        path = self.local_path_var.get().strip()
        if os.path.isdir(path):
            self.current_local_path = path
            self._refresh_local()
        else:
            messagebox.showwarning("路径错误", f"目录不存在: {path}")

    def _on_local_double_click(self, event):
        """本地文件双击处理"""
        selection = self.local_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.local_tree.item(item, "values")
        if not values:
            return

        name = values[0].rstrip('/')
        full_path = os.path.join(self.current_local_path, name)

        if name == "..":
            self._local_go_up()
        elif os.path.isdir(full_path):
            self.current_local_path = full_path
            self._refresh_local()

    def _create_local_dir(self):
        """创建本地目录"""
        dirname = simpledialog.askstring("新建目录", "输入目录名称:",
                                         parent=self.root)
        if dirname:
            path = os.path.join(self.current_local_path, dirname)
            try:
                os.makedirs(path, exist_ok=True)
                self._refresh_local()
                self._set_status(f"已创建目录: {dirname}")
            except Exception as e:
                messagebox.showerror("错误", f"创建目录失败: {str(e)}")

    def _delete_local(self):
        """删除本地文件/目录"""
        selection = self.local_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的文件或目录")
            return

        item = selection[0]
        values = self.local_tree.item(item, "values")
        name = values[0].rstrip('/')
        if name == "..":
            return

        full_path = os.path.join(self.current_local_path, name)

        if not messagebox.askyesno("确认删除", f"确定要删除 {name} 吗？"):
            return

        try:
            if os.path.isdir(full_path):
                import shutil
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            self._refresh_local()
            self._set_status(f"已删除: {name}")
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {str(e)}")

    # ==================== 远程文件操作 ====================

    def _refresh_remote(self):
        """刷新远程文件列表"""
        if not self.is_connected:
            return

        self._set_status("正在刷新远程目录...")

        def do_refresh():
            # 获取原始LIST输出（含文件类型信息）
            success, raw_data = self.ftp.list_dir_raw()
            if not success:
                self.root.after(0, lambda: self._set_status("刷新远程目录失败"))
                return

            # 获取当前路径
            pwd_ok, pwd_path = self.ftp.pwd()
            if pwd_ok:
                self.current_remote_path = pwd_path

            items = []
            if raw_data:
                for line in raw_data.strip().split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 9:
                        perms = parts[0]
                        is_dir = perms.startswith('d')
                        size = parts[4]
                        name = ' '.join(parts[8:])
                        try:
                            size_int = int(size)
                            size_str = self.db.format_bytes(size_int)
                        except ValueError:
                            size_str = size

                        info = f"{size_str}  {parts[5]} {parts[6]} {parts[7]}"
                        items.append((is_dir, name, "目录" if is_dir else "文件", info))
                    elif len(parts) >= 4:
                        name = parts[-1]
                        is_dir = '<DIR>' in line.upper()
                        items.append((is_dir, name, "目录" if is_dir else "文件", ""))

            # 在UI线程更新
            def update_ui():
                for item in self.remote_tree.get_children():
                    self.remote_tree.delete(item)

                self.remote_path_var.set(self.current_remote_path)

                # 添加上级目录
                self.remote_tree.insert("", tk.END, values=("..", "<上级目录>", ""),
                                        tags=("parent",))

                # 目录在前，文件在后，按名称排序
                dirs = [(n, t, i) for d, n, t, i in items if d]
                files = [(n, t, i) for d, n, t, i in items if not d]

                for name, ftype, info in sorted(dirs, key=lambda x: x[0].lower()):
                    self.remote_tree.insert("", tk.END, values=(name, ftype, info),
                                            tags=("dir",))

                for name, ftype, info in sorted(files, key=lambda x: x[0].lower()):
                    self.remote_tree.insert("", tk.END, values=(name, ftype, info),
                                            tags=("file",))

                self._set_status(f"远程目录: {self.current_remote_path}")

            self.root.after(0, update_ui)

        threading.Thread(target=do_refresh, daemon=True).start()

    def _go_up(self):
        """远程目录返回上级"""
        if not self.is_connected:
            return

        def do_cdup():
            success, response = self.ftp.cdup()
            if success:
                pwd_ok, pwd_path = self.ftp.pwd()
                if pwd_ok:
                    self.current_remote_path = pwd_path
                self.root.after(0, self._refresh_remote)
            else:
                self.root.after(0, lambda: self._set_status(f"返回上级失败: {response}"))

        threading.Thread(target=do_cdup, daemon=True).start()

    def _remote_path_enter(self, event):
        """远程路径回车处理"""
        if not self.is_connected:
            return

        path = self.remote_path_var.get().strip()

        def do_cwd():
            success, response = self.ftp.cwd(path)
            if success:
                self.root.after(0, self._refresh_remote)
            else:
                self.root.after(0, lambda: messagebox.showwarning("错误", f"切换目录失败: {response}"))

        threading.Thread(target=do_cwd, daemon=True).start()

    def _goto_path(self):
        """跳转到指定远程路径"""
        if not self.is_connected:
            return
        path = simpledialog.askstring("跳转", "输入远程路径:", parent=self.root)
        if path:
            self.remote_path_var.set(path)

            def do_cwd():
                success, response = self.ftp.cwd(path)
                if success:
                    self.root.after(0, self._refresh_remote)
                else:
                    self.root.after(0, lambda: messagebox.showwarning("错误", f"切换失败: {response}"))

            threading.Thread(target=do_cwd, daemon=True).start()

    def _on_remote_double_click(self, event):
        """远程文件双击处理"""
        if not self.is_connected:
            return

        selection = self.remote_tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.remote_tree.item(item, "values")
        if not values:
            return

        name = values[0].rstrip('/')
        item_type = values[1] if len(values) > 1 else ""

        if name == "..":
            self._go_up()
        elif item_type == "目录" or "<DIR>" in item_type:
            def do_cwd():
                success, response = self.ftp.cwd(name)
                if success:
                    pwd_ok, pwd_path = self.ftp.pwd()
                    if pwd_ok:
                        self.current_remote_path = pwd_path
                    self.root.after(0, self._refresh_remote)
                else:
                    self.root.after(0, lambda: self._set_status(f"切换目录失败: {response}"))

            threading.Thread(target=do_cwd, daemon=True).start()
        else:
            # 双击文件 -> 下载
            self._download_file()

    def _create_remote_dir(self):
        """创建远程目录"""
        if not self.is_connected:
            return

        dirname = simpledialog.askstring("新建远程目录", "输入目录名称:", parent=self.root)
        if not dirname:
            return

        def do_mkdir():
            success, response = self.ftp.make_dir(dirname)
            if success:
                self.root.after(0, self._refresh_remote)
                self.root.after(0, lambda: self._set_status(f"已创建远程目录: {dirname}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", f"创建目录失败: {response}"))

        threading.Thread(target=do_mkdir, daemon=True).start()

    def _delete_remote(self):
        """删除远程文件/目录"""
        if not self.is_connected:
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的文件或目录")
            return

        item = selection[0]
        values = self.remote_tree.item(item, "values")
        name = values[0].rstrip('/')
        if name == "..":
            return

        item_type = values[1] if len(values) > 1 else ""

        if not messagebox.askyesno("确认删除", f"确定要删除远程 {name} 吗？"):
            return

        def do_delete():
            if item_type == "目录":
                success, response = self.ftp.remove_dir(name)
            else:
                success, response = self.ftp.delete_file(name)

            if success:
                self.root.after(0, self._refresh_remote)
                self.root.after(0, lambda: self._set_status(f"已删除: {name}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", f"删除失败: {response}"))

        threading.Thread(target=do_delete, daemon=True).start()

    def _rename_remote(self):
        """重命名远程文件/目录"""
        if not self.is_connected:
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要重命名的文件或目录")
            return

        item = selection[0]
        values = self.remote_tree.item(item, "values")
        old_name = values[0].rstrip('/')
        if old_name == "..":
            return

        new_name = simpledialog.askstring("重命名", "输入新名称:",
                                          initialvalue=old_name, parent=self.root)
        if not new_name or new_name == old_name:
            return

        def do_rename():
            success, response = self.ftp.rename_file(old_name, new_name)
            if success:
                self.root.after(0, self._refresh_remote)
                self.root.after(0, lambda: self._set_status(f"已重命名: {old_name} -> {new_name}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", f"重命名失败: {response}"))

        threading.Thread(target=do_rename, daemon=True).start()

    # ==================== 上传下载 ====================

    def _upload_file(self):
        """上传文件"""
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接到FTP服务器")
            return

        selection = self.local_tree.selection()
        if selection:
            item = selection[0]
            values = self.local_tree.item(item, "values")
            name = values[0].rstrip('/')
            if name == "..":
                local_path = ""
            else:
                local_path = os.path.join(self.current_local_path, name)
        else:
            local_path = filedialog.askopenfilename(
                initialdir=self.current_local_path,
                title="选择要上传的文件"
            )

        if not local_path or not os.path.exists(local_path):
            return

        if os.path.isdir(local_path):
            messagebox.showwarning("提示", "暂不支持上传整个目录")
            return

        remote_filename = os.path.basename(local_path)
        file_size = os.path.getsize(local_path)

        # 检查是否需要断点续传
        resume = False
        # 可以检查数据库中的记录来判断

        # 创建传输记录
        transfer_id = self.db.add_transfer_record(
            self.connection_id, "upload", remote_filename, local_path, file_size
        )
        self.current_transfer_id = transfer_id

        self.transfer_active = True
        self.transfer_paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)

        progress_event = threading.Event()

        def progress_callback(bytes_sent, total_bytes):
            if not progress_event.is_set():
                percent = (bytes_sent / total_bytes) * 100 if total_bytes > 0 else 0
                self.root.after(0, lambda: self._update_progress(
                    percent, f"上传中... {self.db.format_bytes(bytes_sent)} / {self.db.format_bytes(total_bytes)}"
                ))
                self.root.after(0, lambda: self.db.update_transfer_progress(transfer_id, bytes_sent))

        def do_upload():
            success, message = self.ftp.upload_file(
                local_path, remote_filename, progress_callback, resume
            )

            def finish():
                self.transfer_active = False
                self.transfer_paused = False
                self.pause_btn.config(state=tk.DISABLED)
                self.resume_btn.config(state=tk.DISABLED)

                if success:
                    self.db.complete_transfer(transfer_id, file_size if success else 0)
                    self._update_progress(100, f"上传完成: {remote_filename}")
                    self._refresh_remote()
                    messagebox.showinfo("上传完成", message)
                else:
                    self.db.fail_transfer(transfer_id)
                    self._set_status(f"上传失败: {message}")
                    messagebox.showerror("上传失败", message)

                self.current_transfer_id = None

            self.root.after(0, finish)

        threading.Thread(target=do_upload, daemon=True).start()

    def _download_file(self):
        """下载文件"""
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接到FTP服务器")
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请选择要下载的远程文件")
            return

        item = selection[0]
        values = self.remote_tree.item(item, "values")
        remote_name = values[0].rstrip('/')
        if remote_name == "..":
            return

        item_type = values[1] if len(values) > 1 else ""
        if item_type == "目录" or "<DIR>" in item_type:
            messagebox.showwarning("提示", "暂不支持下载整个目录")
            return

        # 选择本地保存路径
        local_path = filedialog.asksaveasfilename(
            initialdir=self.current_local_path,
            initialfile=remote_name,
            title="保存下载文件到"
        )
        if not local_path:
            return

        # 检查是否需要断点续传
        resume = False
        if os.path.exists(local_path):
            local_size = os.path.getsize(local_path)
            resume = messagebox.askyesno("断点续传",
                                         f"文件 {local_path} 已存在 ({self.db.format_bytes(local_size)})。\n"
                                         f"是否使用断点续传继续下载？")

        # 创建传输记录
        transfer_id = self.db.add_transfer_record(
            self.connection_id, "download", remote_name, local_path, 0
        )
        self.current_transfer_id = transfer_id

        self.transfer_active = True
        self.transfer_paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)

        def progress_callback(bytes_downloaded, total_bytes):
            percent = (bytes_downloaded / total_bytes) * 100 if total_bytes > 0 else 0
            self.root.after(0, lambda: self._update_progress(
                percent, f"下载中... {self.db.format_bytes(bytes_downloaded)} / {self.db.format_bytes(total_bytes)}"
            ))
            self.root.after(0, lambda: self.db.update_transfer_progress(transfer_id, bytes_downloaded))

        def do_download():
            success, message = self.ftp.download_file(
                remote_name, local_path, progress_callback, resume
            )

            def finish():
                self.transfer_active = False
                self.transfer_paused = False
                self.pause_btn.config(state=tk.DISABLED)
                self.resume_btn.config(state=tk.DISABLED)

                if success:
                    final_size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
                    self.db.complete_transfer(transfer_id, final_size)
                    self._update_progress(100, f"下载完成: {remote_name}")
                    self._refresh_local()
                    messagebox.showinfo("下载完成", message)
                else:
                    self.db.fail_transfer(transfer_id)
                    self._set_status(f"下载失败: {message}")
                    messagebox.showerror("下载失败", message)

                self.current_transfer_id = None

            self.root.after(0, finish)

        threading.Thread(target=do_download, daemon=True).start()

    def _pause_transfer(self):
        """暂停传输"""
        if not self.transfer_active or self.transfer_paused:
            return
        self.transfer_paused = True
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)

        if self.current_transfer_id:
            # 获取当前进度并保存
            current_bytes = int(self.progress_var.get() * 100)  # 实际需要精确值
            # self.db.pause_transfer(self.current_transfer_id, current_bytes)

        self._set_status("传输已暂停")

    def _resume_transfer(self):
        """继续传输"""
        if not self.transfer_paused:
            return
        self.transfer_paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self._set_status("传输已继续")

    def _cancel_transfer(self):
        """取消传输"""
        if not self.transfer_active:
            return
        if messagebox.askyesno("确认", "确定要取消当前传输吗？"):
            self.transfer_active = False
            self.transfer_paused = False
            self.pause_btn.config(state=tk.DISABLED)
            self.resume_btn.config(state=tk.DISABLED)

            if self.current_transfer_id:
                self.db.fail_transfer(self.current_transfer_id)
                self.current_transfer_id = None

            self._update_progress(0, "")
            self._set_status("传输已取消")

    # ==================== 模式切换 ====================

    def _on_mode_change(self, event):
        """通过下拉框切换模式"""
        if self.mode_combo.current() == 0:
            self.ftp.set_passive_mode(True)
            self._set_status("已切换到被动模式 (PASV)")
        else:
            self.ftp.set_passive_mode(False)
            self._set_status("已切换到主动模式 (PORT)")

    def _switch_mode(self):
        """通过菜单切换模式"""
        if self.mode_var.get() == "passive":
            self.ftp.set_passive_mode(True)
            self.mode_combo.current(0)
            self._set_status("已切换到被动模式 (PASV)")
        else:
            self.ftp.set_passive_mode(False)
            self.mode_combo.current(1)
            self._set_status("已切换到主动模式 (PORT)")

    # ==================== 收藏服务器 ====================

    def _add_favorite(self):
        """收藏当前连接的服务器"""
        if not self.is_connected:
            messagebox.showinfo("提示", "请先连接到FTP服务器")
            return

        name = simpledialog.askstring("收藏服务器", "输入服务器名称:",
                                      parent=self.root)
        if name:
            success, msg = self.db.add_favorite_server(
                name, self.ftp.host, self.ftp.port, self.ftp.username
            )
            if success:
                messagebox.showinfo("成功", msg)
            else:
                messagebox.showerror("失败", msg)

    def _manage_favorites(self):
        """管理收藏的服务器"""
        favorites = self.db.get_favorite_servers()
        if not favorites:
            messagebox.showinfo("收藏列表", "暂无收藏的服务器")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("管理收藏服务器")
        dialog.geometry("600x350")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=(10, 10))
        frame.pack(fill=tk.BOTH, expand=True)

        # 列表
        tree = ttk.Treeview(frame, columns=("name", "host", "port", "username"),
                            show="headings", selectmode="browse")
        tree.heading("name", text="名称")
        tree.heading("host", text="地址")
        tree.heading("port", text="端口")
        tree.heading("username", text="用户名")
        tree.column("name", width=120)
        tree.column("host", width=180)
        tree.column("port", width=60)
        tree.column("username", width=100)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for f in favorites:
            tree.insert("", tk.END, iid=str(f["id"]),
                        values=(f["name"], f["host"], f["port"], f["username"] or ""))

        def delete_selected():
            selection = tree.selection()
            if not selection:
                return
            server_id = int(selection[0])
            if messagebox.askyesno("确认", "确定要删除这个收藏吗？"):
                success, msg = self.db.remove_favorite_server(server_id)
                if success:
                    tree.delete(selection[0])

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="删除选中", command=delete_selected,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT, padx=2)

    # ==================== 历史和统计 ====================

    def _show_transfer_history(self):
        """显示传输历史"""
        records = self.db.get_transfer_history(50)
        if not records:
            messagebox.showinfo("传输历史", "暂无传输记录")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("传输历史")
        dialog.geometry("850x450")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=(10, 10))
        frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(frame, columns=("type", "remote", "local", "size", "status", "time"),
                            show="headings", selectmode="browse")
        tree.heading("type", text="类型")
        tree.heading("remote", text="远程文件")
        tree.heading("local", text="本地路径")
        tree.heading("size", text="大小")
        tree.heading("status", text="状态")
        tree.heading("time", text="时间")

        tree.column("type", width=60)
        tree.column("remote", width=180)
        tree.column("local", width=200)
        tree.column("size", width=80)
        tree.column("status", width=80)
        tree.column("time", width=140)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        status_map = {
            "completed": "✅ 完成",
            "failed": "❌ 失败",
            "in_progress": "⏳ 进行中",
            "paused": "⏸ 已暂停"
        }

        for r in records:
            tree.insert("", tk.END, values=(
                "⬆ 上传" if r["transfer_type"] == "upload" else "⬇ 下载",
                r["remote_file"],
                r["local_path"],
                self.db.format_bytes(r["file_size"] or 0),
                status_map.get(r["status"], r["status"]),
                r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else ""
            ))

        ttk.Button(frame, text="关闭", command=dialog.destroy).pack(pady=(10, 0))

    def _show_statistics(self):
        """显示传输统计"""
        stats = self.db.get_statistics()
        messagebox.showinfo("传输统计",
                            f"📊 传输统计\n\n"
                            f"上传次数: {stats['total_uploads']}\n"
                            f"下载次数: {stats['total_downloads']}\n"
                            f"上传总量: {self.db.format_bytes(stats['total_upload_bytes'])}\n"
                            f"下载总量: {self.db.format_bytes(stats['total_download_bytes'])}\n"
                            f"完成传输: {stats['completed_transfers']}\n"
                            f"失败传输: {stats['failed_transfers']}")

    # ==================== 帮助信息 ====================

    def _show_about_ftp(self):
        """显示FTP协议说明"""
        messagebox.showinfo("关于FTP协议",
                            "FTP (File Transfer Protocol) 文件传输协议\n\n"
                            "本程序基于RFC 959规范实现FTP客户端功能。\n\n"
                            "主要特性:\n"
                            "• 使用Socket编程实现TCP连接\n"
                            "• 支持主动模式(PORT)和被动模式(PASV)\n"
                            "• 支持断点续传(REST命令)\n"
                            "• 使用PostgreSQL存储传输记录\n"
                            "• 支持文件上传下载、目录浏览等功能")

    def _show_help(self):
        """显示使用说明"""
        messagebox.showinfo("使用说明",
                            "📖 FTP客户端使用说明\n\n"
                            "1. 点击「连接」按钮连接FTP服务器\n"
                            "   - 可使用匿名登录或输入用户名密码\n"
                            "   - 选择被动/主动模式\n\n"
                            "2. 左侧为本地文件浏览器\n"
                            "   - 双击目录进入\n"
                            "   - 双击Backspace返回上级\n\n"
                            "3. 右侧为远程文件浏览器\n"
                            "   - 同样支持双击导航\n\n"
                            "4. 上传：选择本地文件，点击「上传」\n"
                            "5. 下载：选择远程文件，点击「下载」\n\n"
                            "6. 断点续传：\n"
                            "   - 下载时如果文件已存在会询问是否续传\n"
                            "   - 暂停的传输可从数据库中恢复\n\n"
                            "快捷键:\n"
                            "  Ctrl+N - 新建连接\n"
                            "  Ctrl+D - 断开连接\n"
                            "  Ctrl+U - 上传文件\n"
                            "  Ctrl+G - 下载文件")

    # ==================== 工具方法 ====================

    def _set_status(self, message: str):
        """设置状态栏消息"""
        self.status_label.config(text=message)

    def _update_progress(self, percent: float, text: str = ""):
        """更新进度条"""
        self.progress_var.set(percent)
        if text:
            self.progress_label.config(text=text)

    def _auto_refresh(self):
        """自动刷新远程目录（连接状态下每30秒）"""
        if self.is_connected:
            self._refresh_remote()
        self.root.after(30000, self._auto_refresh)

    def _on_closing(self):
        """窗口关闭处理"""
        if self.transfer_active:
            if not messagebox.askyesno("确认", "有正在进行的传输，确定要退出吗？"):
                return

        if self.is_connected:
            if self.connection_id:
                self.db.update_disconnect(self.connection_id)
            self.ftp.close()

        self.db.close()
        self.root.destroy()

    def run(self):
        """启动GUI主循环"""
        self.root.mainloop()