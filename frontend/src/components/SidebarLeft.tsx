import React, { useEffect, useRef, useState } from 'react';
import { API_BASE_URL } from '../config';
import type { NewsWSMessage } from '../hooks/useStockWebSocket';

interface SidebarLeftProps {
  news: NewsWSMessage[];
  selectedSymbol: string;
  selectedInterval: string;
}

interface NewsItem {
  symbol: string;
  headline: string;
  url: string;
  timestamp: number;
}

const API = `${API_BASE_URL}/api/v1/market`;

export const SidebarLeft: React.FC<SidebarLeftProps> = ({ news: liveNews, selectedSymbol, selectedInterval }) => {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const oldestTsRef = useRef<number>(Date.now());

  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: 'user' | 'ai', text: string}[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [toastNews, setToastNews] = useState<NewsItem | null>(null);

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

  useEffect(() => {
    if (liveNews.length === 0) return;
    const latest = liveNews[0];
    if (!latest) return;
    
    const newItem: NewsItem = { symbol: latest.symbol, headline: latest.headline, url: latest.url, timestamp: latest.timestamp };
    
    // Hiện popup Global News (tất cả các mã)
    setToastNews(newItem);
    const t = setTimeout(() => setToastNews(null), 5000);
    
    const baseSymbol = selectedSymbol.replace('USDT', '').toUpperCase();
    const newsSymbol = latest.symbol.toUpperCase();
    
    // So khớp để đưa vào danh sách của mã hiện tại
    const isMatch = newsSymbol === baseSymbol || newsSymbol.startsWith(baseSymbol) || baseSymbol.startsWith(newsSymbol);
    
    if (isMatch) {
        setItems(prev => {
          if (prev.some(x => x.timestamp === newItem.timestamp && x.symbol === newItem.symbol)) return prev;
          return [newItem, ...prev];
        });
    }
    
    return () => clearTimeout(t);
  }, [liveNews]);

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isChatLoading) return;
    const userMsg = chatInput.trim();
    
    // Lưu lịch sử chat
    const updatedHistory = [...chatHistory, { role: 'user' as const, text: userMsg }];
    setChatHistory(updatedHistory);
    setChatInput('');
    setIsChatLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: userMsg, 
          symbol: selectedSymbol, 
          interval: selectedInterval,
          history: updatedHistory // Gửi toàn bộ lịch sử
        })
      });
      const data = await res.json();
      if (data.response) setChatHistory(prev => [...prev, { role: 'ai', text: data.response }]);
    } catch {
      setChatHistory(prev => [...prev, { role: 'ai', text: "Lỗi kết nối AI." }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatHistory, isChatLoading]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '12px', overflow: 'hidden' }}>
      
      {/* KHUNG TIN TỨC: ÉP CỨNG TỈ LỆ 55% */}
      <div className="glass-panel" style={{ position: 'relative', height: '55%', display: 'flex', flexDirection: 'column', padding: '12px', overflow: 'hidden', flexShrink: 0 }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', marginBottom: '8px' }}>📰 News Feed</h3>
        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {initialLoading ? <div style={{ textAlign: 'center', fontSize: '11px', color: '#52525b', padding: '20px' }}>Loading news...</div> :
            items.map((item, idx) => {
              return (
                <a key={`${item.timestamp}-${idx}`} href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
                  <div style={{ 
                    padding: '8px 10px', 
                    background: 'rgba(255,255,255,0.02)', 
                    borderRadius: '7px', 
                    borderLeft: '3px solid #3b82f6',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                      <span style={{ color: '#3b82f6', fontWeight: '800', fontSize: '10px' }}>{item.symbol}</span>
                      <span style={{ color: '#52525b', fontSize: '9px' }}>{new Date(item.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <p style={{ fontSize: '11px', color: '#d4d4d8', margin: 0, lineHeight: '1.3' }}>{item.headline}</p>
                  </div>
                </a>
              );
            })
          }
        </div>
        
        {/* Global News Popup (Toast) */}
        {toastNews && (
          <div style={{
            position: 'absolute', bottom: '12px', left: '12px', right: '12px',
            background: 'rgba(16, 185, 129, 0.95)', padding: '10px 12px', borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)', zIndex: 10, animation: 'slide-up 0.3s ease-out'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ color: '#fff', fontWeight: '800', fontSize: '11px' }}>🔔 TIN TỨC MỚI ({toastNews.symbol})</span>
              <button onClick={() => setToastNews(null)} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>✕</button>
            </div>
            <p style={{ color: '#fff', fontSize: '11px', margin: 0, lineHeight: '1.4' }}>{toastNews.headline}</p>
          </div>
        )}
      </div>

      {/* KHUNG AI CHATBOT: ÉP CỨNG TỈ LỆ 45% */}
      <div className="glass-panel" style={{ height: '45%', display: 'flex', flexDirection: 'column', padding: '12px', overflow: 'hidden', flexShrink: 0 }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', marginBottom: '8px' }}>🤖 AI Assistant</h3>
        
        {/* VÙNG CHỨA TIN NHẮN: BẮT BUỘC PHẢI CÓ MIN-HEIGHT: 0 ĐỂ SCROLL */}
        <div ref={chatScrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '8px', minHeight: 0 }}>
          {chatHistory.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#52525b', border: '1px dashed rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '10px' }}>
              Hãy hỏi AI về {selectedSymbol}...
            </div>
          ) : (
            chatHistory.map((msg, idx) => (
              <div key={idx} style={{ 
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', 
                maxWidth: '85%', 
                background: msg.role === 'user' ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.04)', 
                padding: '6px 10px', 
                borderRadius: '8px', 
                fontSize: '11px', 
                color: '#d4d4d8', 
                wordBreak: 'break-word',
                lineHeight: '1.4'
              }}>
                <div dangerouslySetInnerHTML={{ __html: msg.text.replace(/\n/g, '<br/>') }} />
              </div>
            ))
          )}
          {isChatLoading && <div style={{ fontSize: '10px', color: '#71717a' }}>AI đang phản hồi...</div>}
        </div>

        {/* INPUT: CỐ ĐỊNH Ở ĐÁY KHUNG */}
        <div style={{ display: 'flex', gap: '5px', marginTop: 'auto' }}>
          <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()} disabled={isChatLoading} placeholder="Hỏi AI..." style={{ flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '6px 10px', borderRadius: '5px', fontSize: '11px', outline: 'none' }} />
          <button onClick={handleSendMessage} disabled={isChatLoading || !chatInput.trim()} style={{ padding: '6px 10px', background: '#3b82f6', border: 'none', borderRadius: '5px', color: 'white', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}>Gửi</button>
        </div>
      </div>
    </div>
  );
};
