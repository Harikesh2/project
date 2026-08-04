"""One-off: delete stale UserInboxRecord rows from the SocialMedia table.

Rows under PK=USER#... with Sk begins_with "CHAT#" that fail
UserInboxRecord validation were written by the old chat schema and crash
list_conversations. Inbox rows are denormalized projections, so deleting
them is safe — they are rebuilt on the next message send.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boto3.dynamodb.conditions import Attr
from pydantic import ValidationError

from app.database.connection import db_connection
from app.core.config import settings
from app.models.chat import UserInboxRecord


def main():
    table = db_connection.resource.Table(settings.social_media_table)
    last = None
    scanned = deleted = 0
    while True:
        kwargs = {"FilterExpression": Attr("Sk").begins_with("CHAT#")}
        if last:
            kwargs["ExclusiveStartKey"] = last
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            scanned += 1
            try:
                UserInboxRecord.from_dynamo_item(item)
            except ValidationError:
                table.delete_item(Key={"Pk": item["Pk"], "Sk": item["Sk"]})
                deleted += 1
                print(f"deleted {item['Pk']} {item['Sk']}")
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
    print(f"scanned {scanned} inbox rows, deleted {deleted} stale rows")


if __name__ == "__main__":
    main()
