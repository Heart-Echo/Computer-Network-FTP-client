"""
FTP连接诊断工具 - 帮助你排查FTP连接失败的原因
支持普通FTP和显式FTPS (AUTH TLS)
"""
import socket
import ssl


def recv_response(sock, timeout=10) -> str:
    """接收一行FTP响应"""
    sock.settimeout(timeout)
    data = sock.recv(4096)
    return data.decode("utf-8", errors="replace").strip()


def send_cmd(sock, cmd: str):
    """发送FTP命令"""
    sock.sendall(f"{cmd}\r\n".encode())


def diagnose_ftp_connection(host: str = "127.0.0.1", port: int = 21):
    """一步步诊断FTP连接"""

    print("=" * 60)
    print("FTP连接诊断工具")
    print("=" * 60)
    print()

    # 步骤1: 测试TCP连接
    print(f"步骤1: 测试TCP连接到 {host}:{port} ...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)

    try:
        s.connect((host, port))
        print(f"  ✅ TCP连接成功！")
        print()
    except socket.timeout:
        print(f"  ❌ 连接超时 - 服务器无响应")
        print(f"     可能原因: 服务器未启动 / 防火墙阻止 / 端口不对")
        print()
        return
    except ConnectionRefusedError:
        print(f"  ❌ 连接被拒绝 - 端口 {port} 上没有服务在监听")
        print(f"     可能原因: FTP服务器未启动 / 端口号错误")
        print()
        return
    except socket.gaierror:
        print(f"  ❌ 无法解析主机名: {host}")
        print()
        return
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        print()
        return

    # 步骤2: 接收服务器欢迎消息
    print("步骤2: 接收服务器欢迎消息...")
    try:
        welcome = recv_response(s)
        print(f"  服务器响应: {welcome}")
        if "220" in welcome:
            print(f"  ✅ 服务器就绪")
        else:
            print(f"  ⚠️ 非标准欢迎消息")
        print()
    except Exception as e:
        print(f"  ❌ 接收失败: {e}")
        s.close()
        return

    # 标记是否已升级TLS
    is_tls = False

    # 步骤3: 获取用户名
    test_user = input("请输入要测试的用户名 (默认: test): ").strip() or "test"
    print()

    # ---- 尝试发送 USER，如果服务器要求 AUTH 就先升级 TLS ----
    user_response = ""
    need_auth = True  # 是否需要先AUTH

    print(f"步骤3: 发送 USER {test_user} ...")
    try:
        send_cmd(s, f"USER {test_user}")
        user_response = recv_response(s)
        print(f"  服务器响应: {user_response}")

        if "331" in user_response:
            print(f"  ✅ 用户名正确，等待密码 (无需TLS)")
            need_auth = False
        elif "230" in user_response:
            print(f"  ✅ 直接登录成功（无需密码/无需TLS）")
            need_auth = False
        elif "503" in user_response and "AUTH" in user_response.upper():
            print(f"  ⚠️ 服务器要求先使用 AUTH TLS 加密")
            need_auth = True
        else:
            print(f"  ⚠️ 非标准响应")
            # 可能也需要AUTH，继续尝试
    except Exception as e:
        print(f"  ❌ 发送失败: {e}")
        s.close()
        return

    # 步骤3.5: 如果服务器要求 AUTH TLS
    if need_auth:
        print()
        print("步骤3.5: 协商 TLS 加密 (AUTH TLS) ...")
        try:
            send_cmd(s, "AUTH TLS")
            auth_response = recv_response(s)
            print(f"  服务器响应: {auth_response}")

            if "234" in auth_response:
                print(f"  ✅ 服务器同意TLS协商，正在升级连接...")
                # 升级为TLS连接
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                s_tls = context.wrap_socket(s, server_hostname=host)
                s = s_tls  # 替换为TLS socket
                is_tls = True
                print(f"  ✅ TLS连接已建立")
            else:
                print(f"  ❌ 服务器不支持 AUTH TLS")
                # 继续明码尝试
        except ssl.SSLError as e:
            print(f"  ❌ TLS握手失败: {e}")
            print(f"     可能原因: 服务器TLS证书问题")
            s.close()
            return
        except Exception as e:
            print(f"  ❌ AUTH TLS失败: {e}")
            s.close()
            return

        # 重新发送 USER (在TLS加密通道中)
        print()
        print(f"步骤3b: 在TLS加密通道中重新发送 USER {test_user} ...")
        try:
            send_cmd(s, f"USER {test_user}")
            user_response = recv_response(s)
            print(f"  服务器响应: {user_response}")
            if "331" in user_response:
                print(f"  ✅ 用户名正确，等待密码")
            elif "230" in user_response:
                print(f"  ✅ 直接登录成功（无需密码）")
            else:
                print(f"  ⚠️ 非标准响应")
            print()
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")
            s.close()
            return

    # 步骤4: 测试密码
    if "331" in user_response:
        test_pass = input("请输入密码 (默认: 123456): ").strip() or "123456"
        print()
        print(f"步骤4: 发送 PASS *** ...")

        try:
            send_cmd(s, f"PASS {test_pass}")
            pass_response = recv_response(s)
            print(f"  服务器响应: {pass_response}")
            if "230" in pass_response:
                print(f"  ✅ 登录成功！")
            elif "530" in pass_response:
                print(f"  ❌ 登录失败 - 密码错误或用户未启用")
            else:
                print(f"  ⚠️ 非标准响应")
            print()
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")

    # 步骤5: 测试PASV被动模式
    print("步骤5: 测试 PASV (被动模式) ...")
    try:
        send_cmd(s, "PASV")
        pasv_response = recv_response(s)
        print(f"  服务器响应: {pasv_response}")
        if "227" in pasv_response:
            print(f"  ✅ 被动模式可用")
        else:
            print(f"  ⚠️ 被动模式可能不可用")
        print()
    except Exception as e:
        print(f"  ❌ 发送失败: {e}")

    # 步骤6: 退出
    print("步骤6: 发送 QUIT (退出) ...")
    try:
        send_cmd(s, "QUIT")
        quit_response = recv_response(s)
        print(f"  服务器响应: {quit_response}")
        if "221" in quit_response:
            print(f"  ✅ 正常退出")
        print()
    except Exception as e:
        print(f"  ⚠️ 退出异常: {e}")

    s.close()
    print("=" * 60)
    print("诊断完成！")
    print()
    if is_tls:
        print("🔒 本次连接使用了 TLS 加密")

    # 总结
    print()
    print("💡 排查建议:")
    print("  1. 确认 FileZilla Server 是否已启动 (管理界面显示 'Server is online')")
    print("  2. 确认 FTP 监听端口是否是 21 (Server → Server listeners)")
    print("  3. 确认用户是否已创建且启用 (Rights management → Users)")
    print("  4. 确认用户的 Mount points 是否已设置")
    print("  5. Windows防火墙是否阻止了21端口")
    print("  6. 如果服务器要求FTPS，请在FTP客户端中启用 '显式TLS/SSL' 或 'FTP over TLS'")
    print()
    print("如果想测试公共FTP服务器，可以连接:")
    print("  主机: test.rebex.net, 端口: 21, 用户: demo, 密码: password")
    print("  主机: ftp.gnu.org, 端口: 21, 匿名登录")


if __name__ == "__main__":
    host = input("请输入FTP服务器地址 (默认 127.0.0.1): ").strip() or "127.0.0.1"
    port_input = input("请输入端口 (默认 21): ").strip() or "21"
    port = int(port_input)
    diagnose_ftp_connection(host, port)