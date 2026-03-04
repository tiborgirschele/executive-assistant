from __future__ import annotations


def is_egress_denied(
    *,
    tenant: str,
    person_id: str,
    task_type: str,
    data_class: str,
) -> bool:
    """
    Tenant/person/task/data-class scoped egress policy check.
    Best-effort: returns False when DB/table/config is unavailable.
    """
    tenant_key = str(tenant or "").strip() or "*"
    person_key = str(person_id or "").strip()
    task = str(task_type or "").strip() or "*"
    dclass = str(data_class or "").strip() or "*"
    try:
        from app.db import get_db

        db = get_db()
        row = db.fetchone(
            """
            SELECT action
            FROM llm_egress_policies
            WHERE active = TRUE
              AND (tenant = %s OR tenant = '*')
              AND (
                    COALESCE(person_id, '') = ''
                    OR person_id = '*'
                    OR person_id = %s
                  )
              AND (task_type = %s OR task_type = '*')
              AND (data_class = %s OR data_class = '*')
            ORDER BY
              CASE WHEN tenant = %s THEN 0 ELSE 1 END,
              CASE
                WHEN person_id = %s THEN 0
                WHEN person_id = '*' THEN 1
                WHEN COALESCE(person_id, '') = '' THEN 2
                ELSE 3
              END,
              CASE WHEN task_type = %s THEN 0 ELSE 1 END,
              CASE WHEN data_class = %s THEN 0 ELSE 1 END,
              updated_at DESC
            LIMIT 1
            """,
            (
                tenant_key,
                person_key,
                task,
                dclass,
                tenant_key,
                person_key,
                task,
                dclass,
            ),
        )
        action = str((row or {}).get("action") or "allow").strip().lower()
        return action == "deny"
    except Exception:
        return False
