-- Tạo bảng
CREATE TABLE candles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open_price DECIMAL(18, 8) NOT NULL,
    high_price DECIMAL(18, 8) NOT NULL,
    low_price DECIMAL(18, 8) NOT NULL,
    close_price DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(22, 8) NOT NULL
);

-- Kiểm tra tốc độ ghi của postgreSQL
BEGIN;

INSERT INTO candles (symbol, timestamp, open_price, high_price, low_price, close_price, volume)
SELECT 
    'BTCUSDT', 
    now() - (i || ' minutes')::interval, -- Mỗi nến cách nhau 1 phút
    (random() * 60000 + 10000)::decimal(18,8), -- Giá Open ngẫu nhiên
    (random() * 60000 + 10500)::decimal(18,8), -- Giá High
    (random() * 60000 + 9500)::decimal(18,8),  -- Giá Low
    (random() * 60000 + 10000)::decimal(18,8), -- Giá Close
    (random() * 100)::decimal(22,8)             -- Volume
FROM generate_series(1, 10000) AS s(i);

COMMIT;


-- Kiểm tra thời gian truy vấn dữ liệu
select * from candles