import json
from dataclasses import dataclass
from app.db import get_db

@dataclass(frozen=True)
class SecretRef:
    tenant: str
    connector_type: str
    rail_type: str
    credential_alias: str
    allowed_workflows: list
    environment: str
    metadata: dict

def get_secret_ref(tenant: str, connector_type: str, environment: str = "prod") -> SecretRef:
    db = get_db()
    row = db.fetchone("SELECT tenant, connector_type, rail_type, credential_alias, allowed_workflows_json, environment, metadata_json FROM secret_refs WHERE tenant = %s AND connector_type = %s AND environment = %s AND status = 'active'", (tenant, connector_type, environment))
    
    if not row:
        return SecretRef(tenant, connector_type, "api_secret", "dummy", [], environment, {})
        
    r = row if hasattr(row, 'keys') else {"tenant": row[0], "connector_type": row[1], "rail_type": row[2], "credential_alias": row[3], "allowed_workflows_json": row[4], "environment": row[5], "metadata_json": row[6]}
    
    def _parse(val):
        if isinstance(val, (dict, list)): return val
        if isinstance(val, str):
            try: return json.loads(val)
            except: pass
        return {}
        
    return SecretRef(r['tenant'], r['connector_type'], r['rail_type'], r['credential_alias'], _parse(r['allowed_workflows_json']), r['environment'], _parse(r['metadata_json']))
