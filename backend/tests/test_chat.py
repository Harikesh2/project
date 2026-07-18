import pytest
from app.models.chat import build_conversation_id, ChatEntityKeys, ConversationMetadataRecord


def test_build_conversation_id():
    """Verify that conversation ID generation is stable and deterministic."""
    user_a = "user_abc"
    user_b = "user_xyz"

    id_1 = build_conversation_id(user_a, user_b)
    id_2 = build_conversation_id(user_b, user_a)

    # Deterministic check
    assert id_1 == id_2
    assert id_1.startswith("DM#")
    assert len(id_1) > 3


def test_chat_entity_keys():
    """Test the correctness of key helper formatting."""
    conv_id = "DM#abc123xyz"
    user_id = "user_123"
    created_at = "2026-07-17T12:00:00Z"
    message_id = "msg_456"

    # Metadata keys
    metadata_keys = ChatEntityKeys.conversation_metadata_key(conv_id)
    assert metadata_keys == {
        "Pk": f"CHAT#{conv_id}",
        "Sk": "METADATA"
    }

    # Message keys
    msg_keys = ChatEntityKeys.message_key(conv_id, created_at, message_id)
    assert msg_keys == {
        "Pk": f"CHAT#{conv_id}",
        "Sk": f"MESSAGE#{created_at}#{message_id}"
    }

    # Inbox keys
    inbox_keys = ChatEntityKeys.inbox_key(user_id, created_at, conv_id)
    assert inbox_keys == {
        "Pk": f"USER#{user_id}",
        "Sk": f"CHAT#{created_at}#{conv_id}"
    }


def test_conversation_metadata_record_serialization():
    """Verify that ConversationMetadataRecord serializes correctly for DynamoDB and deserializes back."""
    conv_id = "DM#abc123xyz"
    participants = ["user_1", "user_2"]
    created_at = "2026-07-17T12:00:00Z"
    updated_at = "2026-07-17T12:05:00Z"

    record = ConversationMetadataRecord.create(
        conversation_id=conv_id,
        participant_ids=participants,
        created_at=created_at,
        updated_at=updated_at,
        last_message_preview="Hello there!",
        last_message_at="2026-07-17T12:05:00Z"
    )

    # Check Pydantic access
    assert record.conversation_id == conv_id
    assert record.participant_ids == participants
    assert record.created_at == created_at
    assert record.updated_at == updated_at
    assert record.last_message_preview == "Hello there!"
    assert record.last_message_at == "2026-07-17T12:05:00Z"

    # Serialize to Dynamo item
    dynamo_item = record.to_dynamo_item()
    assert dynamo_item["Pk"] == f"CHAT#{conv_id}"
    assert dynamo_item["Sk"] == "METADATA"
    assert dynamo_item["conversation_id"] == conv_id
    assert dynamo_item["participant_ids"] == participants
    assert dynamo_item["created_at"] == created_at
    assert dynamo_item["updated_at"] == updated_at
    assert dynamo_item["last_message_preview"] == "Hello there!"
    assert dynamo_item["last_message_at"] == "2026-07-17T12:05:00Z"

    # Deserialize from Dynamo item
    deserialized = ConversationMetadataRecord.from_dynamo_item(dynamo_item)
    assert deserialized.conversation_id == conv_id
    assert deserialized.participant_ids == participants
    assert deserialized.created_at == created_at
    assert deserialized.updated_at == updated_at
    assert deserialized.last_message_preview == "Hello there!"
    assert deserialized.last_message_at == "2026-07-17T12:05:00Z"
    assert deserialized.pk == f"CHAT#{conv_id}"
    assert deserialized.sk == "METADATA"
