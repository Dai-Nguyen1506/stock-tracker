-- Tạo keyspace (= database trong Cassandra)
CREATE KEYSPACE IF NOT EXISTS market_data
  WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
  };

USE market_data;

-- Bảng lưu nến OHLCV đa khung thời gian (1m, 5m, 1h...)
CREATE TABLE IF NOT EXISTS klines (
    symbol      TEXT,
    interval    TEXT,
    date_bucket DATE,
    timestamp   TIMESTAMP,
    open        DECIMAL,
    high        DECIMAL,
    low         DECIMAL,
    close       DECIMAL,
    volume      DECIMAL,
    PRIMARY KEY ((symbol, interval, date_bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  }
  AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'};

-- Bảng lưu News từ Alpaca
CREATE TABLE IF NOT EXISTS news (
    symbol      TEXT,
    date_bucket DATE,
    timestamp   TIMESTAMP,
    headline    TEXT,
    summary     TEXT,
    url         TEXT,
    sentiment   TEXT,
    PRIMARY KEY ((symbol, date_bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'DAYS',
    'compaction_window_size': 1
  };

-- Bảng lưu raw Depth để test hiệu năng ghi
CREATE TABLE IF NOT EXISTS depth (
    symbol      TEXT,
    date_bucket DATE,
    timestamp   TIMESTAMP,
    bids        TEXT, -- JSON string or map
    asks        TEXT,
    PRIMARY KEY ((symbol, date_bucket), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
  AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': 1
  }
  AND default_time_to_live = 300  -- 5 phút TTL
  AND gc_grace_seconds = 3600;      -- Giảm thời gian giữ tombstone để dọn dẹp sớm