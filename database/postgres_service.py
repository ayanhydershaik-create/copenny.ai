"""
database/postgres_service.py
PostgreSQL connection pool and service for CoPenny AI.
Matches the EXACT live Neon database schema:
  - users:         id (integer), email, name, password_hash, firebase_uid, created_at
  - transactions:  id (integer), user_id (integer FK), amount, type (credit|debit), category, description, date, notes, created_at
  - goals:         id (integer), user_id (integer FK), name, target_amount, current_amount, deadline, color, created_at
  - budgets:       id (integer), user_id (integer FK), category, limit_amount, spent_amount, month (varchar), created_at
  - subscriptions: id (integer), user_id (integer FK), name, amount, billing_cycle (monthly|yearly|weekly), next_billing_date, category, status, created_at
  - rules:         id (integer), user_id (integer FK), name, condition (jsonb), action (jsonb), is_active, created_at
  - messages:      id (text), user_id (text), role, content, agent_actions (jsonb), created_at
"""
import os
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("[PostgreSQL] WARNING: psycopg2 not installed.")

import uuid
from urllib.parse import urlparse, parse_qs, unquote


def _parse_database_url(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    params: Dict[str, Any] = {}
    if parsed.username:
        params["user"] = unquote(parsed.username)
    if parsed.password:
        params["password"] = unquote(parsed.password)
    if parsed.hostname:
        params["host"] = parsed.hostname
    if parsed.port:
        params["port"] = parsed.port
    if parsed.path and len(parsed.path) > 1:
        params["database"] = parsed.path.lstrip("/").split("?")[0]
    if parsed.query:
        query_params = parse_qs(parsed.query)
        if "sslmode" in query_params:
            params["sslmode"] = query_params["sslmode"][0]
    return params


def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def _get_user_int_id(pg_service, user_id_str: str) -> Optional[int]:
    """
    Resolve a Firebase UID / string user_id to the integer primary key in the users table.
    Returns None if user does not exist.
    """
    row = pg_service._execute(
        "SELECT id FROM users WHERE firebase_uid = %s OR email = %s LIMIT 1",
        (str(user_id_str), str(user_id_str)),
        fetch="one"
    )
    return row["id"] if row else None


class PostgresService:
    """
    Connection-pooled PostgreSQL service aligned to Neon live schema.
    All queries use parameterized values to prevent SQL injection.
    """

    def __init__(self):
        self._pool: Optional[Any] = None
        self._connect()

    def _connect(self):
        if not PSYCOPG2_AVAILABLE:
            print("[PostgreSQL] psycopg2 not available — skipping connection.")
            return

        db_url = os.getenv("DATABASE_URL", "").strip()

        if db_url and "<username>" not in db_url and "<friend-ip>" not in db_url:
            try:
                conn_params = _parse_database_url(db_url)
                conn_params["minconn"] = 1
                conn_params["maxconn"] = 10
                conn_params["connect_timeout"] = 10

                self._pool = pg_pool.ThreadedConnectionPool(**conn_params)

                conn = self._pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                self._pool.putconn(conn)
                print(
                    f"[PostgreSQL] Connected successfully via DATABASE_URL to "
                    f"'{conn_params.get('database')}' on {conn_params.get('host')}:{conn_params.get('port', 5432)}"
                )
                return
            except Exception as e:
                print(f"[PostgreSQL] Connection to DATABASE_URL failed: {e}")
                self._pool = None
                return

        print("[PostgreSQL] Paused: Waiting for DATABASE_URL.")
        self._pool = None

    def reconnect(self, database_url: Optional[str] = None):
        if self._pool:
            try:
                self._pool.closeall()
            except Exception:
                pass
            self._pool = None
        if database_url:
            os.environ["DATABASE_URL"] = database_url
        self._connect()

    def is_connected(self) -> bool:
        return self._pool is not None

    def _execute(
        self,
        sql: str,
        params: Tuple = (),
        fetch: str = "none",
        commit: bool = False,
        retry: bool = True,
    ) -> Any:
        if not self._pool:
            self._connect()
            if not self._pool:
                raise RuntimeError("PostgreSQL not connected")

        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                result = None
                if fetch == "one":
                    row = cur.fetchone()
                    result = dict(row) if row else None
                elif fetch == "all":
                    rows = cur.fetchall()
                    result = [dict(r) for r in rows]
                elif fetch == "scalar":
                    row = cur.fetchone()
                    result = list(row.values())[0] if row else None
                if commit:
                    conn.commit()
                return result
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as conn_err:
            if conn:
                try:
                    self._pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None
            if retry:
                print(f"[PostgreSQL] Connection dropped ({conn_err}), reconnecting and retrying query...")
                self.reconnect()
                return self._execute(sql, params, fetch=fetch, commit=commit, retry=False)
            raise
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    if getattr(conn, "closed", 0) != 0:
                        self._pool.putconn(conn, close=True)
                    else:
                        self._pool.putconn(conn)
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────────────
    # User Resolution — firebase_uid or email → integer user id
    # ──────────────────────────────────────────────────────────────

    def _resolve_user_id(self, user_id_str: str) -> Optional[int]:
        """
        Resolve string user identifier (firebase UID, email, or 'demo_user') to integer PK.
        For demo_user, returns the first available user or creates a demo row.
        """
        if not user_id_str or user_id_str == "demo_user":
            # Return first user in DB for demo access
            row = self._execute("SELECT id FROM users LIMIT 1", fetch="one")
            return row["id"] if row else None

        row = self._execute(
            "SELECT id FROM users WHERE firebase_uid = %s OR email = %s LIMIT 1",
            (str(user_id_str), str(user_id_str)),
            fetch="one"
        )
        return row["id"] if row else None

    def ensure_user(self, user_id_str: str, email: Optional[str] = None, name: Optional[str] = None) -> Optional[int]:
        """Ensure a user exists for the given firebase_uid. Returns integer id."""
        uid_int = self._resolve_user_id(user_id_str)
        if uid_int is not None:
            return uid_int

        # User doesn't exist — create one (only possible if we have their email or firebase UID)
        em = email or f"user_{user_id_str[:8]}@copenny.ai"
        nm = name or "CoPenny User"
        try:
            row = self._execute(
                """
                INSERT INTO users (email, name, firebase_uid, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (email) DO UPDATE SET firebase_uid = EXCLUDED.firebase_uid
                RETURNING id
                """,
                (em, nm, str(user_id_str)),
                fetch="one", commit=True
            )
            return row["id"] if row else None
        except Exception as e:
            print(f"[PostgreSQL] ensure_user failed: {e}")
            # Return first existing user as fallback
            row = self._execute("SELECT id FROM users LIMIT 1", fetch="one")
            return row["id"] if row else None

    def get_user(self, user_id_str: str) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id_str)
        if not uid_int:
            return None
        row = self._execute(
            "SELECT id, email, name, firebase_uid, created_at FROM users WHERE id = %s",
            (uid_int,), fetch="one"
        )
        if row:
            row["user_id"] = row["id"]
            row["display_name"] = row.get("name")
            row["financial_health_score"] = 750
        return row

    def upsert_user(self, firebase_uid: str, email: str, name: str) -> Optional[Dict[str, Any]]:
        row = self._execute(
            """
            INSERT INTO users (email, name, firebase_uid, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, firebase_uid = EXCLUDED.firebase_uid
            RETURNING id, email, name, firebase_uid, created_at
            """,
            (email, name, firebase_uid),
            fetch="one", commit=True
        )
        if row:
            row["user_id"] = row["id"]
            row["display_name"] = row.get("name")
        return row

    # ──────────────────────────────────────────────────────────────
    # Transactions
    # ──────────────────────────────────────────────────────────────

    def get_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        tx_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []

        conditions = ["user_id = %s"]
        params: list = [uid_int]

        if category:
            conditions.append("category = %s")
            params.append(category)
        if tx_type:
            # Map income/expense → credit/debit
            mapped = {"income": "credit", "expense": "debit"}.get(tx_type, tx_type)
            conditions.append("type = %s")
            params.append(mapped)
        if from_date:
            conditions.append("date >= %s")
            params.append(from_date)
        if to_date:
            conditions.append("date <= %s")
            params.append(to_date)
        if search:
            conditions.append("(description ILIKE %s OR category ILIKE %s)")
            like = f"%{search}%"
            params.extend([like, like])

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        rows = self._execute(
            f"""
            SELECT
              id, id AS transaction_id,
              user_id, amount, type,
              CASE WHEN type='credit' THEN 'income' ELSE 'expense' END AS type_label,
              category,
              description, category AS merchant,
              date, notes,
              created_at
            FROM transactions
            WHERE {where}
            ORDER BY date DESC, created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["transaction_id"] = str(r["id"])
            r["amount"] = float(r["amount"])
            r["date"] = str(r["date"])
        return rows

    def get_transaction(self, tx_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        row = self._execute(
            """
            SELECT id, id AS transaction_id, user_id, amount, type,
              CASE WHEN type='credit' THEN 'income' ELSE 'expense' END AS type_label,
              category, description, category AS merchant, date, notes, created_at
            FROM transactions
            WHERE id = %s AND user_id = %s
            """,
            (int(tx_id), uid_int), fetch="one"
        )
        if row:
            row["id"] = str(row["id"])
            row["transaction_id"] = str(row["id"])
            row["amount"] = float(row["amount"])
            row["date"] = str(row["date"])
        return row

    def create_transaction(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            raise ValueError("Cannot create transaction: user not found")

        raw_amt = float(data.get("amount", 0))
        tx_type_input = data.get("type", "expense").lower()
        # Map income/expense → credit/debit
        mapped_type = {"income": "credit", "expense": "debit"}.get(tx_type_input, tx_type_input)
        if mapped_type not in ("credit", "debit"):
            mapped_type = "debit"
        amount = abs(raw_amt)

        row = self._execute(
            """
            INSERT INTO transactions
              (user_id, amount, type, category, description, date, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, id AS transaction_id, user_id, amount, type, category, description, date, notes, created_at
            """,
            (
                uid_int,
                amount,
                mapped_type,
                data.get("category", "Uncategorized"),
                data.get("description", ""),
                data.get("date", str(date.today())),
                data.get("notes", ""),
            ),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["transaction_id"] = str(row["id"])
            row["amount"] = float(row["amount"])
            row["date"] = str(row["date"])
        return row

    def update_transaction(self, tx_id: str, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        fields, params = [], []
        mapping = {"amount": "amount", "category": "category", "description": "description",
                   "date": "date", "notes": "notes"}
        for f, col in mapping.items():
            if f in data:
                fields.append(f"{col} = %s")
                params.append(data[f])
        if "type" in data:
            mapped = {"income": "credit", "expense": "debit"}.get(data["type"], data["type"])
            fields.append("type = %s")
            params.append(mapped)
        if not fields:
            return self.get_transaction(tx_id, user_id)
        params.extend([int(tx_id), uid_int])
        row = self._execute(
            f"""
            UPDATE transactions SET {', '.join(fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, id AS transaction_id, user_id, amount, type, category, description, date, notes, created_at
            """,
            tuple(params), fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["transaction_id"] = str(row["id"])
            row["amount"] = float(row["amount"])
            row["date"] = str(row["date"])
        return row

    def delete_transaction(self, tx_id: str, user_id: str) -> bool:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return False
        self._execute(
            "DELETE FROM transactions WHERE id = %s AND user_id = %s",
            (int(tx_id), uid_int), commit=True
        )
        return True

    def batch_insert_transactions(self, user_id: str, rows: List[Dict[str, Any]]) -> int:
        if not self._pool or not rows:
            return 0
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            return 0
        conn = self._pool.getconn()
        inserted = 0
        try:
            with conn.cursor() as cur:
                for row in rows:
                    raw_amt = float(row.get("amount", 0))
                    tx_type_input = row.get("type", "expense").lower()
                    mapped_type = {"income": "credit", "expense": "debit"}.get(tx_type_input, tx_type_input)
                    if mapped_type not in ("credit", "debit"):
                        mapped_type = "debit"

                    try:
                        cur.execute(
                            """
                            INSERT INTO transactions
                              (user_id, amount, type, category, description, date, notes, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                            """,
                            (
                                uid_int,
                                abs(raw_amt),
                                mapped_type,
                                row.get("category", "Uncategorized"),
                                row.get("description", ""),
                                row.get("date", str(date.today())),
                                row.get("notes", "Imported via CSV"),
                            )
                        )
                        inserted += 1
                    except Exception as e:
                        print(f"[PostgreSQL] Batch row skip: {e}")
                        conn.rollback()
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[PostgreSQL] Batch insert failed: {e}")
        finally:
            self._pool.putconn(conn)
        return inserted

    def get_transaction_analytics(self, user_id: str) -> Dict[str, Any]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return {"total_income": 0, "total_expense": 0, "net": 0, "by_category": {}, "has_data": False}
        try:
            summary = self._execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN type='credit' THEN amount ELSE 0 END), 0) AS total_income,
                  COALESCE(SUM(CASE WHEN type='debit' THEN amount ELSE 0 END), 0) AS total_expense
                FROM transactions WHERE user_id = %s
                """,
                (uid_int,), fetch="one"
            ) or {}

            by_cat = self._execute(
                """
                SELECT category, SUM(amount) AS total
                FROM transactions WHERE user_id = %s AND type='debit'
                GROUP BY category ORDER BY total DESC LIMIT 10
                """,
                (uid_int,), fetch="all"
            ) or []

            income = float(summary.get("total_income") or 0)
            expense = float(summary.get("total_expense") or 0)
            return {
                "total_income": round(income, 2),
                "total_expense": round(expense, 2),
                "net": round(income - expense, 2),
                "by_category": {r["category"]: float(r["total"]) for r in by_cat},
                "has_data": income > 0 or expense > 0,
            }
        except Exception as e:
            print(f"[PostgreSQL] Analytics error: {e}")
            return {"total_income": 0, "total_expense": 0, "net": 0, "by_category": {}, "has_data": False}

    # ──────────────────────────────────────────────────────────────
    # Goals
    # ──────────────────────────────────────────────────────────────

    def get_goals(self, user_id: str) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []
        rows = self._execute(
            """
            SELECT id, id AS goal_id, user_id, name, target_amount, current_amount,
              current_amount AS saved_amount, deadline, color, created_at
            FROM goals WHERE user_id = %s ORDER BY created_at DESC
            """,
            (uid_int,), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["goal_id"] = str(r["id"])
            r["target_amount"] = float(r["target_amount"] or 0)
            r["current_amount"] = float(r["current_amount"] or 0)
            r["saved_amount"] = float(r["current_amount"] or 0)
            r["deadline"] = str(r["deadline"]) if r.get("deadline") else None
        return rows

    def get_goal(self, goal_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        row = self._execute(
            """
            SELECT id, id AS goal_id, user_id, name, target_amount, current_amount,
              current_amount AS saved_amount, deadline, color, created_at
            FROM goals WHERE id = %s AND user_id = %s
            """,
            (int(goal_id), uid_int), fetch="one"
        )
        if row:
            row["id"] = str(row["id"])
            row["goal_id"] = str(row["id"])
            row["target_amount"] = float(row["target_amount"] or 0)
            row["current_amount"] = float(row["current_amount"] or 0)
            row["saved_amount"] = float(row["current_amount"] or 0)
            row["deadline"] = str(row["deadline"]) if row.get("deadline") else None
        return row

    def create_goal(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            raise ValueError("Cannot create goal: user not found")
        saved_amt = float(data.get("current_amount", data.get("saved_amount", 0)))
        row = self._execute(
            """
            INSERT INTO goals (user_id, name, target_amount, current_amount, deadline, color, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, id AS goal_id, user_id, name, target_amount, current_amount,
              current_amount AS saved_amount, deadline, color, created_at
            """,
            (
                uid_int,
                data.get("name", "Savings Goal"),
                float(data.get("target_amount", 10000)),
                saved_amt,
                data.get("deadline"),
                data.get("color", "#00BFFF"),
            ),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["goal_id"] = str(row["id"])
            row["target_amount"] = float(row["target_amount"] or 0)
            row["current_amount"] = float(row["current_amount"] or 0)
            row["saved_amount"] = float(row["current_amount"] or 0)
        return row

    def update_goal(self, goal_id: str, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        fields, params = [], []
        for f in ["name", "target_amount", "current_amount", "deadline", "color"]:
            if f in data:
                fields.append(f"{f} = %s")
                params.append(data[f])
        if "saved_amount" in data and "current_amount" not in data:
            fields.append("current_amount = %s")
            params.append(float(data["saved_amount"]))
        if not fields:
            return self.get_goal(goal_id, user_id)
        params.extend([int(goal_id), uid_int])
        row = self._execute(
            f"""
            UPDATE goals SET {', '.join(fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, id AS goal_id, user_id, name, target_amount, current_amount,
              current_amount AS saved_amount, deadline, color, created_at
            """,
            tuple(params), fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["goal_id"] = str(row["id"])
            row["target_amount"] = float(row["target_amount"] or 0)
            row["current_amount"] = float(row["current_amount"] or 0)
            row["saved_amount"] = float(row["current_amount"] or 0)
        return row

    def delete_goal(self, goal_id: str, user_id: str) -> bool:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return False
        self._execute("DELETE FROM goals WHERE id = %s AND user_id = %s", (int(goal_id), uid_int), commit=True)
        return True

    # ──────────────────────────────────────────────────────────────
    # Subscriptions
    # ──────────────────────────────────────────────────────────────

    def get_subscriptions(self, user_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []
        where = "user_id = %s"
        params = [uid_int]
        if active_only:
            where += " AND status = 'active'"
        rows = self._execute(
            f"""
            SELECT id, id AS subscription_id, user_id, name, amount,
              billing_cycle, billing_cycle AS cycle,
              next_billing_date, next_billing_date AS next_billing,
              category, status, status = 'active' AS is_active, created_at
            FROM subscriptions WHERE {where} ORDER BY created_at DESC
            """,
            tuple(params), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["subscription_id"] = str(r["id"])
            r["amount"] = float(r["amount"] or 0)
            r["next_billing_date"] = str(r["next_billing_date"]) if r.get("next_billing_date") else None
            r["next_billing"] = r["next_billing_date"]
            r["billing_cycle"] = r.get("billing_cycle", "monthly")
            r["cycle"] = r["billing_cycle"]
            r["is_active"] = r.get("status", "active") == "active"
        return rows

    def create_subscription(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            raise ValueError("Cannot create subscription: user not found")
        cycle = data.get("billing_cycle", data.get("cycle", "monthly")).lower()
        if cycle not in ("monthly", "yearly", "weekly"):
            cycle = "monthly"
        status = "active" if data.get("is_active", data.get("active", True)) else "cancelled"
        next_billing = data.get("next_billing_date", data.get("next_billing"))
        row = self._execute(
            """
            INSERT INTO subscriptions (user_id, name, amount, billing_cycle, next_billing_date, category, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, id AS subscription_id, user_id, name, amount,
              billing_cycle, next_billing_date, category, status, created_at
            """,
            (
                uid_int,
                data.get("name", "Subscription"),
                float(data.get("amount", 0)),
                cycle,
                next_billing,
                data.get("category", "General"),
                status,
            ),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["subscription_id"] = str(row["id"])
            row["amount"] = float(row["amount"] or 0)
            row["cycle"] = row.get("billing_cycle", "monthly")
            row["is_active"] = row.get("status", "active") == "active"
        return row

    def update_subscription(self, sub_id: str, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        fields, params = [], []
        if "name" in data:
            fields.append("name = %s"); params.append(data["name"])
        if "amount" in data:
            fields.append("amount = %s"); params.append(float(data["amount"]))
        if "billing_cycle" in data or "cycle" in data:
            cycle = data.get("billing_cycle", data.get("cycle", "monthly")).lower()
            if cycle not in ("monthly", "yearly", "weekly"):
                cycle = "monthly"
            fields.append("billing_cycle = %s"); params.append(cycle)
        if "next_billing_date" in data or "next_billing" in data:
            fields.append("next_billing_date = %s"); params.append(data.get("next_billing_date", data.get("next_billing")))
        if "category" in data:
            fields.append("category = %s"); params.append(data["category"])
        if "is_active" in data or "active" in data or "status" in data:
            if "status" in data:
                status = data["status"]
            else:
                active = data.get("is_active", data.get("active", True))
                status = "active" if active else "cancelled"
            fields.append("status = %s"); params.append(status)
        if not fields:
            return self.get_subscriptions(user_id)[0] if self.get_subscriptions(user_id) else None
        params.extend([int(sub_id), uid_int])
        row = self._execute(
            f"""
            UPDATE subscriptions SET {', '.join(fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, id AS subscription_id, user_id, name, amount, billing_cycle, next_billing_date, category, status, created_at
            """,
            tuple(params), fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["subscription_id"] = str(row["id"])
            row["amount"] = float(row["amount"] or 0)
            row["is_active"] = row.get("status", "active") == "active"
            row["cycle"] = row.get("billing_cycle", "monthly")
        return row

    def delete_subscription(self, sub_id: str, user_id: str) -> bool:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return False
        self._execute("DELETE FROM subscriptions WHERE id = %s AND user_id = %s", (int(sub_id), uid_int), commit=True)
        return True

    # ──────────────────────────────────────────────────────────────
    # Budgets
    # ──────────────────────────────────────────────────────────────

    def get_budgets(self, user_id: str) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        rows = self._execute(
            """
            SELECT id, id AS budget_id, user_id, category, limit_amount,
              limit_amount AS monthly_limit, spent_amount, spent_amount AS spent,
              month, created_at
            FROM budgets WHERE user_id = %s ORDER BY created_at DESC
            """,
            (uid_int,), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["budget_id"] = str(r["id"])
            r["monthly_limit"] = float(r["limit_amount"] or 0)
            r["spent"] = float(r["spent_amount"] or 0)
        return rows

    def get_budget_utilization(self, user_id: str) -> List[Dict[str, Any]]:
        budgets = self.get_budgets(user_id)
        result = []
        for b in budgets:
            limit = float(b.get("limit_amount") or b.get("monthly_limit") or 1)
            spent = float(b.get("spent_amount") or b.get("spent") or 0)
            pct = round((spent / limit) * 100, 1) if limit > 0 else 0
            result.append({
                **b,
                "utilization_pct": pct,
                "remaining": round(limit - spent, 2),
                "over_budget": spent > limit,
            })
        return result

    def create_budget(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            raise ValueError("Cannot create budget: user not found")
        from datetime import datetime
        now = datetime.now()
        month_str = data.get("month", now.strftime("%Y-%m"))
        limit_amt = float(data.get("limit_amount", data.get("monthly_limit", 0)))
        row = self._execute(
            """
            INSERT INTO budgets (user_id, category, limit_amount, spent_amount, month, created_at)
            VALUES (%s, %s, %s, 0, %s, NOW())
            RETURNING id, id AS budget_id, user_id, category, limit_amount, spent_amount, month, created_at
            """,
            (uid_int, data.get("category", "General"), limit_amt, month_str),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["budget_id"] = str(row["id"])
            row["monthly_limit"] = float(row["limit_amount"] or 0)
            row["spent"] = float(row["spent_amount"] or 0)
        return row

    def update_budget(self, budget_id: str, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        fields, params = [], []
        if "category" in data:
            fields.append("category = %s"); params.append(data["category"])
        if "limit_amount" in data or "monthly_limit" in data:
            fields.append("limit_amount = %s"); params.append(float(data.get("limit_amount", data.get("monthly_limit"))))
        if "spent_amount" in data or "spent" in data:
            fields.append("spent_amount = %s"); params.append(float(data.get("spent_amount", data.get("spent"))))
        if "month" in data:
            fields.append("month = %s"); params.append(data["month"])
        if not fields:
            return self.get_budgets(user_id)[0] if self.get_budgets(user_id) else None
        params.extend([int(budget_id), uid_int])
        row = self._execute(
            f"""
            UPDATE budgets SET {', '.join(fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, id AS budget_id, user_id, category, limit_amount, spent_amount, month, created_at
            """,
            tuple(params), fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["budget_id"] = str(row["id"])
            row["monthly_limit"] = float(row["limit_amount"] or 0)
            row["spent"] = float(row["spent_amount"] or 0)
        return row

    def delete_budget(self, budget_id: str, user_id: str) -> bool:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return False
        self._execute("DELETE FROM budgets WHERE id = %s AND user_id = %s", (int(budget_id), uid_int), commit=True)
        return True

    # ──────────────────────────────────────────────────────────────
    # Rules (IFTTT) — condition (jsonb), action (jsonb), is_active
    # ──────────────────────────────────────────────────────────────

    def get_rules(self, user_id: str) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []
        rows = self._execute(
            """
            SELECT id, id AS rule_id, user_id, name, condition, action, is_active, created_at
            FROM rules WHERE user_id = %s ORDER BY created_at DESC
            """,
            (uid_int,), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["rule_id"] = str(r["id"])
            # Unpack condition/action JSON into top-level keys for compatibility
            cond = r.get("condition") or {}
            if isinstance(cond, str):
                try: cond = json.loads(cond)
                except: cond = {}
            act = r.get("action") or {}
            if isinstance(act, str):
                try: act = json.loads(act)
                except: act = {}
            r["trigger_type"] = cond.get("condition_type", cond.get("type", "threshold"))
            r["condition_field"] = cond.get("condition_field", "balance")
            r["condition_operator"] = cond.get("condition_operator", "<")
            r["condition_value"] = cond.get("condition_value", "0")
            r["action_type"] = act.get("action_type", "alert")
            r["action_config"] = act.get("action_config", {})
        return rows

    def create_rule(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        uid_int = self.ensure_user(user_id)
        if not uid_int:
            raise ValueError("Cannot create rule: user not found")
        condition_data = {
            "condition_type": data.get("condition_type", data.get("trigger_type", "threshold")),
            "condition_field": data.get("condition_field", "balance"),
            "condition_operator": data.get("condition_operator", "<"),
            "condition_value": str(data.get("condition_value", "5000")),
            "natural_language": data.get("natural_language", ""),
        }
        action_data = {
            "action_type": data.get("action_type", "alert"),
            "action_config": data.get("action_config") or data.get("action_params") or {"message": "Alert triggered"}
        }
        row = self._execute(
            """
            INSERT INTO rules (user_id, name, condition, action, is_active, created_at)
            VALUES (%s, %s, %s, %s, TRUE, NOW())
            RETURNING id, id AS rule_id, user_id, name, condition, action, is_active, created_at
            """,
            (
                uid_int,
                data.get("name", "Financial Rule"),
                json.dumps(condition_data, default=_json_serial),
                json.dumps(action_data, default=_json_serial),
            ),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["rule_id"] = str(row["id"])
        return row

    def update_rule(self, rule_id: str, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return None
        fields, params = [], []
        if "name" in data:
            fields.append("name = %s"); params.append(data["name"])
        if "is_active" in data:
            fields.append("is_active = %s"); params.append(bool(data["is_active"]))
        if not fields:
            return None
        params.extend([int(rule_id), uid_int])
        row = self._execute(
            f"""
            UPDATE rules SET {', '.join(fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, id AS rule_id, user_id, name, condition, action, is_active, created_at
            """,
            tuple(params), fetch="one", commit=True
        )
        if row:
            row["id"] = str(row["id"])
            row["rule_id"] = str(row["id"])
        return row

    def delete_rule(self, rule_id: str, user_id: str) -> bool:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return False
        self._execute("DELETE FROM rules WHERE id = %s AND user_id = %s", (int(rule_id), uid_int), commit=True)
        return True

    # ──────────────────────────────────────────────────────────────
    # Messages (Chat History) — id is TEXT in this table
    # ──────────────────────────────────────────────────────────────

    def save_message(self, user_id: str, role: str, content: str, agent: Optional[str] = None) -> Dict[str, Any]:
        mid = str(uuid.uuid4())
        agent_meta = json.dumps({"agent": agent} if agent else {})
        row = self._execute(
            """
            INSERT INTO messages (id, user_id, role, content, agent_actions, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id, id AS message_id, user_id, role, content, agent_actions, created_at
            """,
            (mid, str(user_id), role, content, agent_meta),
            fetch="one", commit=True
        )
        if row:
            row["id"] = str(row.get("id", mid))
            row["message_id"] = row["id"]
        return row or {}

    def get_messages(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._execute(
            """
            SELECT id, id AS message_id, user_id, role, content, agent_actions, created_at
            FROM messages WHERE user_id = %s
            ORDER BY created_at ASC LIMIT %s
            """,
            (str(user_id), limit), fetch="all"
        ) or []
        for r in rows:
            r["id"] = str(r["id"])
            r["message_id"] = str(r["id"])
        return rows

    # ──────────────────────────────────────────────────────────────
    # Financial Health Score
    # ──────────────────────────────────────────────────────────────

    def calculate_health_score(self, user_id: str) -> Dict[str, Any]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return {"total": 750, "score_1000": 750, "components": {}, "has_data": False}
        try:
            summary = self._execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN type='credit' THEN amount ELSE 0 END), 0) AS total_income,
                  COALESCE(SUM(CASE WHEN type='debit' THEN amount ELSE 0 END), 0) AS total_expense
                FROM transactions WHERE user_id = %s
                """,
                (uid_int,), fetch="one"
            ) or {}

            income = float(summary.get("total_income") or 0)
            expense = float(summary.get("total_expense") or 0)

            # Component 1: Savings Ratio (0-300)
            if income > 0:
                savings_ratio = max(0.0, (income - expense) / income)
                savings_score = min(300, int(savings_ratio * 600))
            else:
                savings_score = 150

            # Component 2: Budget Adherence (0-250)
            budgets = self.get_budget_utilization(user_id)
            if budgets:
                within = sum(1 for b in budgets if float(b.get("utilization_pct") or 0) <= 100)
                adherence_score = min(250, int((within / len(budgets)) * 250))
            else:
                adherence_score = 175

            # Component 3: Goal Progress (0-200)
            goals = self.get_goals(user_id)
            if goals:
                progresses = [min(1.0, float(g.get("saved_amount", 0)) / max(float(g.get("target_amount", 1)), 1)) for g in goals]
                goal_score = min(200, int((sum(progresses) / len(progresses)) * 200))
            else:
                goal_score = 140

            # Component 4: Subscription Burden (0-150)
            subscriptions = self.get_subscriptions(user_id, active_only=True)
            monthly_sub_total = sum(float(s.get("amount") or 0) for s in subscriptions if s.get("billing_cycle") == "monthly")
            monthly_income = (income / 3) if income > 0 else 50000.0
            sub_ratio = monthly_sub_total / monthly_income if monthly_income > 0 else 0
            sub_score = min(150, max(0, int((1 - (sub_ratio * 4)) * 150)))

            # Component 5: Spending Stability (0-100)
            stability_score = 80

            total = savings_score + adherence_score + goal_score + sub_score + stability_score
            final_total = max(0, min(1000, total))

            return {
                "total": final_total,
                "score_1000": final_total,
                "components": {
                    "savings_ratio": savings_score,
                    "budget_adherence": adherence_score,
                    "goal_progress": goal_score,
                    "subscription_burden": sub_score,
                    "spending_stability": stability_score,
                },
                "income_90d": round(income, 2),
                "expense_90d": round(expense, 2),
                "has_data": income > 0 or expense > 0,
            }
        except Exception as e:
            print(f"[PostgreSQL] Health score error: {e}")
            return {"total": 750, "score_1000": 750, "components": {}, "has_data": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Anomaly Detection
    # ──────────────────────────────────────────────────────────────

    def get_anomalies(self, user_id: str, lookback_days: int = 90) -> List[Dict[str, Any]]:
        uid_int = self._resolve_user_id(user_id)
        if not uid_int:
            return []
        try:
            rows = self._execute(
                """
                WITH stats AS (
                  SELECT
                    category,
                    AVG(amount) AS avg_amount,
                    STDDEV(amount) AS std_amount,
                    COUNT(*) AS tx_count
                  FROM transactions
                  WHERE user_id = %s AND type = 'debit'
                  GROUP BY category
                  HAVING COUNT(*) >= 2
                ),
                scored AS (
                  SELECT
                    t.id,
                    t.date,
                    t.description,
                    t.category AS merchant,
                    t.amount,
                    t.category,
                    s.avg_amount,
                    s.std_amount,
                    ROUND(
                      ((t.amount - s.avg_amount) / NULLIF(s.std_amount, 0))::numeric, 2
                    ) AS z_score
                  FROM transactions t
                  JOIN stats s ON t.category = s.category
                  WHERE t.user_id = %s
                    AND t.type = 'debit'
                    AND s.std_amount > 0
                    AND ABS(t.amount - s.avg_amount) >= 1.5 * s.std_amount
                )
                SELECT * FROM scored ORDER BY ABS(z_score) DESC LIMIT 10
                """,
                (uid_int, uid_int),
                fetch="all"
            ) or []

            anomalies = []
            for row in rows:
                z = float(row.get("z_score") or 0)
                confidence = min(99, int(min(abs(z), 4.0) / 4.0 * 100))
                avg = float(row.get("avg_amount") or 0)
                amt = float(row.get("amount") or 0)
                anomalies.append({
                    "id": str(row["id"]),
                    "date": str(row.get("date", "")),
                    "description": row.get("description", ""),
                    "merchant": row.get("merchant", ""),
                    "amount": amt,
                    "category": row.get("category", ""),
                    "confidence": confidence,
                    "z_score": z,
                    "avg_for_category": round(avg, 2),
                    "reason": f"This ₹{amt:,.0f} {row.get('category')} expense is {abs(z):.1f} standard deviations above your average ₹{avg:,.0f}."
                })
            return anomalies
        except Exception as e:
            print(f"[PostgreSQL] Anomaly query error: {e}")
            return []


# Singleton
_pg_service: Optional[PostgresService] = None


def get_postgres_service() -> PostgresService:
    global _pg_service
    if _pg_service is None:
        _pg_service = PostgresService()
    return _pg_service
