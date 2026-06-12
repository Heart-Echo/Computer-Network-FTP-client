import ssl
import socket
import os
import re
import time as time_module
from typing import Optional, Tuple, List

def modify_ftp_core():
    with open("ftp_core.py", "r", encoding="utf-8") as f:
        content = f.read()

    changes = 0

    # 1) import ssl after docstring
    old = '"""\n\nimport socket'
    new = '"""\nimport ssl\n\nimport socket'
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("1) Added import ssl")

    # 2) tls_enabled in __init__
    old = "self.timeout: int = 30\n        self.buffer_size: int = 8192"
    new = "self.timeout: int = 30\n        self.tls_enabled: bool = False\n        self.buffer_size: int = 8192"
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("2) Added tls_enabled in __init__")

    # 3) reset tls_enabled in close()
    old = 'self.is_logged_in = False\n        self.host = ""\n        self.username = ""'
    new = 'self.is_logged_in = False\n        self.host = ""\n        self.username = ""\n        self.tls_enabled = False'
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("3) Reset tls_enabled in close()")

    # 4) Insert enable_tls() and _wrap_socket_tls() after the login() else clause
    anchor = '            return False, response\n\n    # ==================== FTP命令实现 ===================='
    insertion = '''            return False, response

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
'''
    if anchor in content:
        content = content.replace(anchor, insertion)
        changes += 1
        print("4) Inserted enable_tls() and _wrap_socket_tls()")
    else:
        print("4) ERROR: anchor not found for TLS methods insertion")

    # 5) Auto-detect TLS in login() when USER fails
    old = '''        success, response = self._send_command(f"USER {username}")
        if not success:
            return False, f"USER命令失败: {response}"'''
    new = '''        success, response = self._send_command(f"USER {username}")
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
                return False, f"USER命令失败: {response}"'''
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("5) Added TLS auto-detect in login()")
    else:
        print("5) ERROR: login() USER block not found")

    # 6) Handle 503 response after USER
    old = '''        if response.startswith("230"):
            self.username = username
            self.is_logged_in = True
            return True, response

        # 需要密码，发送PASS命令
        if response.startswith("331"):'''
    new = '''        if response.startswith("230"):
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
        if response.startswith("331"):'''
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("6) Added 503 handling in login()")
    else:
        print("6) ERROR: login() 230/331 block not found")

    # 7) TLS wrap in passive mode
    old = '''            self.data_socket.settimeout(self.timeout)
            self.data_socket.connect((data_host, data_port))

            return True'''
    new = '''            self.data_socket.settimeout(self.timeout)
            self.data_socket.connect((data_host, data_port))

            if self.tls_enabled:
                self.data_socket = self._wrap_socket_tls(self.data_socket)

            return True'''
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("7) Added TLS wrap in passive mode")
    else:
        print("7) ERROR: passive mode block not found")

    # 8) TLS wrap in active mode
    old = '''                self.data_socket.settimeout(self.timeout)
                sock = self.data_socket'''
    new = '''                self.data_socket.settimeout(self.timeout)
                if self.tls_enabled:
                    self.data_socket = self._wrap_socket_tls(self.data_socket)
                sock = self.data_socket'''
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("8) Added TLS wrap in active mode")
    else:
        print("8) ERROR: active mode block not found")

    # 9) Fix: remove self._close_data_connection() in upload_file() after failed STOR
    old = "            self._close_data_connection()\n            return False, f\"上传请求失败: {response}\""
    new = "            return False, f\"上传请求失败: {response}\""
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print("9) Removed redundant _close_data_connection() in upload STOR error path")
    else:
        print("9) NOTE: upload STOR error path not found (may already be fixed)")

    with open("ftp_core.py", "w", encoding="utf-8", newline="") as f:
        f.write(content)

    print(f"\\nTotal changes applied: {changes}")

if __name__ == "__main__":
    import socket as _sock  # ensure socket module is available
    modify_ftp_core()
