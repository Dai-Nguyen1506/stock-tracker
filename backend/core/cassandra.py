import acsylla
from core.config import settings

_cluster = None
_session = None

async def get_session() -> acsylla.Session:
    """
    Returns the connected Cassandra session. Creates it if it doesn't exist.
    """
    global _cluster, _session
    if _session is None:
        _cluster = acsylla.create_cluster(
            [settings.CASSANDRA_HOST],
            port=settings.CASSANDRA_PORT,
            connect_timeout=10.0,
            request_timeout=10.0,
        )
        _session = await _cluster.create_session(
            keyspace=settings.CASSANDRA_KEYSPACE
        )
    return _session

async def close_session():
    """
    Closes the Cassandra session and cluster.
    """
    global _cluster, _session
    if _session:
        await _session.close()
        _session = None
    if _cluster:
        _cluster = None