import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import type { ISeriesApi, IChartApi } from 'lightweight-charts';
import { useBinanceKlineStream } from '../hooks/useBinanceKlineStream';

const INTERVALS = [
  { label: '1m',  value: '1m'  },
  { label: '5m',  value: '5m'  },
  { label: '15m', value: '15m' },
  { label: '1h',  value: '1h'  },
  { label: '4h',  value: '4h'  },
  { label: '1D',  value: '1d'  },
];

const LIMIT_MAP: Record<string, number> = {
  '1m': 500, '5m': 500, '15m': 500, '1h': 365, '4h': 365, '1d': 365,
};

interface MainChartProps {
  selectedSymbol: string;
}

export const MainChart: React.FC<MainChartProps> = ({ selectedSymbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const [selectedInterval, setSelectedInterval] = useState('1m');
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<{ close: string; change: string; vol: string; dir: 'up'|'down'|'flat' } | null>(null);
  // Track oldest timestamp for scroll-left pagination
  const oldestTsRef = useRef<number>(0);
  const loadingMoreRef = useRef(false);

  // ── Init Chart once ──────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current || chartRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#a1a1aa',
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.035)' },
        horzLines: { color: 'rgba(255,255,255,0.035)' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(59,130,246,0.6)', width: 1, style: 1 },
        horzLine: { color: 'rgba(59,130,246,0.6)', width: 1, style: 1 },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981', downColor: '#f43f5e',
      borderUpColor: '#10b981', borderDownColor: '#f43f5e',
      wickUpColor: '#10b981', wickDownColor: '#f43f5e',
    });

    volRef.current = chart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current)
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };
    window.addEventListener('resize', handleResize);

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const currentDataRef = useRef<{candles: any[], volumes: any[]}>({ candles: [], volumes: [] });

  // ── Load history bars ─────────────────────────────────
  const loadHistory = useCallback(async (sym: string, iv: string, limit: number, prepend = false) => {
    const candle = candleRef.current;
    const vol   = volRef.current;
    const chart = chartRef.current;
    if (!candle || !vol || !chart) return;

    setIsLoading(true);
    try {
      let url = `http://localhost:8001/api/v1/market/history?symbol=${sym}&interval=${iv}&limit=${limit}`;
      if (prepend && oldestTsRef.current > 0) {
        url += `&before_ts=${oldestTsRef.current}`;
      }

      const res = await fetch(url);
      const json = await res.json();
      if (!json.data || !Array.isArray(json.data) || json.data.length === 0) {
          loadingMoreRef.current = false;
          return;
      }

      const sorted = [...json.data].sort((a: any, b: any) => a.timestamp - b.timestamp);

      const newCandles = sorted.map((k: any) => ({
        time: Math.floor(k.timestamp / 1000) as any,
        open: k.open, high: k.high, low: k.low, close: k.close,
      }));
      const newVolumes = sorted.map((k: any) => ({
        time: Math.floor(k.timestamp / 1000) as any,
        value: k.volume,
        color: k.close >= k.open ? 'rgba(16,185,129,0.4)' : 'rgba(244,63,94,0.4)',
      }));

      if (prepend) {
        currentDataRef.current.candles = [...newCandles, ...currentDataRef.current.candles];
        currentDataRef.current.volumes = [...newVolumes, ...currentDataRef.current.volumes];
      } else {
        currentDataRef.current.candles = newCandles;
        currentDataRef.current.volumes = newVolumes;
      }

      candle.setData(currentDataRef.current.candles);
      vol.setData(currentDataRef.current.volumes);
      
      if (!prepend) {
          chart.timeScale().fitContent();
      }
      
      if (sorted.length > 0) {
          oldestTsRef.current = sorted[0].timestamp;
      }
      
      loadingMoreRef.current = false;

      // Stats
      if (currentDataRef.current.candles.length >= 2) {
        const last = currentDataRef.current.candles[currentDataRef.current.candles.length - 1];
        const prev = currentDataRef.current.candles[currentDataRef.current.candles.length - 2];
        const pct = ((last.close - prev.close) / prev.close) * 100;
        setStats({
          close: last.close.toLocaleString(undefined, { maximumFractionDigits: 2 }),
          change: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`,
          vol: last.volume?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || '0',
          dir: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat',
        });
      }
    } catch (err) {
      console.error('Chart load error:', err);
      loadingMoreRef.current = false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Reload when symbol or interval changes
  useEffect(() => {
    oldestTsRef.current = 0;
    loadHistory(selectedSymbol, selectedInterval, LIMIT_MAP[selectedInterval] || 300);
  }, [selectedSymbol, selectedInterval, loadHistory]);

  // Scroll-left to load more (pagination)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const handler = (range: any) => {
      if (!range) return;
      if (range.from <= 5 && !loadingMoreRef.current && oldestTsRef.current > 0) {
        loadingMoreRef.current = true;
        loadHistory(selectedSymbol, selectedInterval, 300, true);
      }
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
    return () => chart.timeScale().unsubscribeVisibleLogicalRangeChange(handler);
  }, [selectedSymbol, selectedInterval, loadHistory]);

  // ── Real-time update via direct Binance Kline WS ──────
  useBinanceKlineStream(selectedSymbol, selectedInterval, (kline) => {
    const candle = candleRef.current;
    const vol = volRef.current;
    if (!candle || !vol) return;
    try {
      candle.update({
        time: kline.time as any,
        open: kline.open, high: kline.high, low: kline.low, close: kline.close,
      });
      vol.update({
        time: kline.time as any,
        value: kline.volume,
        color: kline.close >= kline.open ? 'rgba(16,185,129,0.4)' : 'rgba(244,63,94,0.4)',
      });
      // Live stats
      setStats(prev => prev ? {
        ...prev,
        close: kline.close.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        vol: kline.volume.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      } : null);
    } catch { }
  });

  const changeColor = stats?.dir === 'up' ? '#10b981' : stats?.dir === 'down' ? '#f43f5e' : '#a1a1aa';

  // ── Render ────────────────────────────────────────────
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '14px 16px 10px' }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px', gap: '8px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h3 style={{ fontSize: '17px', fontWeight: '700', color: '#f8fafc' }}>{selectedSymbol}</h3>
            {isLoading && <span style={{ fontSize: '11px', color: '#52525b' }}>Loading...</span>}
          </div>
          {stats && (
            <div style={{ display: 'flex', gap: '10px', alignItems: 'baseline', marginTop: '2px' }}>
              <span style={{ fontSize: '20px', fontWeight: '700', color: '#f8fafc' }}>{stats.close}</span>
              <span style={{ fontSize: '13px', fontWeight: '600', color: changeColor }}>{stats.change}</span>
              <span style={{ fontSize: '11px', color: '#71717a' }}>Vol {stats.vol}</span>
            </div>
          )}
        </div>

        {/* Interval buttons */}
        <div style={{ display: 'flex', gap: '3px', background: 'rgba(0,0,0,0.35)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.07)' }}>
          {INTERVALS.map(iv => (
            <button key={iv.value} onClick={() => setSelectedInterval(iv.value)} style={{
              padding: '5px 10px', border: 'none', borderRadius: '5px', fontSize: '12px', fontWeight: '600',
              cursor: 'pointer', transition: 'all 0.12s',
              background: selectedInterval === iv.value ? '#3b82f6' : 'transparent',
              color: selectedInterval === iv.value ? '#fff' : '#71717a',
            }}>
              {iv.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart fills remaining */}
      <div ref={chartContainerRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  );
};
