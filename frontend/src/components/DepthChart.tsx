import React, { useEffect, useRef, useState } from 'react';

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

function fmt(n: number, d = 2) {
  return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
}

export const DepthChart: React.FC<DepthChartProps> = ({ selectedSymbol }) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [asks, setAsks] = useState<Level[]>([]);
  const [bids, setBids] = useState<Level[]>([]);
  const [midPrice, setMidPrice] = useState<number | null>(null);
  const [ingestRate, setIngestRate] = useState(0);
  const [globalIngest, setGlobalIngest] = useState(0);
  const [writeSpeed, setWriteSpeed] = useState<number>(0);
  const [peakWrite, setPeakWrite] = useState<number>(0);
  const [time, setTime] = useState<string>('');
  const msgCountRef = useRef(0);
  const lastCountRef = useRef(Date.now());

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
        msgCountRef.current += 1;

        // Đo ingest rate mỗi 1 giây
        const now = Date.now();
        const elapsed = (now - lastCountRef.current) / 1000;
        if (elapsed >= 1.0) {
          const rate = +(msgCountRef.current / elapsed).toFixed(1);
          setIngestRate(rate);
          msgCountRef.current = 0;
          lastCountRef.current = now;
        }

        const newBids = buildLevels(data.bids || [], 'bids', 10);
        const newAsks = buildLevels(data.asks || [], 'asks', 10);
        setBids(newBids);
        setAsks(newAsks);

        const bestBid = newBids[0]?.price;
        const bestAsk = newAsks[0]?.price;
        if (bestBid && bestAsk) setMidPrice((bestBid + bestAsk) / 2);
      } catch { }
    };

    ws.onerror = () => ws.close();
    return () => ws.close();
  }, [selectedSymbol]);

  // Poll write status từ backend stats mỗi 1s cho Metrics Dashboard
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('http://localhost:8001/api/v1/market/stats');
        const json = await res.json();
        setWriteSpeed(json.write_speed_per_s || 0);
        setGlobalIngest(json.ingest_speed_per_s || 0);
        setPeakWrite(json.peak_write_per_s || 0);
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

      <div style={{ padding: '4px 0', display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
          {midPrice
            ? <span style={{ fontSize: '18px', fontWeight: '700', color: '#f8fafc', fontVariantNumeric: 'tabular-nums' }}>{midPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            : <span style={{ color: '#52525b', fontSize: '11px' }}>Connecting...</span>}
      </div>

      {/* System Metrics Dashboard */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', minHeight: 0, paddingRight: '4px' }}>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', flexShrink: 0 }}>
          <div style={{ fontSize: '11px', color: '#a1a1aa', marginBottom: '4px' }}>Symbol Ingest Rate ({selectedSymbol})</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#3b82f6' }}>{ingestRate} <span style={{ fontSize: '11px', fontWeight: 'normal', color: '#52525b' }}>msg/s</span></div>
        </div>

        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: '11px', color: '#a1a1aa', marginBottom: '4px' }}>Global Ingest Rate (All Symbols)</div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#8b5cf6' }}>{globalIngest} <span style={{ fontSize: '11px', fontWeight: 'normal', color: '#52525b' }}>msg/s</span></div>
        </div>

        <div style={{ background: 'rgba(16,185,129,0.05)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.15)', flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{ fontSize: '11px', color: '#10b981' }}>Cassandra Write Speed</span>
            <span style={{ fontSize: '9px', background: 'rgba(16,185,129,0.2)', color: '#10b981', padding: '2px 6px', borderRadius: '10px' }}>Disk I/O</span>
          </div>
          <div style={{ fontSize: '18px', fontWeight: '700', color: '#10b981' }}>{writeSpeed} <span style={{ fontSize: '11px', fontWeight: 'normal', color: '#52525b' }}>tx/s</span></div>
        </div>
      </div>

      {/* Stats bar dưới cùng */}
      <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px dashed rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
        <span style={{ color: '#52525b' }}>{time}</span>
        <span style={{ color: '#71717a' }}>Peak Write: <strong style={{ color: '#f59e0b' }}>{peakWrite}</strong> tx/s</span>
      </div>
    </div>
  );
};
