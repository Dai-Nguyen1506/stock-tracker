import React, { useEffect, useRef, useState } from 'react';
import type { NewsWSMessage } from '../hooks/useStockWebSocket';

interface SidebarLeftProps {
  news: NewsWSMessage[];
  selectedSymbol: string;
}

interface NewsItem {
  symbol: string;
  headline: string;
  url: string;
  timestamp: number;
}

const API = 'http://localhost:8001/api/v1/market';

export const SidebarLeft: React.FC<SidebarLeftProps> = ({ news: liveNews, selectedSymbol }) => {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loadingMore, setLoadingMore] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const oldestTsRef = useRef<number>(Date.now());

  // Đổi symbol thì clear và fetch news lịch sử của riêng symbol đó (hoặc base asset)
  useEffect(() => {
    setInitialLoading(true);
    setItems([]);
    oldestTsRef.current = Date.now();
    const baseSymbol = selectedSymbol.replace('USDT', '');
    
    fetch(`${API}/news/history?symbol=${baseSymbol}&limit=12`)
      .then(r => r.json())
      .then(json => {
        const data: NewsItem[] = json.data || [];
        setItems(data);
        if (data.length > 0) oldestTsRef.current = data[data.length - 1].timestamp;
      })
      .catch(() => {})
      .finally(() => setInitialLoading(false));
  }, [selectedSymbol]);

  // Khi có news live mới từ WS → lọc theo symbol đang chọn rồi đẩy lên đầu
  useEffect(() => {
    if (liveNews.length === 0) return;
    const latest = liveNews[0];
    if (!latest) return;
    
    const baseSymbol = selectedSymbol.replace('USDT', '');
    // Chỉ thêm nếu map đúng base symbol
    if (latest.symbol.toUpperCase() !== baseSymbol.toUpperCase()) return;

    const newItem: NewsItem = {
      symbol: latest.symbol,
      headline: latest.headline,
      url: latest.url,
      timestamp: latest.timestamp,
    };
    
    setItems(prev => {
      if (prev.some(x => x.timestamp === newItem.timestamp && x.symbol === newItem.symbol)) return prev;
      return [newItem, ...prev];
    });
  }, [liveNews.length, selectedSymbol]);

  // Scroll xuống đáy → fetch tin lịch sử cũ hơn của symbol đó
  const handleScroll = async (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (!nearBottom || loadingMore) return;

    setLoadingMore(true);
    try {
      const baseSymbol = selectedSymbol.replace('USDT', '');
      const res = await fetch(`${API}/news/history?symbol=${baseSymbol}&limit=12&before_ts=${oldestTsRef.current}`);
      const json = await res.json();
      const older: NewsItem[] = json.data || [];

      if (older.length > 0) {
        setItems(prev => [...prev, ...older]);
        oldestTsRef.current = older[older.length - 1].timestamp;
      }
    } catch {}
    setLoadingMore(false);
  };

  return (
    <>
      {/* News Feed */}
      <div className="glass-panel" style={{ flex: 6, display: 'flex', flexDirection: 'column', padding: '14px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#f8fafc' }}>📰 News Feed</h3>
            {liveNews.length > 0 && (
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981', animation: 'pulse 2s ease-in-out infinite' }} />
            )}
          </div>
          <span style={{ fontSize: '10px', color: '#52525b' }}>{items.length} items · scroll ↓ more</span>
        </div>

        <div
          ref={scrollRef}
          onScroll={handleScroll}
          style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', paddingRight: '4px' }}
        >
          {initialLoading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#52525b', fontSize: '12px' }}>
              Đang tải tin tức...
            </div>
          ) : items.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px', color: '#52525b' }}>
              <div style={{ fontSize: '24px' }}>📡</div>
              <p style={{ fontSize: '12px', textAlign: 'center', lineHeight: 1.5 }}>
                Chưa có tin tức.<br />
                <code style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 5px', borderRadius: '3px', fontSize: '11px' }}>alpaca_ws.py</code>
              </p>
            </div>
          ) : (
            items.map((item, idx) => (
              <a key={`${item.timestamp}-${idx}`} href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
                <div style={{
                  padding: '8px 10px', background: idx === 0 && liveNews.length > 0 ? 'rgba(59,130,246,0.08)' : 'rgba(255,255,255,0.025)',
                  borderRadius: '7px', borderLeft: '2.5px solid #3b82f6', transition: 'background 0.12s',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                    <span style={{ color: '#3b82f6', fontWeight: '700', fontSize: '11px' }}>{item.symbol}</span>
                    <span style={{ color: '#52525b', fontSize: '10px' }}>
                      {new Date(item.timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p style={{ fontSize: '12px', lineHeight: '1.4', color: '#d4d4d8', margin: 0 }}>{item.headline}</p>
                </div>
              </a>
            ))
          )}
          {loadingMore && (
            <div style={{ textAlign: 'center', color: '#52525b', fontSize: '11px', padding: '8px' }}>Loading older news...</div>
          )}
        </div>
      </div>

      {/* AI Chatbot */}
      <div className="glass-panel" style={{ flex: 4, display: 'flex', flexDirection: 'column', padding: '14px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#f8fafc', marginBottom: '10px' }}>🤖 AI Assistant</h3>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#52525b', border: '1px dashed rgba(255,255,255,0.08)', borderRadius: '8px', gap: '6px' }}>
            <span style={{ fontSize: '20px' }}>🚧</span>
            <span style={{ fontSize: '11px', textAlign: 'center', lineHeight: 1.5 }}>RAG Chatbot<br />(Phase 5)</span>
          </div>
          <div style={{ marginTop: '10px', display: 'flex', gap: '6px' }}>
            <input disabled placeholder="Hỏi AI..." style={{ flex: 1, background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.07)', color: 'white', padding: '8px 10px', borderRadius: '6px', outline: 'none', fontSize: '12px', opacity: 0.5 }} />
            <button disabled style={{ padding: '8px 12px', background: 'rgba(59,130,246,0.25)', border: 'none', borderRadius: '6px', color: 'white', cursor: 'not-allowed', fontSize: '12px', opacity: 0.5 }}>Gửi</button>
          </div>
        </div>
      </div>
    </>
  );
};
