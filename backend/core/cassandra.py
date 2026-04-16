import acsylla
from core.config import settings

_cluster = None
_session = None

async def get_session() -> acsylla.Session:
    """
    Trả về session đã kết nối.
    Dùng pattern singleton — chỉ tạo 1 lần, tái dùng cho mọi request.
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
    global _cluster, _session
    if _session:
        await _session.close()
        _session = None
    if _cluster:
        _cluster = None