import os
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from google.cloud import firestore
from common.config.settings import settings

logger = logging.getLogger("common.firestore")

_client: Optional[firestore.AsyncClient] = None


def get_firestore_client() -> firestore.AsyncClient:
    global _client
    if _client is None:
        project = (
            settings.FIRESTORE_PROJECT_ID
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or "pix-guard-poc"
        )
        database = settings.FIRESTORE_DATABASE or "(default)"
        _client = firestore.AsyncClient(project=project, database=database)
    return _client


async def init_firestore_seeds(db: Optional[firestore.AsyncClient] = None):
    """Garante usuários iniciais para a PoC e demonstração."""
    client = db or get_firestore_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    seeds = [
        {"id": "usr_abc123", "cpf_cnpj": "12345678901", "name": "Alice Sender", "status": "ACTIVE"},
        {"id": "usr_xyz789", "cpf_cnpj": "98765432100", "name": "Bob Receiver", "status": "ACTIVE"},
        {"id": "usr_livre_01", "cpf_cnpj": "12312312312", "name": "Você", "status": "ACTIVE"},
    ]
    for s in seeds:
        doc_ref = client.collection("users").document(s["id"])
        doc = await doc_ref.get()
        if not doc.exists:
            payload = {**s, "created_at": now_iso, "updated_at": now_iso}
            await doc_ref.set(payload)
            logger.info(f"Seed Firestore provisionado: {s['id']} ({s['name']})")


async def get_user_by_id(user_id: str, db: Optional[firestore.AsyncClient] = None) -> Optional[dict]:
    client = db or get_firestore_client()
    doc = await client.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None


async def get_user_by_cpf(cpf_cnpj: str, db: Optional[firestore.AsyncClient] = None) -> Optional[dict]:
    client = db or get_firestore_client()
    query = client.collection("users").where(filter=firestore.FieldFilter("cpf_cnpj", "==", cpf_cnpj)).limit(1)
    async for d in query.stream():
        return d.to_dict()
    return None


async def ensure_user(user_id: str, cpf_cnpj: str, name: str, db: Optional[firestore.AsyncClient] = None) -> dict:
    client = db or get_firestore_client()
    existing = await get_user_by_id(user_id, client)
    if existing:
        return existing
    existing_cpf = await get_user_by_cpf(cpf_cnpj, client)
    if existing_cpf:
        return existing_cpf

    now_iso = datetime.now(timezone.utc).isoformat()
    data = {
        "id": user_id,
        "cpf_cnpj": cpf_cnpj,
        "name": name,
        "status": "ACTIVE",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await client.collection("users").document(user_id).set(data)
    logger.info(f"Usuário auto-provisionado no Firestore: {user_id} ({name})")
    return data


async def block_user(
    user_id: str,
    reason: str,
    total_threats: int,
    triggered_by_tx: Optional[str] = None,
    details: Optional[str] = None,
    db: Optional[firestore.AsyncClient] = None,
) -> dict:
    client = db or get_firestore_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    doc_ref = client.collection("users").document(user_id)
    doc = await doc_ref.get()

    if not doc.exists:
        data = {
            "id": user_id,
            "cpf_cnpj": f"CPF_{user_id[-8:]}",
            "name": f"User {user_id}",
            "status": "BLOCKED_SUSPICIOUS",
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await doc_ref.set(data)
    else:
        data = doc.to_dict()
        data["status"] = "BLOCKED_SUSPICIOUS"
        data["updated_at"] = now_iso
        await doc_ref.update({"status": "BLOCKED_SUSPICIOUS", "updated_at": now_iso})

    logger.warning(
        f"USUÁRIO BLOQUEADO (Firestore): id={user_id} status=BLOCKED_SUSPICIOUS "
        f"motivo={reason} total_ameacas={total_threats} tx={triggered_by_tx}"
    )
    return data


async def unblock_user(user_id: str, db: Optional[firestore.AsyncClient] = None) -> Optional[dict]:
    client = db or get_firestore_client()
    doc_ref = client.collection("users").document(user_id)
    doc = await doc_ref.get()
    if not doc.exists:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    await doc_ref.update({"status": "ACTIVE", "updated_at": now_iso})
    data = doc.to_dict()
    data["status"] = "ACTIVE"
    data["updated_at"] = now_iso
    logger.info(f"USUÁRIO DESBLOQUEADO (Firestore): id={user_id}")
    return data


async def list_users(db: Optional[firestore.AsyncClient] = None) -> List[dict]:
    client = db or get_firestore_client()
    users = []
    async for d in client.collection("users").stream():
        users.append(d.to_dict())
    return users


async def get_threat_by_tx(transaction_id: str, db: Optional[firestore.AsyncClient] = None) -> Optional[dict]:
    client = db or get_firestore_client()
    query = client.collection("threat_logs").where(filter=firestore.FieldFilter("transaction_id", "==", transaction_id)).limit(1)
    async for d in query.stream():
        return d.to_dict()
    return None


async def get_threats_by_user(user_id: str, db: Optional[firestore.AsyncClient] = None) -> List[dict]:
    client = db or get_firestore_client()
    threats = []
    query = client.collection("threat_logs").where(filter=firestore.FieldFilter("user_id", "==", user_id))
    try:
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        async for d in query.stream():
            threats.append(d.to_dict())
    except Exception:
        async for d in client.collection("threat_logs").where(filter=firestore.FieldFilter("user_id", "==", user_id)).stream():
            threats.append(d.to_dict())
        threats.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return threats


async def record_threat_log(threat_data: dict, db: Optional[firestore.AsyncClient] = None) -> dict:
    client = db or get_firestore_client()
    threat_id = threat_data.get("id") or str(uuid.uuid4())
    threat_data["id"] = threat_id
    if "created_at" not in threat_data or not threat_data["created_at"]:
        threat_data["created_at"] = datetime.now(timezone.utc).isoformat()

    await client.collection("threat_logs").document(threat_id).set(threat_data)
    return threat_data


async def count_user_threats(user_id: str, db: Optional[firestore.AsyncClient] = None) -> int:
    client = db or get_firestore_client()
    query = client.collection("threat_logs").where(filter=firestore.FieldFilter("user_id", "==", user_id))
    count = 0
    async for _ in query.stream():
        count += 1
    return count


async def get_user_threat_history(user_id: str, limit: int = 10, db: Optional[firestore.AsyncClient] = None) -> List[str]:
    client = db or get_firestore_client()
    query = (
        client.collection("threat_logs")
        .where(filter=firestore.FieldFilter("user_id", "==", user_id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    messages = []
    try:
        async for d in query.stream():
            msg = d.to_dict().get("original_message")
            if msg:
                messages.append(msg)
    except Exception as e:
        logger.warning(f"Erro ao buscar histórico ordenado no Firestore para {user_id}: {e}")
        # Fallback sem order_by caso falte índice composto
        query_fallback = client.collection("threat_logs").where(filter=firestore.FieldFilter("user_id", "==", user_id))
        async for d in query_fallback.stream():
            msg = d.to_dict().get("original_message")
            if msg:
                messages.append(msg)
        messages = messages[:limit]

    return list(reversed(messages))


async def list_all_threats(db: Optional[firestore.AsyncClient] = None) -> List[dict]:
    client = db or get_firestore_client()
    users_list = await list_users(client)
    user_map = {u["id"]: u for u in users_list}

    threats = []
    try:
        query = client.collection("threat_logs").order_by("created_at", direction=firestore.Query.DESCENDING)
        async for d in query.stream():
            td = d.to_dict()
            u = user_map.get(td.get("user_id"), {})
            td["user_name"] = u.get("name", "Desconhecido")
            td["user_status"] = u.get("status", "ACTIVE")
            threats.append(td)
    except Exception as e:
        logger.warning(f"Erro ao listar ameaças ordenadas no Firestore: {e}")
        async for d in client.collection("threat_logs").stream():
            td = d.to_dict()
            u = user_map.get(td.get("user_id"), {})
            td["user_name"] = u.get("name", "Desconhecido")
            td["user_status"] = u.get("status", "ACTIVE")
            threats.append(td)
        threats.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return threats


async def reset_user_threats(user_id: str, db: Optional[firestore.AsyncClient] = None) -> int:
    client = db or get_firestore_client()
    query = client.collection("threat_logs").where(filter=firestore.FieldFilter("user_id", "==", user_id))
    count = 0
    async for d in query.stream():
        await d.reference.delete()
        count += 1
    await unblock_user(user_id, client)
    logger.info(f"Ocorrências resetadas no Firestore para user={user_id}: {count} removidos")
    return count


async def clear_all_audit_history(db: Optional[firestore.AsyncClient] = None) -> dict:
    client = db or get_firestore_client()
    count = 0
    async for d in client.collection("threat_logs").stream():
        await d.reference.delete()
        count += 1

    # Reativa usuários que estavam suspensos
    async for ud in client.collection("users").stream():
        u = ud.to_dict()
        if u.get("status") == "BLOCKED_SUSPICIOUS":
            await ud.reference.update({"status": "ACTIVE", "updated_at": datetime.now(timezone.utc).isoformat()})

    logger.info(f"Histórico de auditoria Firestore limpo: {count} logs removidos")
    return {"deleted_threats": count}


async def get_audit_metrics(db: Optional[firestore.AsyncClient] = None) -> dict:
    client = db or get_firestore_client()
    users_list = await list_users(client)
    total_users = len(users_list)
    blocked_users = sum(1 for u in users_list if u.get("status") == "BLOCKED_SUSPICIOUS")

    total_threats = 0
    total_cost_usd = 0.0
    total_cost_brl = 0.0
    total_tokens = 0

    async for d in client.collection("threat_logs").stream():
        td = d.to_dict()
        total_threats += 1
        total_cost_usd += float(td.get("cost_usd") or 0.0)
        total_cost_brl += float(td.get("cost_brl") or 0.0)
        total_tokens += int(td.get("total_tokens") or 0)

    return {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "total_threats": total_threats,
        "total_cost_usd": round(total_cost_usd, 6),
        "total_cost_brl": round(total_cost_brl, 4),
        "total_tokens": total_tokens,
    }
