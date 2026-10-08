from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db_name]
    await _db.users.create_index("email", unique=True)
    await _db.sessions.create_index([("user_id", 1), ("started_at", -1)])
    # Encrypted face embeddings. MongoDB deletes each one once expires_at
    # passes, so an abandoned session never leaves biometric data behind.
    await _db.identity_references.create_index("expires_at", expireAfterSeconds=0)
    await _db.identity_references.create_index("user_id")


async def close_mongo_connection() -> None:
    if _client is not None:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized - connect_to_mongo() must run first")
    return _db
