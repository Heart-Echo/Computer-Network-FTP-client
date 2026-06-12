"""FTP核心协议模块 - 使用Socket编程实现FTP协议 (支持FTPS)
按照RFC 959规范实现FTP客户端功能
支持主动模式(PORT)和被动模式(PASV)、断点续传(REST)
"""

import ssl
import socket
import os
import re
import time
from typing import Optional, Tuple, List


class FTPClient:
    """FTP客户端核心类 - 从创建Socket、建立TCP连接开始实现FTP协议"""

    def __init__(self):
        self.control_socket: Optional[socket.socket] = None
        self.data_socket: Optional[socket.socket] = None
        self.data_listen_socket: Optional[socket.socket] = None
        self.host: str = ""
        self.port: int = 21
        self.username: str = ""
        self.password: str = ""
        self.is_logged_in: bool = False
        self.is_passive: bool = True  # 默认被动模式
        self.timeout: int = 30
        self.tls_enabled: bool = False  # TLS/SSL 是否已启用
        self.buffer_size: int = 8192
        self.transfer_paused: bool = False  # 传输暂停标志
        self.last_transferred_bytes: int = 0  # 暂停时已传输的字节数

    # ==================== Socket连接管理 ====================

    def connect(self, host: str, port: int = 21, timeout: int = 30) -> Tuple[bool, str]:
        """
        建立控制连接 - 创建socket并建立TCP连接
        参数:
            host: FTP服务器地址
            port: FTP服务器端口（默认21）
            timeout: 超时时间（秒）
        返回:
            (成功标志, 响应消息)
        """
        try:
            self.host = host
            self.port = port
            self.timeout = timeout

            # 步骤1: 创建socket (AF_INET用于IPv4, SOCK_STREAM用于TCP)
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.settimeout(timeout)

            # 步骤2: 建立TCP连接
            self.control_socket.connect((host, port))

            # 步骤3: 读取服务器欢迎消息
            response = self._receive_response()

            if response.startswith("220"):
                return True, response
            else:
                self.close()
                return False, f"连接被拒绝: {response}"

        except socket.timeout:
            self.close()
            return False, "连接超时，请检查服务器地址和端口"
        except socket.gaierror:
            self.close()
            return False, f"无法解析主机名: {host}"
        except ConnectionRefusedError:
            self.close()
            return False, f"连接被拒绝: {host}:{port}"
        except OSError as e:
            self.close()
            return False, f"网络错误: {str(e)}"

    def close(self):
        """关闭所有连接"""
        try:
            if self.is_logged_in and self.control_socket:
                self._send_command("QUIT")
        except Exception:
            pass

        self._close_data_connection()
        self._close_listen_socket()

        if self.control_socket:
            try:
                self.control_socket.close()
            except Exception:
                pass
            self.control_socket = None

        self.is_logged_in = False
        self.host = ""
        self.username = ""
        self.tls_enabled = False

    # ==================== FTP认证 ====================

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        FTP用户认证
        参数:
            username: 用户名
            password: 密码
        返回:
            (成功标志, 响应消息)
        """
        if not self.control_socket:
            return False, "未连接到FTP服务器"

        # 发送USER命令
        success, response = self._send_command(f"USER {username}")
        if not success:
            # 自动检测：如果服务器要求AUTH TLS，尝试启用TLS后重试
            if "503" in response and "AUTH" in response.upper():
                tls_ok, tls_msg = self.enable_tls()
                if not tls_ok:
                    return False, f"服务器要求TLS但启用失败: {tls_msg}"
                success, response = self._send_command(f"USER {username}")
                if not success:
                    return False, f"USER命令在TLS后仍失败: {response}"
            else:
                return False, f"USER命令失败: {response}"

        # 如果返回230，说明无需密码（匿名登录）
        if response.startswith("230"):
            self.username = username
            self.is_logged_in = True
            return True, response

        # 服务器要求先AUTH TLS
        if response.startswith("503"):
            tls_ok, tls_msg = self.enable_tls()
            if not tls_ok:
                return False, f"服务器要求TLS但启用失败: {tls_msg}"
            return self.login(username, password)

        # 需要密码，发送PASS命令
        if response.startswith("331"):
            success, response = self._send_command(f"PASS {password}")
            if success and response.startswith("230"):
                self.username = username
                self.password = password
                self.is_logged_in = True
                return True, response
            else:
                return False, f"密码错误: {response}"
        else:
            return False, response

    # ==================== FTPS (TLS/SSL) ====================

    def enable_tls(self) -> Tuple[bool, str]:
        """
        启用TLS/SSL加密 (AUTH TLS)
        FTP over TLS (FTPS) - 加密控制通道和数据通道
        """
        if not self.control_socket:
            return False, "未连接到FTP服务器"
        if self.tls_enabled:
            return True, "TLS已启用"

        success, response = self._send_command("AUTH TLS")
        if not success or not response.startswith("234"):
            return False, f"AUTH TLS失败: {response}"

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            self.control_socket = context.wrap_socket(
                self.control_socket,
                server_hostname=self.host,
                do_handshake_on_connect=True
            )
        except ssl.SSLError as e:
            return False, f"SSL握手失败: {e}"
        except OSError as e:
            return False, f"TLS协商失败: {e}"

        self.tls_enabled = True
        self._send_command("PBSZ 0")
        self._send_command("PROT P")
        return True, "TLS加密已启用"

    def _wrap_socket_tls(self, sock: socket.socket) -> socket.socket:
        """用TLS包裹socket (用于数据通道)"""
        if not self.tls_enabled:
            return sock
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            return context.wrap_socket(
                sock, server_hostname=self.host, do_handshake_on_connect=True
            )
        except Exception:
            return sock

    # ==================== FTP命令实现 ====================

    def cwd(self, directory: str) -> Tuple[bool, str]:
        """改变工作目录 (CWD)"""
        success, response = self._send_command(f"CWD {directory}")
        return success and response.startswith("250"), response

    def pwd(self) -> Tuple[bool, str]:
        """获取当前工作目录 (PWD)"""
        success, response = self._send_command("PWD")
        if success and response.startswith("257"):
            match = re.search(r'"([^"]*)"', response)
            if match:
                return True, match.group(1)
        return False, response

    def cdup(self) -> Tuple[bool, str]:
        """返回上级目录 (CDUP)"""
        success, response = self._send_command("CDUP")
        return success and response.startswith("250"), response

    def list_dir(self, path: str = "") -> Tuple[bool, List[str]]:
        """
        列出目录内容 (LIST)
        使用数据连接获取目录列表
        """
        if not self._setup_data_connection():
            return False, ["无法建立数据连接"]

        cmd = f"LIST {path}" if path else "LIST"
        success, response = self._send_command(cmd)

        if not success:
            self._close_data_connection()
            return False, [response]

        if not response.startswith("150") and not response.startswith("125"):
            self._close_data_connection()
            return False, [response]

        data = self._receive_data()
        self._close_data_connection()
        self._receive_response()

        if not data:
            return True, []

        lines = data.strip().split("\n")
        file_names = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 9:
                name = " ".join(parts[8:])
                file_names.append(name)
            elif len(parts) >= 4:
                name = parts[-1]
                file_names.append(name)
            else:
                file_names.append(line)

        return True, file_names

    def list_dir_raw(self, path: str = "") -> Tuple[bool, str]:
        """列出目录原始内容（用于判断文件/目录类型）"""
        if not self._setup_data_connection():
            return False, "无法建立数据连接"

        cmd = f"LIST {path}" if path else "LIST"
        success, response = self._send_command(cmd)

        if not success or (not response.startswith("150") and not response.startswith("125")):
            self._close_data_connection()
            return False, response

        data = self._receive_data()
        self._close_data_connection()
        self._receive_response()

        return True, data if data else ""

    def get_file_size(self, filename: str) -> Tuple[bool, int]:
        """获取远程文件大小 (SIZE)"""
        success, response = self._send_command(f"SIZE {filename}")
        if success and response.startswith("213"):
            try:
                size = int(response.split()[1].strip())
                return True, size
            except (IndexError, ValueError):
                pass
        return False, 0

    def set_restart_marker(self, offset: int) -> Tuple[bool, str]:
        """设置断点续传位置 (REST)"""
        success, response = self._send_command(f"REST {offset}")
        return success and response.startswith("350"), response

    def set_type(self, type_char: str = "I") -> Tuple[bool, str]:
        """设置传输类型 (TYPE)"""
        success, response = self._send_command(f"TYPE {type_char}")
        return success and response.startswith("200"), response

    def set_passive_mode(self, passive: bool):
        """切换主动/被动模式"""
        self.is_passive = passive

    def pause_transfer(self):
        """暂停当前传输 - 线程安全"""
        self.transfer_paused = True

    def resume_transfer(self):
        """恢复暂停的传输"""
        self.transfer_paused = False

    def download_file(self, remote_file: str, local_path: str,
                      progress_callback=None, resume: bool = False) -> Tuple[bool, str]:
        """下载文件 (RETR) - 支持断点续传和暂停"""
        try:
            self.transfer_paused = False
            self.last_transferred_bytes = 0
            self.set_type("I")
            get_size_ok, remote_size = self.get_file_size(remote_file)

            local_size = 0
            if resume and os.path.exists(local_path):
                local_size = os.path.getsize(local_path)
                if local_size > 0:
                    self.set_restart_marker(local_size)

            if not self._setup_data_connection():
                return False, "无法建立数据连接"

            success, response = self._send_command(f"RETR {remote_file}")

            if not success or (not response.startswith("150") and not response.startswith("125")):
                self._close_data_connection()
                return False, f"下载请求失败: {response}"

            mode = "ab" if (resume and local_size > 0) else "wb"
            total_bytes = local_size
            total_size = local_size + remote_size if remote_size > 0 else 0

            try:
                with open(local_path, mode) as f:
                    while True:
                        # 检查暂停标志
                        if self.transfer_paused:
                            self.last_transferred_bytes = total_bytes
                            self._close_data_connection()
                            return False, "TRANSPORT_PAUSED"

                        try:
                            self.data_socket.settimeout(1)
                            chunk = self.data_socket.recv(self.buffer_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            total_bytes += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(total_bytes, total_size)
                        except socket.timeout:
                            # 超时后继续循环，检查暂停标志
                            continue
            except socket.timeout:
                pass

            self._close_data_connection()
            final_response = self._receive_response()

            if final_response.startswith("226") or final_response.startswith("250"):
                if progress_callback and total_size > 0:
                    progress_callback(total_bytes, total_size)
                # 验证文件完整性：比对本地文件大小与远程文件大小
                if remote_size > 0 and os.path.exists(local_path):
                    actual_local_size = os.path.getsize(local_path)
                    if actual_local_size != remote_size:
                        return False, f"下载可能不完整: 本地 {actual_local_size} 字节，远程 {remote_size} 字节"
                return True, f"下载完成: {remote_file} ({total_bytes} 字节)"
            else:
                return False, f"传输可能不完整: {final_response}"

        except Exception as e:
            self._close_data_connection()
            return False, f"下载失败: {str(e)}"

    def upload_file(self, local_path: str, remote_filename: str,
                    progress_callback=None, resume: bool = False) -> Tuple[bool, str]:
        """上传文件 (STOR) - 支持断点续传和暂停"""
        try:
            if not os.path.exists(local_path):
                return False, f"本地文件不存在: {local_path}"

            self.transfer_paused = False
            self.last_transferred_bytes = 0
            self.set_type("I")
            total_size = os.path.getsize(local_path)

            offset = 0
            if resume:
                get_size_ok, remote_size = self.get_file_size(remote_filename)
                if get_size_ok and remote_size < total_size:
                    offset = remote_size
                    self.set_restart_marker(offset)
                elif get_size_ok and remote_size >= total_size:
                    return False, "远程文件已完整，无需续传"

            if not self._setup_data_connection():
                return False, "无法建立数据连接"

            success, response = self._send_command(f"STOR {remote_filename}")

            if not success or (not response.startswith("150") and not response.startswith("125")):
                return False, f"上传请求失败: {response}"

            bytes_sent = offset
            try:
                with open(local_path, "rb") as f:
                    if offset > 0:
                        f.seek(offset)
                    while True:
                        # 检查暂停标志
                        if self.transfer_paused:
                            self.last_transferred_bytes = bytes_sent
                            self._close_data_connection()
                            return False, "TRANSPORT_PAUSED"

                        chunk = f.read(self.buffer_size)
                        if not chunk:
                            break
                        self.data_socket.sendall(chunk)
                        bytes_sent += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_sent, total_size)
            except Exception as e:
                self._close_data_connection()
                return False, f"数据传输失败: {str(e)}"

            self._close_data_connection()
            final_response = self._receive_response()

            if final_response.startswith("226") or final_response.startswith("250"):
                if progress_callback:
                    progress_callback(bytes_sent, total_size)
                return True, f"上传完成: {remote_filename} ({bytes_sent} 字节)"
            else:
                return False, f"传输可能不完整: {final_response}"

        except Exception as e:
            self._close_data_connection()
            return False, f"上传失败: {str(e)}"

    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """删除远程文件 (DELE)"""
        success, response = self._send_command(f"DELE {filename}")
        return success and response.startswith("250"), response

    def rename_file(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        """重命名远程文件 (RNFR/RNTO)"""
        success, response = self._send_command(f"RNFR {old_name}")
        if not success or not response.startswith("350"):
            return False, f"RNFR失败: {response}"

        success, response = self._send_command(f"RNTO {new_name}")
        return success and response.startswith("250"), response

    def make_dir(self, dirname: str) -> Tuple[bool, str]:
        """创建远程目录 (MKD)"""
        success, response = self._send_command(f"MKD {dirname}")
        return success and response.startswith("257"), response

    def remove_dir(self, dirname: str) -> Tuple[bool, str]:
        """删除远程目录 (RMD)"""
        success, response = self._send_command(f"RMD {dirname}")
        return success and response.startswith("250"), response

    def noop(self) -> Tuple[bool, str]:
        """保持连接活跃 (NOOP)"""
        return self._send_command("NOOP")

    def get_system_info(self) -> Tuple[bool, str]:
        """获取服务器系统信息 (SYST)"""
        return self._send_command("SYST")

    # ==================== 内部方法：命令发送与响应接收 ====================

    def _send_command(self, command: str) -> Tuple[bool, str]:
        """向服务器发送FTP命令并接收响应"""
        if not self.control_socket:
            return False, "未连接到服务器"

        try:
            cmd_bytes = (command + "\r\n").encode("utf-8", errors="ignore")
            self.control_socket.sendall(cmd_bytes)
            response = self._receive_response()
            return True, response

        except socket.timeout:
            return False, "命令超时"
        except OSError as e:
            return False, f"发送失败: {str(e)}"

    def _receive_response(self) -> str:
        """接收FTP控制连接的响应"""
        try:
            response = self.control_socket.recv(self.buffer_size).decode("utf-8", errors="ignore")
            while True:
                if len(response) >= 4 and response[3] == " ":
                    break
                try:
                    self.control_socket.settimeout(1)
                    more = self.control_socket.recv(self.buffer_size).decode("utf-8", errors="ignore")
                    if not more:
                        break
                    response += more
                except socket.timeout:
                    break
                finally:
                    self.control_socket.settimeout(self.timeout)

            return response.strip()

        except socket.timeout:
            return "响应超时"
        except OSError as e:
            return f"接收错误: {str(e)}"

    # ==================== 内部方法：数据连接管理 ====================

    def _setup_data_connection(self) -> bool:
        """建立数据连接 - 支持主动模式(PORT)和被动模式(PASV)"""
        self._close_data_connection()
        self._close_listen_socket()

        if self.is_passive:
            return self._setup_passive_data_connection()
        else:
            return self._setup_active_data_connection()

    def _setup_passive_data_connection(self) -> bool:
        """被动模式(PASV) - 服务器监听，客户端连接"""
        try:
            success, response = self._send_command("PASV")
            if not success or not response.startswith("227"):
                return False

            match = re.search(
                r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)",
                response
            )
            if not match:
                return False

            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
            data_host = f"{h1}.{h2}.{h3}.{h4}"
            data_port = p1 * 256 + p2

            self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_socket.settimeout(self.timeout)
            self.data_socket.connect((data_host, data_port))

            if self.tls_enabled:
                self.data_socket = self._wrap_socket_tls(self.data_socket)

            return True

        except Exception:
            self._close_data_connection()
            return False

    def _setup_active_data_connection(self) -> bool:
        """主动模式(PORT) - 客户端监听，服务器连接"""
        try:
            self.data_listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.data_listen_socket.settimeout(self.timeout)
            self.data_listen_socket.bind(("0.0.0.0", 0))
            self.data_listen_socket.listen(1)

            listen_port = self.data_listen_socket.getsockname()[1]
            local_ip = self.control_socket.getsockname()[0]
            ip_parts = local_ip.replace(".", ",")
            port_high = listen_port // 256
            port_low = listen_port % 256

            success, response = self._send_command(f"PORT {ip_parts},{port_high},{port_low}")
            if not success or not response.startswith("200"):
                self._close_listen_socket()
                return False

            return True

        except Exception:
            self._close_data_connection()
            self._close_listen_socket()
            return False

    def _receive_data(self) -> str:
        """从数据连接接收数据"""
        if self.is_passive:
            sock = self.data_socket
        else:
            try:
                self.data_socket, addr = self.data_listen_socket.accept()
                self.data_socket.settimeout(self.timeout)
                if self.tls_enabled:
                    self.data_socket = self._wrap_socket_tls(self.data_socket)
                sock = self.data_socket
            except socket.timeout:
                return ""

        data = b""
        try:
            while True:
                chunk = sock.recv(self.buffer_size)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass

        return data.decode("utf-8", errors="ignore")

    def _close_data_connection(self):
        """关闭数据连接"""
        if self.data_socket:
            try:
                self.data_socket.close()
            except Exception:
                pass
            self.data_socket = None

    def _close_listen_socket(self):
        """关闭监听socket（主动模式）"""
        if self.data_listen_socket:
            try:
                self.data_listen_socket.close()
            except Exception:
                pass
            self.data_listen_socket = None
