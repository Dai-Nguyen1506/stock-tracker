-- Tạo keyspace (= database trong Cassandra)
CREATE KEYSPACE IF NOT EXISTS market_data
  WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
  };

USE market_data;

-- Bảng lưu nến OHLCV chứng khoán VN
CREATE TABLE IF NOT EXISTS vn_ohlcv (
    symbol      TEXT,
    date_bucket DATE,
    timestamp   TIMESTAMP,
    open        DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    close       DECIMAL,
    volume      BIGINT,
    PRIMARY KEY ((symbol, date_bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 7
  };

-- Bảng lưu nến OHLCV crypto
CREATE TABLE IF NOT EXISTS crypto_ohlcv (
    symbol      TEXT,
    interval    TEXT,
    date_bucket DATE,
    open_time   TIMESTAMP,
    open        DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    close       DECIMAL,
    volume      DECIMAL,
    PRIMARY KEY ((symbol, interval, date_bucket), open_time)
) WITH CLUSTERING ORDER BY (open_time DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  };