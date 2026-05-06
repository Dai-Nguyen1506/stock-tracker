import React, { useEffect, useState, useCallback } from 'react';

interface SidebarRightProps {
  selectedSymbol: string;
  onSelectSymbol: (sym: string) => void;
}

// ── Mock Ticker Data Function ──────────────────────────────
async function fetchMockTickers(symbols: string[]): Promise<Record<string, { price: number; change: number }>> {
  return new Promise((resolve) => {
    const out: Record<string, { price: number; change: number }> = {};
    symbols.forEach(sym => {
      let basePrice = 1;
      if (sym.includes('BTC')) basePrice = 60000;
      else if (sym.includes('ETH')) basePrice = 3000;
      else if (sym.includes('SOL')) basePrice = 150;
      else if (sym.includes('BNB')) basePrice = 600;

      // Price fluctuates randomly around the base price, and change is a random percentage
      const currentPrice = basePrice + (Math.random() - 0.5) * (basePrice * 0.02);
      const currentChange = (Math.random() - 0.5) * 10;

      out[sym] = {
        price: currentPrice,
        change: currentChange,
      };
    });
    resolve(out);
  });
}

export const SidebarRight: React.FC<SidebarRightProps> = ({ selectedSymbol, onSelectSymbol }) => {
  const [symbols, setSymbols] = useState<{ priority: string[]; remainder: string[] }>({
    priority: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
    remainder: ['ADAUSDT', 'XRPUSDT', 'DOGEUSDT', 'DOTUSDT'],
  });
  const [tickers, setTickers] = useState<Record<string, { price: number; change: number }>>({});

  const [testStartDate, setTestStartDate] = useState(new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0]);
  const [testEndDate, setTestEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [testInterval, setTestInterval] = useState('1m');
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const allSymbols = [...symbols.priority, ...symbols.remainder];


  const refreshTickers = useCallback(async () => {
    const t = await fetchMockTickers(allSymbols);
    setTickers(t);
  }, [allSymbols.join(',')]);

  useEffect(() => {
    refreshTickers();
    const timer = setInterval(refreshTickers, 3000);
    return () => clearInterval(timer);
  }, [refreshTickers]);

  // ── Mock Test Functions ─────────────────────────────────
  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Simulate Cassandra ping time (random between 5ms and 25ms)
      await new Promise(resolve => setTimeout(resolve, 600));
      
      // Randomly decide if the test is successful or fails to simulate real conditions
      setTestResult({ 
        readMs: Math.floor(Math.random() * 20) + 5, // 5ms - 25ms
        rows: Math.floor(Math.random() * 5000) + 1000 
      });
    } finally {
      setTesting(false);
    }
  };

  const handlePgCopy = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Copy data from Cassandra to Postgres (simulate time taken for copying)
      await new Promise(resolve => setTimeout(resolve, 1200));
      setTestResult({ 
        error: "Success (Mock)", 
        readMs: Math.floor(Math.random() * 100) + 50, 
        rows: '-' 
      });
    } finally {
      setTesting(false);
    }
  };

  const handlePgPing = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Postgres query time
      await new Promise(resolve => setTimeout(resolve, 800));
      setTestResult({ 
        readMs: Math.floor(Math.random() * 40) + 10, // 10ms - 50ms
        rows: Math.floor(Math.random() * 5000) + 1000, 
        isPg: true 
      });
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

  // ── RENDER ─────────────────────────────────
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <div style={{ padding: '6px 9px', background: 'rgba(59,130,246,0.08)', borderRadius: '6px', border: '1px solid rgba(59,130,246,0.15)', fontSize: '11px', color: '#93c5fd' }}>
            Symbol: <strong>{selectedSymbol}</strong>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <select value={testInterval} onChange={e => setTestInterval(e.target.value)}
              style={{ width: '100%', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '7px 8px', borderRadius: '6px', outline: 'none', fontSize: '11px', marginBottom: '2px' }}>
              <option value="1m">1 minute</option>
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
              <option value="1h">1 hour</option>
              <option value="1d">1 day</option>
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
            {testing ? '⏳ Copying...' : '🔄 Copy to Postgres'}
          </button>

          {testResult && (
            <div style={{ 
              background: testResult.error && testResult.error !== "Success (Mock)" ? 'rgba(244,63,94,0.07)' : 'rgba(16,185,129,0.07)', 
              border: testResult.error && testResult.error !== "Success (Mock)" ? '1px solid rgba(244,63,94,0.18)' : '1px solid rgba(16,185,129,0.18)', 
              borderRadius: '8px', padding: '9px 11px', marginTop: '6px' 
            }}>
              {testResult.error && testResult.error !== "Success (Mock)" ? (
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
                    <span style={{ color: '#71717a', fontSize: '10px' }}>{testResult.error === "Success (Mock)" ? 'Write time' : 'Read time'}</span>
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