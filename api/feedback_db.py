"""
反馈数据库模块
使用SQLite存储对话消息和用户反馈（点赞/踩），支持越用越好用的数据积累。
"""
import sqlite3
import os
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict

from rag_agent_project.utils.path_tool import get_abs_path
from rag_agent_project.utils.logger_handler import logger

DB_PATH = get_abs_path("data/feedback.db")
_db_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                agent TEXT,
                intent TEXT,
                tools_called TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                session_id TEXT,
                rating TEXT NOT NULL,
                comment TEXT,
                query TEXT,
                response TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (message_id) REFERENCES messages(id)
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating);
            CREATE INDEX IF NOT EXISTS idx_feedback_message ON feedback(message_id);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        """)
        conn.commit()
        logger.info(f"[FeedbackDB] 数据库已初始化: {DB_PATH}")
    except Exception as e:
        logger.error(f"[FeedbackDB] 初始化失败: {e}")
    finally:
        conn.close()


def save_message(msg_id: str, session_id: str, role: str, content: str,
                 agent: str = None, intent: str = None, tools_called: list = None):
    """保存一条消息"""
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO messages (id, session_id, role, content, agent, intent, tools_called, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (msg_id, session_id, role, content, agent, intent,
                 json.dumps(tools_called, ensure_ascii=False) if tools_called else None,
                 datetime.now().isoformat())
            )
            conn.commit()
        except Exception as e:
            logger.error(f"[FeedbackDB] 保存消息失败: {e}")
        finally:
            conn.close()


def save_feedback(message_id: str, rating: str, comment: str = None,
                  session_id: str = None, query: str = None, response: str = None) -> dict:
    """
    保存用户反馈
    :param message_id: 消息ID
    :param rating: "like" 或 "dislike"
    :param comment: 可选评论
    :return: 保存结果
    """
    with _db_lock:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO feedback (message_id, session_id, rating, comment, query, response, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (message_id, session_id, rating, comment, query, response, datetime.now().isoformat())
            )
            conn.commit()
            feedback_id = cursor.lastrowid
            logger.info(f"[FeedbackDB] 反馈已保存: id={feedback_id}, message={message_id}, rating={rating}")
            return {"id": feedback_id, "message_id": message_id, "rating": rating, "status": "saved"}
        except Exception as e:
            logger.error(f"[FeedbackDB] 保存反馈失败: {e}")
            return {"error": str(e)}
        finally:
            conn.close()


def get_feedback_stats() -> dict:
    """获取反馈统计"""
    with _db_lock:
        conn = _get_conn()
        try:
            likes = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE rating='like'").fetchone()["cnt"]
            dislikes = conn.execute("SELECT COUNT(*) as cnt FROM feedback WHERE rating='dislike'").fetchone()["cnt"]
            total = conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
            # 按意图统计（关联messages表）
            intent_stats = {}
            rows = conn.execute("""
                SELECT m.intent, f.rating, COUNT(*) as cnt
                FROM feedback f
                JOIN messages m ON f.message_id = m.id
                WHERE m.intent IS NOT NULL
                GROUP BY m.intent, f.rating
            """).fetchall()
            for row in rows:
                intent = row["intent"]
                if intent not in intent_stats:
                    intent_stats[intent] = {"like": 0, "dislike": 0}
                intent_stats[intent][row["rating"]] = row["cnt"]

            return {
                "total": total,
                "likes": likes,
                "dislikes": dislikes,
                "satisfaction_rate": round(likes / total * 100, 1) if total > 0 else 0,
                "by_intent": intent_stats,
            }
        except Exception as e:
            logger.error(f"[FeedbackDB] 统计失败: {e}")
            return {"error": str(e)}
        finally:
            conn.close()


def get_low_rated_responses(limit: int = 20) -> List[Dict]:
    """获取被踩的回答，用于后续优化"""
    with _db_lock:
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT f.message_id, f.query, f.response, f.comment, f.timestamp, m.intent, m.tools_called
                FROM feedback f
                LEFT JOIN messages m ON f.message_id = m.id
                WHERE f.rating = 'dislike'
                ORDER BY f.timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[FeedbackDB] 获取低分回答失败: {e}")
            return []
        finally:
            conn.close()


def get_message_history(session_id: str, limit: int = 50) -> List[Dict]:
    """获取会话消息历史"""
    with _db_lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[FeedbackDB] 获取历史失败: {e}")
            return []
        finally:
            conn.close()
