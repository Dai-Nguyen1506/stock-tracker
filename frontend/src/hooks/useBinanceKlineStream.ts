import { useEffect, useRef } from 'react';

export type BinanceKline = {
  time: number;   // seconds (for lightweight-charts)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Callback = (k: BinanceKline) => void;

/**
 * Connects directly to the Binance Kline WebSocket.
 * Provides real-time updates every second for the chart.
 */
export function useBinanceKlineStream(symbol: string, interval: string, onKline: Callback) {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!symbol || !interval) return;

    const binanceInterval = interval; // '1m' , '5m', '15m', '1h', '4h', '1d'
    const url = `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_${binanceInterval}`;

    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        const k = data.k;
        if (!k) return;

        onKline({
          time: Math.floor(k.t / 1000),    // epoch seconds
          open: parseFloat(k.o),
          high: parseFloat(k.h),
          low: parseFloat(k.l),
          close: parseFloat(k.c),
          volume: parseFloat(k.v),
        });
      } catch { }
    };

    ws.onerror = () => ws.close();

    return () => {
      ws.close();
    };
  }, [symbol, interval]);
}
