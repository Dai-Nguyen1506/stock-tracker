import { useEffect, useRef, useState } from 'react';

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

    ws.onopen = () => console.log('✅ Connected to WebSockets');

    ws.onmessage = (event) => {
      const raw = event.data;
      // BỎ QUA NGAY NẾU LÀ HEARTBEAT (PONG)
      if (raw === "pong" || typeof raw !== "string") return;

      try {
        // Chỉ parse nếu là một chuỗi JSON hợp lệ
        if (raw.trim().startsWith('{')) {
          const data = JSON.parse(raw);
          if (data.type === 'kline') {
            setLatestKline(data);
          } else if (data.type === 'news') {
            setNews(prev => [data, ...prev].slice(0, 50));
          }
        }
      } catch (e) {
        // Không log lỗi nếu dữ liệu không phải JSON chủ đích
      }
    };

    ws.onclose = () => console.log('❌ Disconnected');

    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 20000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [url]);

  return { news, latestKline };
}
