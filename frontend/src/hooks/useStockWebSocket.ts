import { useEffect, useRef, useState } from 'react';

// Cấu trúc dữ liệu WS trả về từ kênh Pub/Sub của Backend
// Kline Data: {"type": "kline", "symbol": "BTCUSDT", "interval": "1m", "timestamp": 12345678, "close": "65000.12"}
// News Data: {"type": "news", "symbol": "BTC", "headline": "...", "url": "...", "timestamp": ...}

export type KlineWSMessage = {
  type: 'kline';
  symbol: string;
  interval: string;
  timestamp: number;
  close: string;
};

export type NewsWSMessage = {
  type: 'news';
  symbol: string;
  headline: string;
  url: string;
  timestamp: number;
};

export function useStockWebSocket(url: string) {
  const [news, setNews] = useState<NewsWSMessage[]>([]);
  const [latestKline, setLatestKline] = useState<KlineWSMessage | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ Connected to WebSockets Data Stream');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'kline') {
          setLatestKline(data);
        } else if (data.type === 'news') {
          setNews(prev => [data, ...prev].slice(0, 50)); // Giữ 50 tin mới nhất để nhẹ RAM
        }
      } catch (err) {
        console.error("Lỗi parse WS Message", err);
      }
    };

    ws.onclose = () => {
      console.log('❌ Disconnected from WebSockets');
      // Co the them Logic auto-reconnect o day
    };

    // Ping/Pong để giữ kết nối không bị timeout
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 20000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [url]);

  return { news, latestKline };
}
