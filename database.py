"""
PostgreSQL数据库模块 - 存储FTP连接历史、传输记录和断点续传信息
"""

import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class FTDatabase:
    """FTP客户端数据库管理类"""

    def __init__(self, host: str = "localhost", port: int = 5432,
                 database: str = "ftp_client", user: str = "postgres",
                 password: str = "050528"):
        self.conn = None
        self.config = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }

    def connect(self) -> Tuple[bool, str]:
        """连接到PostgreSQL数据库"""
        try:
            self.conn = psycopg2.connect(**self.config)
            self.conn.autocommit = True
            return True, "数据库连接成功"
        except psycopg2.OperationalError as e:
            return False, f"数据库连接失败: {str(e)}"
        except Exception as e:
            return False, f"数据库错误: {str(e)}"

    def init_tables(self) -> Tuple[bool, str]:
        """初始化数据库表结构"""
        if not self.conn:
            success, msg = self.connect()
            if not success:
                return False, msg

        create_statements = [
            """
            CREATE TABLE IF NOT EXISTS connection_history (
                id SERIAL PRIMARY KEY,
                host VARCHAR(255) NOT NULL,
                port INTEGER DEFAULT 21,
                username VARCHAR(100),
                connection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                disconnect_time TIMESTAMP,
                status VARCHAR(20) DEFAULT 'connected'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transfer_records (
                id SERIAL PRIMARY KEY,
                connection_id INTEGER REFERENCES connection_history(id),
                transfer_type VARCHAR(10) NOT NULL,  -- 'upload' 或 'download'
                remote_file VARCHAR(500) NOT NULL,
                local_path VARCHAR(500) NOT NULL,
                file_size BIGINT DEFAULT 0,
                transferred_bytes BIGINT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'failed', 'paused'
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                resume_supported BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS resume_points (
                id SERIAL PRIMARY KEY,
                transfer_id INTEGER REFERENCES transfer_records(id) ON DELETE CASCADE,
                byte_offset BIGINT NOT NULL,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(transfer_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS favorite_servers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INTEGER DEFAULT 21,
                username VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(host, port, username)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_connection_history_host 
            ON connection_history(host)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_transfer_records_connection 
            ON transfer_records(connection_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_transfer_records_status 
            ON transfer_records(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_resume_points_transfer 
            ON resume_points(transfer_id)
            """
        ]

        try:
            cursor = self.conn.cursor()
            for stmt in create_statements:
                cursor.execute(stmt)
            cursor.close()
            return True, "数据库表初始化成功"
        except Exception as e:
            return False, f"表初始化失败: {str(e)}"

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    # ==================== 连接历史管理 ====================

    def add_connection_record(self, host: str, port: int, username: str) -> Optional[int]:
        """添加连接记录，返回记录ID"""
        if not self.conn:
            return None
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO connection_history (host, port, username, connection_time, status)
                   VALUES (%s, %s, %s, %s, 'connected')
                   RETURNING id""",
                (host, port, username, datetime.now())
            )
            conn_id = cursor.fetchone()[0]
            cursor.close()
            return conn_id
        except Exception:
            return None

    def update_disconnect(self, connection_id: int):
        """更新断开连接时间"""
        if not self.conn or not connection_id:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE connection_history 
                   SET disconnect_time = %s, status = 'disconnected'
                   WHERE id = %s""",
                (datetime.now(), connection_id)
            )
            cursor.close()
        except Exception:
            pass

    def get_connection_history(self, limit: int = 20) -> List[Dict]:
        """获取最近的连接历史"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                """SELECT * FROM connection_history 
                   ORDER BY connection_time DESC LIMIT %s""",
                (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    # ==================== 传输记录管理 ====================

    def add_transfer_record(self, connection_id: int, transfer_type: str,
                            remote_file: str, local_path: str,
                            file_size: int = 0) -> Optional[int]:
        """添加传输记录，返回记录ID"""
        if not self.conn:
            return None
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO transfer_records 
                   (connection_id, transfer_type, remote_file, local_path, 
                    file_size, status, resume_supported)
                   VALUES (%s, %s, %s, %s, %s, 'in_progress', TRUE)
                   RETURNING id""",
                (connection_id, transfer_type, remote_file, local_path, file_size)
            )
            transfer_id = cursor.fetchone()[0]
            cursor.close()
            return transfer_id
        except Exception:
            return None

    def update_transfer_progress(self, transfer_id: int, transferred_bytes: int):
        """更新传输进度"""
        if not self.conn or not transfer_id:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE transfer_records 
                   SET transferred_bytes = %s
                   WHERE id = %s""",
                (transferred_bytes, transfer_id)
            )
            cursor.close()
        except Exception:
            pass

    def complete_transfer(self, transfer_id: int, transferred_bytes: int):
        """标记传输完成"""
        if not self.conn or not transfer_id:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE transfer_records 
                   SET status = 'completed', transferred_bytes = %s, 
                       end_time = %s
                   WHERE id = %s""",
                (transferred_bytes, datetime.now(), transfer_id)
            )
            cursor.close()
        except Exception:
            pass

    def fail_transfer(self, transfer_id: int):
        """标记传输失败"""
        if not self.conn or not transfer_id:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """UPDATE transfer_records 
                   SET status = 'failed', end_time = %s
                   WHERE id = %s""",
                (datetime.now(), transfer_id)
            )
            cursor.close()
        except Exception:
            pass

    def pause_transfer(self, transfer_id: int, transferred_bytes: int):
        """暂停传输并保存断点"""
        if not self.conn or not transfer_id:
            return
        try:
            cursor = self.conn.cursor()
            # 更新传输状态为暂停
            cursor.execute(
                """UPDATE transfer_records 
                   SET status = 'paused', transferred_bytes = %s
                   WHERE id = %s""",
                (transferred_bytes, transfer_id)
            )
            # 保存断点续传位置
            cursor.execute(
                """INSERT INTO resume_points (transfer_id, byte_offset)
                   VALUES (%s, %s)
                   ON CONFLICT (transfer_id) 
                   DO UPDATE SET byte_offset = %s, saved_at = %s""",
                (transfer_id, transferred_bytes, transferred_bytes, datetime.now())
            )
            cursor.close()
        except Exception:
            pass

    def get_resume_offset(self, transfer_id: int) -> int:
        """获取断点续传的字节偏移量"""
        if not self.conn or not transfer_id:
            return 0
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT byte_offset FROM resume_points WHERE transfer_id = %s""",
                (transfer_id,)
            )
            row = cursor.fetchone()
            cursor.close()
            return row[0] if row else 0
        except Exception:
            return 0

    def get_incomplete_transfers(self) -> List[Dict]:
        """获取所有未完成的传输记录（用于断点续传恢复）"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                """SELECT t.*, r.byte_offset as resume_offset
                   FROM transfer_records t
                   LEFT JOIN resume_points r ON t.id = r.transfer_id
                   WHERE t.status IN ('in_progress', 'paused')
                   ORDER BY t.created_at DESC"""
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def get_transfer_history(self, limit: int = 50) -> List[Dict]:
        """获取传输历史记录"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                """SELECT * FROM transfer_records 
                   ORDER BY created_at DESC LIMIT %s""",
                (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    # ==================== 收藏服务器管理 ====================

    def add_favorite_server(self, name: str, host: str, port: int,
                            username: str) -> Tuple[bool, str]:
        """添加收藏服务器"""
        if not self.conn:
            return False, "数据库未连接"
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO favorite_servers (name, host, port, username)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (host, port, username) DO NOTHING""",
                (name, host, port, username)
            )
            cursor.close()
            return True, "服务器已收藏"
        except Exception as e:
            return False, f"收藏失败: {str(e)}"

    def get_favorite_servers(self) -> List[Dict]:
        """获取所有收藏的服务器"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                """SELECT * FROM favorite_servers ORDER BY name"""
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

    def remove_favorite_server(self, server_id: int) -> Tuple[bool, str]:
        """删除收藏的服务器"""
        if not self.conn:
            return False, "数据库未连接"
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """DELETE FROM favorite_servers WHERE id = %s""",
                (server_id,)
            )
            cursor.close()
            return True, "已删除收藏"
        except Exception as e:
            return False, f"删除失败: {str(e)}"

    # ==================== 统计功能 ====================

    def get_statistics(self) -> Dict:
        """获取传输统计信息"""
        stats = {
            "total_uploads": 0,
            "total_downloads": 0,
            "total_upload_bytes": 0,
            "total_download_bytes": 0,
            "completed_transfers": 0,
            "failed_transfers": 0
        }
        if not self.conn:
            return stats
        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # 上传统计
            cursor.execute(
                """SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_bytes
                   FROM transfer_records 
                   WHERE transfer_type = 'upload' AND status = 'completed'"""
            )
            row = cursor.fetchone()
            if row:
                stats["total_uploads"] = row["count"]
                stats["total_upload_bytes"] = row["total_bytes"]

            # 下载统计
            cursor.execute(
                """SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_bytes
                   FROM transfer_records 
                   WHERE transfer_type = 'download' AND status = 'completed'"""
            )
            row = cursor.fetchone()
            if row:
                stats["total_downloads"] = row["count"]
                stats["total_download_bytes"] = row["total_bytes"]

            # 完成/失败统计
            cursor.execute(
                """SELECT status, COUNT(*) as count FROM transfer_records 
                   WHERE status IN ('completed', 'failed') GROUP BY status"""
            )
            for row in cursor.fetchall():
                if row["status"] == "completed":
                    stats["completed_transfers"] = row["count"]
                elif row["status"] == "failed":
                    stats["failed_transfers"] = row["count"]

            cursor.close()
        except Exception:
            pass
        return stats

    def format_bytes(self, size: int) -> str:
        """格式化字节大小为可读字符串"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"