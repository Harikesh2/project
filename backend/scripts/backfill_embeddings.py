"""Backfill embeddings into Pinecone for all existing posts and users.

Idempotent — safe to rerun. Embedding failures are logged and skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boto3.dynamodb.conditions import Attr

from app.database.connection import db_connection
from app.core.config import settings
from app.services.embedding_service import embedding_service


def backfill_posts(table):
    last = None
    processed = failed = 0
    while True:
        kwargs = {
            "FilterExpression": (
                Attr("Pk").begins_with("POST#") & Attr("Sk").eq("METADATA")
            ),
        }
        if last:
            kwargs["ExclusiveStartKey"] = last
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            post_id = item.get("post_id")
            user_id = item.get("user_id")
            content = item.get("content", "")
            if not post_id or not user_id:
                continue
            user_item = table.get_item(
                Key={"Pk": f"USER#{user_id}", "Sk": "METADATA"}
            ).get("Item", {})
            username = user_item.get("username", "unknown")
            try:
                embedding_service.upsert_post(post_id, user_id, username, content)
                processed += 1
            except Exception as e:
                print(f"  failed post {post_id}: {e}")
                failed += 1
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
    return processed, failed


def backfill_users(table):
    last = None
    processed = failed = 0
    while True:
        kwargs = {
            "FilterExpression": (
                Attr("Pk").begins_with("USER#") & Attr("Sk").eq("METADATA")
            ),
        }
        if last:
            kwargs["ExclusiveStartKey"] = last
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            user_id = item.get("user_id")
            username = item.get("username", "")
            if not user_id:
                continue
            profile_item = table.get_item(
                Key={"Pk": f"USER#{user_id}", "Sk": "PROFILE"}
            ).get("Item", {})
            bio = profile_item.get("bio", "")
            try:
                embedding_service.upsert_user(user_id, username, bio)
                processed += 1
            except Exception as e:
                print(f"  failed user {user_id}: {e}")
                failed += 1
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
    return processed, failed


def main():
    table = db_connection.resource.Table(settings.social_media_table)
    print("Backfilling post embeddings...")
    p, f = backfill_posts(table)
    print(f"Posts: {p} processed, {f} failed")
    print("Backfilling user embeddings...")
    p, f = backfill_users(table)
    print(f"Users: {p} processed, {f} failed")
    print("Done.")


if __name__ == "__main__":
    main()
