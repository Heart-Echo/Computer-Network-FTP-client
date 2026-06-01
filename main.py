"""
FTP客户端 - 主入口文件
计算机网络实验项目
使用Socket编程实现FTP协议，PostgreSQL存储传输记录
"""

import sys
import os

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import FTPClientGUI


def main():
    """启动FTP客户端图形界面"""
    print("=" * 60)
    print("  FTP客户端 - 计算机网络实验")
    print("  基于Socket编程，实现RFC 959 FTP协议")
    print("  支持主动/被动模式、断点续传、PostgreSQL存储")
    print("=" * 60)
    print()
    
    try:
        app = FTPClientGUI()
        app.run()
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()