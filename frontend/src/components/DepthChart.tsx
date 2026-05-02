import React, { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '../config';

interface DepthChartProps {
  selectedSymbol: string;
}

interface Level {
  price: number;
  amount: number;
  total: number;
  pct: number;
}

function buildLevels(raw: [string, string][], side: 'bids' | 'asks', n = 10): Level[] {
  const sorted = raw
    .map(([p, q]) => ({ price: parseFloat(p), amount: parseFloat(q) }))
    .filter(x => x.amount > 0)
    .sort((a, b) => side === 'bids' ? b.price - a.price : a.price - b.price)
    .slice(0, n);

  let acc = 0;
  const withTotal = sorted.map(x => {
    acc += x.amount;
    return { ...x, total: acc };
  });
  const max = withTotal[withTotal.length - 1]?.total || 1;
  return withTotal.map(x => ({ ...x, pct: (x.total / max) * 100 }));
}



export const DepthChart: React.FC<DepthChartProps> = ({ selectedSymbol }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [asks, setAsks] = useState<Level[]>([]);
  const [bids, setBids] = useState<Level[]>([]);
  
  const [tradeSpeed, setTradeSpeed] = useState<string | number>(0);
  const [depthSpeed, setDepthSpeed] = useState<number>(0);
  const [totalSpeed, setTotalSpeed] = useState<number>(0);
  const [latency, setLatency] = useState<string | number>(0);
  const [pgLatency, setPgLatency] = useState<string | number>(0);
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('vi-VN'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Binance depth WebSocket
  useEffect(() => {
    wsRef.current?.close();

    const url = `wss://stream.binance.com:9443/ws/${selectedSymbol.toLowerCase()}@depth20@100ms`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        const newBids = buildLevels(data.bids || [], 'bids', 10);
        const newAsks = buildLevels(data.asks || [], 'asks', 10);
        setBids(newBids);
        setAsks(newAsks);
        
        // Phát event giá midPrice cho App nhận (tùy chọn)
        const bestBid = newBids[0]?.price;
        const bestAsk = newAsks[0]?.price;
        if (bestBid && bestAsk) {
           const ev = new CustomEvent('midPriceUpdate', { detail: (bestBid + bestAsk) / 2 });
           window.dispatchEvent(ev);
        }
      } catch { }
    };

    ws.onerror = () => ws.close();
    return () => ws.close();
  }, [selectedSymbol]);

  // Poll write status từ backend stats mỗi 1s cho Metrics Dashboard
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/market/stats`);
        const json = await res.json();
        setTradeSpeed(json.trade_speed || 0);
        setDepthSpeed(json.depth_speed || 0);
        setTotalSpeed(json.total_speed || 0);
        setLatency(json.cassandra_latency_ms || 0);
        setPgLatency(json.postgres_latency_ms || 0);
      } catch { }
    };
    poll();
    const t = setInterval(poll, 1000);
    return () => clearInterval(t);
  }, []);

  const totalBid = bids.reduce((s, x) => s + x.amount, 0);
  const totalAsk = asks.reduce((s, x) => s + x.amount, 0);
  const bidPct = totalBid + totalAsk > 0 ? Math.round((totalBid / (totalBid + totalAsk)) * 100) : 50;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '10px 14px 8px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc' }}>
          ⚔️ Orderbook <span style={{ color: '#52525b', fontWeight: '400', fontSize: '11px' }}>· {selectedSymbol}</span>
        </h3>
      </div>

      {/* Ratio bar — Giữ nguyên nhu cầu người dùng */}
      <div style={{ height: '8px', minHeight: '8px', borderRadius: '4px', overflow: 'hidden', display: 'flex', marginBottom: '4px', boxShadow: '0 0 6px rgba(0,0,0,0.4)', marginTop: '8px', flexShrink: 0 }}>
        <div style={{ width: `${bidPct}%`, height: '100%', background: 'linear-gradient(90deg, #059669, #10b981)', transition: 'width 0.4s ease' }} />
        <div style={{ flex: 1, height: '100%', background: 'linear-gradient(90deg, #f43f5e, #be123c)', transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', marginBottom: '16px' }}>
        <span style={{ color: '#10b981', fontWeight: '700' }}>Bid {bidPct}%</span>
        <span style={{ color: '#f43f5e', fontWeight: '700' }}>Ask {100 - bidPct}%</span>
      </div>

      {/* System Metrics Dashboard */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', overflowY: 'auto', minHeight: 0, paddingRight: '4px' }}>
        
        {/* Ô 1: Trade data */}
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', flexShrink: 0 }}>
          <div style={{ fontSize: '10px', color: '#a1a1aa', marginBottom: '4px' }}>Candles Created</div>
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#3b82f6' }}>{tradeSpeed} <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#52525b' }}>/ 1 min</span></div>
        </div>

        {/* Ô 2: Order book data */}
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', flexShrink: 0 }}>
          <div style={{ fontSize: '10px', color: '#a1a1aa', marginBottom: '4px' }}>Depth Messages</div>
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#8b5cf6' }}>{depthSpeed} <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#52525b' }}>/ 1 min</span></div>
        </div>

        {/* Ô 3: Total data */}
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', flexShrink: 0 }}>
          <div style={{ fontSize: '10px', color: '#a1a1aa', marginBottom: '4px' }}>Total Records</div>
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#f59e0b' }}>{totalSpeed} <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#52525b' }}>/ 1 min</span></div>
        </div>

        {/* Ô 4: Cassandra Latency */}
        <div style={{ background: 'rgba(16,185,129,0.05)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.15)', flexShrink: 0 }}>
          <div style={{ fontSize: '10px', color: '#10b981', marginBottom: '4px' }}>Cassandra Write</div>
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#10b981' }}>{latency} <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#52525b' }}>ms</span></div>
        </div>

        {/* Ô 5: Postgres Latency */}
        <div style={{ background: 'rgba(244,63,94,0.05)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(244,63,94,0.15)', flexShrink: 0 }}>
          <div style={{ fontSize: '10px', color: '#f43f5e', marginBottom: '4px' }}>Postgres Write</div>
          <div style={{ fontSize: '16px', fontWeight: '700', color: '#f43f5e' }}>{pgLatency} <span style={{ fontSize: '10px', fontWeight: 'normal', color: '#52525b' }}>ms</span></div>
        </div>
      </div>

      {/* Stats bar dưới cùng */}
      <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px dashed rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'center', fontSize: '11px' }}>
        <span style={{ color: '#52525b' }}>{time}</span>
      </div>
    </div>
  );
};
