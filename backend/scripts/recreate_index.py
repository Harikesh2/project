"""Recreate the social-posts index at 1024 dimensions.

Run once after Phase 6.1:
    cd backend
    python scripts/recreate_index.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings

pc = Pinecone(api_key=settings.pinecone_index and settings.pinecone_api_key)
name = settings.pinecone_index

# Delete old index if it exists
existing = [i.name for i in pc.list_indexes()]
if name in existing:
    print(f"Deleting old index '{name}'...")
    pc.delete_index(name)

print(f"Creating new 1024-dim index '{name}'...")
pc.create_index(
    name=name,
    dimension=1024,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)

while not pc.describe_index(name).status["ready"]:
    time.sleep(1)

desc = pc.describe_index(name)
print(f"Ready — dimension={desc.dimension}, metric={desc.metric}")
