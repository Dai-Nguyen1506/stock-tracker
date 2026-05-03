import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE_URL } from '../config';



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

export const SidebarRight: React.FC<SidebarRightProps> = ({ selectedSymbol, onSelectSymbol }) => {
  const [symbols, setSymbols] = useState<{ priority: string[]; remainder: string[] }>({
    priority: [],
    remainder: [],
  });
  const [tickers, setTickers] = useState<Record<string, { price: number; change: number }>>({});

  // Test state
  const [testStartDate, setTestStartDate] = useState(new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0]);
  const [testEndDate, setTestEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [testInterval, setTestInterval] = useState('1m');
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const allSymbols = [...symbols.priority, ...symbols.remainder];

  // Load symbols từ Discovery API - KHÔNG CẮT BỚT .slice()
  useEffect(() => {
    const fetchSymbols = () => {
      fetch(`${API_BASE_URL}/api/v1/market/symbols`)
        .then(r => r.json())
        .then(d => {
          if (d.priority?.length || d.remainder?.length) {
            setSymbols({ priority: d.priority || [], remainder: d.remainder || [] });
          } else {
            // Retry if empty (backend might still be warming up)
            setTimeout(fetchSymbols, 2000);
          }
        })
        .catch(() => {
            setTimeout(fetchSymbols, 2000);
        });
    };
    fetchSymbols();
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

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/market/test/ping`, {
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
      if (data.error) {
        setTestResult({ error: data.error });
      } else {
        setTestResult({ readMs: data.read_ms, rows: data.rows });
      }
    } catch {
      setTestResult({ error: 'Không thể kết nối tới Backend' });
    } finally {
      setTesting(false);
    }
  };

  const handlePgCopy = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/market/postgres/copy`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: selectedSymbol, interval: testInterval, start_date: testStartDate, end_date: testEndDate })
      });
      const data = await res.json();
      setTestResult({ error: data.status, readMs: data.write_ms, rows: '-' }); // Using error field just to display status text for now
    } catch {
      setTestResult({ error: 'Không thể kết nối tới Backend' });
    } finally {
      setTesting(false);
    }
  };

  const handlePgPing = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/market/postgres/ping`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: selectedSymbol, interval: testInterval, start_date: testStartDate, end_date: testEndDate })
      });
      const data = await res.json();
      if (data.error) {
        setTestResult({ error: data.error });
      } else {
        setTestResult({ readMs: data.read_ms, rows: data.rows, isPg: true });
      }
    } catch {
      setTestResult({ error: 'Không thể kết nối tới Backend' });
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

        {/* Ingestion Worker info removed */}

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

          <div style={{ display: 'flex', gap: '6px' }}>
            <button onClick={handleTest} disabled={testing} style={{
              flex: 1, background: testing ? 'rgba(59,130,246,0.35)' : '#3b82f6', color: 'white', border: 'none',
              padding: '9px', borderRadius: '6px', fontWeight: '700', cursor: testing ? 'wait' : 'pointer', fontSize: '11px',
            }}>
              {testing ? '⏳' : 'Cassandra Ping'}
            </button>
            <button onClick={handlePgPing} disabled={testing} style={{
              flex: 1, background: testing ? 'rgba(244,63,94,0.35)' : '#f43f5e', color: 'white', border: 'none',
              padding: '9px', borderRadius: '6px', fontWeight: '700', cursor: testing ? 'wait' : 'pointer', fontSize: '11px',
            }}>
              {testing ? '⏳' : 'Postgres Ping'}
            </button>
          </div>
          <button onClick={handlePgCopy} disabled={testing} style={{
            background: testing ? 'rgba(16,185,129,0.35)' : '#10b981', color: 'white', border: 'none',
            padding: '9px', borderRadius: '6px', fontWeight: '700', cursor: testing ? 'wait' : 'pointer', fontSize: '11px',
          }}>
            {testing ? '⏳ Đang Copy...' : '🔄 Copy to Postgres'}
          </button>

          {testResult && (
            <div style={{ 
              background: testResult.error ? 'rgba(244,63,94,0.07)' : 'rgba(16,185,129,0.07)', 
              border: testResult.error ? '1px solid rgba(244,63,94,0.18)' : '1px solid rgba(16,185,129,0.18)', 
              borderRadius: '8px', padding: '9px 11px', marginTop: '6px' 
            }}>
              {testResult.error ? (
                <div>
                   <div style={{ color: '#f43f5e', fontSize: '11px', lineHeight: 1.4, marginBottom: testResult.readMs ? '4px' : '0' }}>{testResult.error}</div>
                   {testResult.readMs && <div style={{ color: '#10b981', fontSize: '11px' }}>Time: {testResult.readMs}ms</div>}
                </div>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ color: '#71717a', fontSize: '10px' }}>Rows scanned ({testResult.isPg ? 'PG' : 'Cass'})</span>
                    <span style={{ color: '#a1a1aa', fontWeight: '600', fontSize: '12px' }}>{testResult.rows}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#71717a', fontSize: '10px' }}>Read time</span>
                    <span style={{ color: testResult.isPg ? '#f43f5e' : '#3b82f6', fontWeight: '700', fontSize: '14px' }}>{testResult.readMs} <span style={{ fontSize: '10px' }}>ms</span></span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
};
