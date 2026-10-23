import pytest
from unittest.mock import AsyncMock, MagicMock
from common.database import firestore_repo


@pytest.mark.asyncio
async def test_firestore_ensure_user():
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    
    mock_db.collection.return_value = mock_col
    mock_col.document.return_value = mock_doc
    
    mock_get = AsyncMock()
    mock_snap = MagicMock()
    mock_snap.exists = False
    mock_get.return_value = mock_snap
    mock_doc.get = mock_get
    mock_doc.set = AsyncMock()

    # Query where filter for CPF
    mock_query = MagicMock()
    mock_query.limit.return_value = mock_query
    async def empty_stream():
        if False:
            yield None
    mock_query.stream = empty_stream
    mock_col.where.return_value = mock_query

    user = await firestore_repo.ensure_user(
        user_id="usr_fs_mock",
        cpf_cnpj="12345678900",
        name="Mock User",
        db=mock_db,
    )

    assert user["id"] == "usr_fs_mock"
    assert user["name"] == "Mock User"
    assert user["status"] == "ACTIVE"
    mock_doc.set.assert_called_once()


@pytest.mark.asyncio
async def test_firestore_record_threat():
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_doc = MagicMock()
    
    mock_db.collection.return_value = mock_col
    mock_col.document.return_value = mock_doc
    mock_doc.set = AsyncMock()

    threat = await firestore_repo.record_threat_log(
        {
            "id": "th_123",
            "user_id": "usr_fs_mock",
            "transaction_id": "tx_mock",
            "original_message": "Vou te pegar",
        },
        db=mock_db,
    )

    assert threat["id"] == "th_123"
    assert threat["original_message"] == "Vou te pegar"
    mock_doc.set.assert_called_once()
