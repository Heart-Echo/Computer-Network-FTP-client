import ssl
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
        self.is_passive: bool = True
        self.timeout: int = 30
        self.tls_enabled: bool = False
        self.buffer_size: int = 8192
