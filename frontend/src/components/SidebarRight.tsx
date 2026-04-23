import React, { useEffect, useState, useCallback, useRef } from 'react';

interface SymbolInfo {
  symbol: string;
  price: number | null;
  change: number | null;
}

interface SidebarRightProps {
  selectedSymbol: string;
  onSelectSymbol: (sym: string) => void;
}

// ── Market data từ Binance REST API ──────────────────────────
async function fetchTickers(symbols: string[]): Promise<Record<string, { price: number; change: number }>> {
  try {
    const res = await fetch('https://api.binance.com/api/v3/ticker/24hr');
    const data: any[] = await res.json();
    const out: Record<string, { price: number; change: number }> = {};
    for (const item of data) {
      if (symbols.includes(item.symbol)) {
        out[item.symbol] = {
          price: parseFloat(item.lastPrice),
          change: parseFloat(item.priceChangePercent),
        };
      }
    }
    return out;
  } catch {
    return {};
  }
}

// ── Stats từ Backend ─────────────────────────────────────────
async function fetchStats() {
  try {
    const res = await fetch('http://localhost:8001/api/v1/market/stats');
    return await res.json();
  } catch {
    return null;
  }
}

export const SidebarRight: React.FC<SidebarRightProps> = ({ selectedSymbol, onSelectSymbol }) => {
  const [symbols, setSymbols] = useState<{ priority: string[]; remainder: string[] }>({
    priority: ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT'],
    remainder: ['ADAUSDT','DOGEUSDT','AVAXUSDT','DOTUSDT','MATICUSDT'],
  });
  const [tickers, setTickers] = useState<Record<string, { price: number; change: number }>>({});
  const [stats, setStats] = useState<any>(null);

  // Test state
  const [testStartDate, setTestStartDate] = useState(new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0]);
  const [testEndDate, setTestEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [testInterval, setTestInterval] = useState('1m');
  const [testResult, setTestResult] = useState<{ writeMs: string; rows?: number } | null>(null);
  const [testing, setTesting] = useState(false);

  const allSymbols = [...symbols.priority, ...symbols.remainder];

  // Load symbols từ Discovery API - KHÔNG CẮT BỚT .slice()
  useEffect(() => {
    fetch('http://localhost:8001/api/v1/market/symbols')
      .then(r => r.json())
      .then(d => {
        if (d.priority?.length) setSymbols({ priority: d.priority, remainder: d.remainder });
      })
      .catch(() => {});
  }, []);

  const refreshTickers = useCallback(async () => {
    // Fetch giá cho toàn bộ symbols có trong danh sách
    const t = await fetchTickers(allSymbols);
    setTickers(t);
  }, [allSymbols.join(',')]);

  useEffect(() => {
    refreshTickers();
    const timer = setInterval(refreshTickers, 5000);
    return () => clearInterval(timer);
  }, [refreshTickers]);

  useEffect(() => {
    const load = () => fetchStats().then(s => setStats(s));
    load();
    const timer = setInterval(load, 6000);
    return () => clearInterval(timer);
  }, []);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`http://localhost:8001/api/v1/market/test/ping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            symbol: selectedSymbol, 
            interval: testInterval, 
            limit: 100,
            start_date: testStartDate,
            end_date: testEndDate
        })
      });
      const data = await res.json();
      setTestResult({ writeMs: data.write_ms, rows: data.rows });
    } catch {
      setTestResult({ writeMs: 'Lỗi' });
    } finally {
      setTesting(false);
    }
  };

  const fmtPrice = (sym: string) => {
    const t = tickers[sym];
    if (!t) return '---';
    return t.price > 1 ? t.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : t.price.toFixed(5);
  };

  const fmtChange = (sym: string) => {
    const t = tickers[sym];
    if (!t) return null;
    return { val: `${t.change >= 0 ? '+' : ''}${t.change.toFixed(2)}%`, up: t.change >= 0 };
  };

  const SymbolRow = ({ sym }: { sym: string }) => {
    const ch = fmtChange(sym);
    const isSelected = selectedSymbol === sym;
    return (
      <div onClick={() => onSelectSymbol(sym)} style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 8px', cursor: 'pointer', borderRadius: '6px',
        background: isSelected ? 'rgba(59,130,246,0.12)' : 'transparent',
        borderLeft: isSelected ? '2px solid #3b82f6' : '2px solid transparent',
        transition: 'all 0.12s', marginBottom: '1px',
      }}>
        <span style={{ fontWeight: '600', fontSize: '12px', color: isSelected ? '#3b82f6' : '#d4d4d8' }}>{sym}</span>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#f8fafc' }}>{fmtPrice(sym)}</div>
          {ch && <div style={{ fontSize: '10px', color: ch.up ? '#10b981' : '#f43f5e' }}>{ch.val}</div>}
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="glass-panel" style={{ flex: 6, display: 'flex', flexDirection: 'column', padding: '14px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ fontWeight: '700', fontSize: '14px', color: '#f8fafc' }}>📋 Market Watch</h3>
          <span style={{ fontSize: '10px', color: '#52525b' }}>5s</span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', paddingRight: '2px' }}>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '10px', color: '#3b82f6', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px', display: 'flex', gap: '5px', alignItems: 'center' }}>
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }} />
              Priority
            </div>
            {symbols.priority.map(sym => <SymbolRow key={sym} sym={sym} />)}
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '10px' }}>
            <div style={{ fontSize: '10px', color: '#71717a', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px', display: 'flex', gap: '5px', alignItems: 'center' }}>
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#52525b', display: 'inline-block' }} />
              Remainder
            </div>
            {symbols.remainder.map(sym => <SymbolRow key={sym} sym={sym} />)}
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ flex: 4, display: 'flex', flexDirection: 'column', padding: '14px', overflow: 'hidden' }}>
        <h3 style={{ fontWeight: '700', fontSize: '14px', color: '#f8fafc', marginBottom: '10px' }}>⚡ Cassandra Test</h3>

        {stats && (
          <div style={{ marginBottom: '10px', padding: '8px', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '11px' }}>
            <div style={{ color: '#52525b', marginBottom: '3px' }}>Ingestion Worker</div>
            {stats.running ? (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>
                  <span style={{ color: '#10b981', fontWeight: '700' }}>{stats.write_speed_per_s}</span>
                  <span style={{ color: '#71717a' }}> tx/s write</span>
                </span>
                <span>
                  <span style={{ color: '#3b82f6', fontWeight: '700' }}>{stats.ingest_speed_per_s}</span>
                  <span style={{ color: '#71717a' }}> msg/s</span>
                </span>
              </div>
            ) : (
              <span style={{ color: '#52525b' }}>binance_ws.py chưa chạy</span>
            )}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <div style={{ padding: '6px 9px', background: 'rgba(59,130,246,0.08)', borderRadius: '6px', border: '1px solid rgba(59,130,246,0.15)', fontSize: '11px', color: '#93c5fd' }}>
            Symbol: <strong>{selectedSymbol}</strong>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <select value={testInterval} onChange={e => setTestInterval(e.target.value)}
              style={{ width: '100%', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '7px 8px', borderRadius: '6px', outline: 'none', fontSize: '11px', marginBottom: '2px' }}>
              <option value="1m">1 phút</option>
              <option value="5m">5 phút</option>
              <option value="15m">15 phút</option>
              <option value="1h">1 giờ</option>
              <option value="1d">1 ngày</option>
            </select>
            
            <div style={{ display: 'flex', gap: '6px' }}>
              <input type="date" value={testStartDate}
                onChange={e => setTestStartDate(e.target.value)}
                style={{ flex: 1, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '6px', borderRadius: '6px', outline: 'none', fontSize: '11px' }}
              />
              <input type="date" value={testEndDate}
                onChange={e => setTestEndDate(e.target.value)}
                style={{ flex: 1, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '6px', borderRadius: '6px', outline: 'none', fontSize: '11px' }}
              />
            </div>
          </div>

          <button onClick={handleTest} disabled={testing} style={{
            background: testing ? 'rgba(59,130,246,0.35)' : '#3b82f6', color: 'white', border: 'none',
            padding: '9px', borderRadius: '6px', fontWeight: '700', cursor: testing ? 'wait' : 'pointer', fontSize: '12px',
          }}>
            {testing ? '⏳ Đang Ping...' : '🚀 Ping Cassandra'}
          </button>

          {testResult && (
            <div style={{ background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.18)', borderRadius: '8px', padding: '9px 11px', marginTop: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span style={{ color: '#71717a', fontSize: '10px' }}>Rows Inserted</span>
                <span style={{ color: '#a1a1aa', fontWeight: '600', fontSize: '12px' }}>{testResult.rows}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#71717a', fontSize: '10px' }}>Write time</span>
                <span style={{ color: '#3b82f6', fontWeight: '700', fontSize: '14px' }}>{testResult.writeMs} <span style={{ fontSize: '10px' }}>ms</span></span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
