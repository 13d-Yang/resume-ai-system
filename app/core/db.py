# -*- coding: utf-8 -*-
"""数据库连接池（DBUtils PooledDB）。

商业项目约定：
- 全应用共享一个连接池，禁止在业务代码里每次请求 pymysql.connect；
- 统一通过 db_cursor() 上下文管理器取游标，异常自动回滚、正常自动提交；
- 退出 with 块时连接自动归还连接池（并非真正关闭）。
"""
import logging
from contextlib import contextmanager

import pymysql
from dbutils.pooled_db import PooledDB

from app.config import DB_POOL_CONFIG, MYSQL_CONFIG

# 进程级单例连接池
_pool = PooledDB(creator=pymysql, **DB_POOL_CONFIG, **MYSQL_CONFIG)


@contextmanager
def db_cursor(dict_cursor: bool = True):
    """获取游标上下文。

    用法::

        with db_cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()

    - 正常退出自动 commit
    - 抛异常自动 rollback
    - 连接最终归还连接池
    """
    conn = _pool.connection()
    cur = None
    try:
        cursor_class = pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
        cur = conn.cursor(cursor_class)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        logging.exception("【数据库操作异常，已回滚】")
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()
