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

interface NewsSection {
  year: number;
  month: number;
  items: NewsItem[];
}

const API = `${API_BASE_URL}/api/v1/market`;

export const SidebarLeft: React.FC<SidebarLeftProps> = ({ news: liveNews, selectedSymbol, selectedInterval }) => {
  const [sections, setSections] = useState<NewsSection[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  
  const currentCursorRef = useRef<{year: number, month: number} | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: 'user' | 'ai', text: string}[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [toastNews, setToastNews] = useState<NewsItem | null>(null);

  const fetchMonth = async (year?: number, month?: number, isStartup: boolean = false) => {
    const isLoadMore = !isStartup;
    if (isLoadMore) setLoadingMore(true);
    else setInitialLoading(true);

    const baseSymbol = selectedSymbol.replace('USDT', '');
    let url = `${API}/news/history?symbol=${baseSymbol}&limit=20`;
    if (year && month) url += `&year=${year}&month=${month}`;

    try {
        const r = await fetch(url);
        const json = await r.json();
        
        const newSection: NewsSection = {
            year: json.year,
            month: json.month,
            items: json.data || []
        };

        setSections(prev => {
            // Avoid duplicate sections
            if (prev.some(s => s.year === newSection.year && s.month === newSection.month)) return prev;
            return [...prev, newSection];
        });

        // Update cursor for next fetch
        let nextYear = newSection.year;
        let nextMonth = newSection.month - 1;
        if (nextMonth === 0) {
            nextMonth = 12;
            nextYear -= 1;
        }
        currentCursorRef.current = { year: nextYear, month: nextMonth };

        // STARTUP LOGIC: If current month is empty, automatically fetch previous month
        if (isStartup && newSection.items.length === 0) {
            await fetchMonth(nextYear, nextMonth, true);
        }
    } catch (e) {
        console.error("Fetch news error", e);
    } finally {
        setInitialLoading(false);
        setLoadingMore(false);
    }
  };

  useEffect(() => {
    setSections([]);
    currentCursorRef.current = null;
    fetchMonth(undefined, undefined, true);
  }, [selectedSymbol]);

  const handleLoadMore = () => {
    if (loadingMore || initialLoading || !currentCursorRef.current) return;
    fetchMonth(currentCursorRef.current.year, currentCursorRef.current.month, false);
  };

  useEffect(() => {
    if (liveNews.length === 0) return;
    const latest = liveNews[0];
    if (!latest) return;
    
    const newItem: NewsItem = { symbol: latest.symbol, headline: latest.headline, url: latest.url, timestamp: latest.timestamp };
    
    setToastNews(newItem);
    const t = setTimeout(() => setToastNews(null), 5000);
    
    const baseSymbol = selectedSymbol.replace('USDT', '').toUpperCase();
    const newsSymbol = latest.symbol.toUpperCase();
    
    const isMatch = newsSymbol === baseSymbol || newsSymbol.startsWith(baseSymbol) || baseSymbol.startsWith(newsSymbol);
    
    if (isMatch) {
        // Add to the top-most section if it matches the current month
        const now = new Date();
        const curYear = now.getUTCFullYear();
        const curMonth = now.getUTCMonth() + 1;

        setSections(prev => {
            return prev.map(s => {
                if (s.year === curYear && s.month === curMonth) {
                    if (s.items.some(x => x.timestamp === newItem.timestamp)) return s;
                    return { ...s, items: [newItem, ...s.items] };
                }
                return s;
            });
        });
    }
    
    return () => clearTimeout(t);
  }, [liveNews]);

  const getMonthName = (m: number) => {
    const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
    return months[m - 1] || "";
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isChatLoading) return;
    const userMsg = chatInput.trim();
    
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
          history: updatedHistory
        })
      });
      const data = await res.json();
      if (data.response) setChatHistory(prev => [...prev, { role: 'ai', text: data.response }]);
    } catch {
      setChatHistory(prev => [...prev, { role: 'ai', text: "AI Connection Error." }]);
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
      
      <div className="glass-panel" style={{ position: 'relative', height: '55%', display: 'flex', flexDirection: 'column', padding: '12px', overflow: 'hidden', flexShrink: 0 }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', marginBottom: '8px' }}>📰 News Feed</h3>
        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {initialLoading && sections.length === 0 ? <div style={{ textAlign: 'center', fontSize: '11px', color: '#52525b', padding: '20px' }}>Loading news...</div> :
            <>
              {sections.map((section) => (
                <div key={`${section.year}-${section.month}`} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ 
                    fontSize: '10px', 
                    fontWeight: '800', 
                    color: '#3b82f6', 
                    background: 'rgba(59,130,246,0.05)', 
                    padding: '4px 8px', 
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderLeft: '2px solid #3b82f6'
                  }}>
                    <span>{getMonthName(section.month)} {section.year}</span>
                    {section.items.length === 0 && <span style={{ color: '#71717a', fontWeight: '400' }}>No updates</span>}
                  </div>
                  
                  {section.items.length === 0 ? (
                    <div style={{ padding: '10px', textAlign: 'center', fontSize: '11px', color: '#52525b', border: '1px dashed rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                        No news available for this month.
                    </div>
                  ) : (
                    section.items.map((item, idx) => (
                      <a key={`${item.timestamp}-${idx}`} href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none' }}>
                        <div style={{ 
                          padding: '8px 10px', 
                          background: 'rgba(255,255,255,0.02)', 
                          borderRadius: '7px', 
                          border: '1px solid rgba(255,255,255,0.03)',
                          transition: 'transform 0.1s',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.transform = 'translateX(2px)'}
                        onMouseLeave={(e) => e.currentTarget.style.transform = 'translateX(0)'}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                            <span style={{ color: '#60a5fa', fontWeight: '800', fontSize: '10px' }}>{item.symbol}</span>
                            <span style={{ color: '#52525b', fontSize: '9px' }}>{new Date(item.timestamp).toLocaleDateString()} {new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                          </div>
                          <p style={{ fontSize: '11px', color: '#d4d4d8', margin: 0, lineHeight: '1.3', fontWeight: '500' }}>{item.headline}</p>
                        </div>
                      </a>
                    ))
                  )}
                </div>
              ))}
              
              <button 
                onClick={handleLoadMore} 
                disabled={loadingMore}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: 'rgba(59,130,246,0.1)',
                  border: '1px dashed rgba(59,130,246,0.3)',
                  borderRadius: '8px',
                  color: '#93c5fd',
                  fontSize: '11px',
                  fontWeight: '700',
                  cursor: loadingMore ? 'wait' : 'pointer',
                  marginTop: '10px',
                  marginBottom: '10px',
                  transition: 'all 0.2s'
                }}
              >
                {loadingMore ? '⌛ Loading older month...' : '⬇️ Load Previous Month'}
              </button>
            </>
          }
        </div>
        
        {toastNews && (
          <div style={{
            position: 'absolute', bottom: '12px', left: '12px', right: '12px',
            background: 'rgba(16, 185, 129, 0.95)', padding: '10px 12px', borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)', zIndex: 10, animation: 'slide-up 0.3s ease-out'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ color: '#fff', fontWeight: '800', fontSize: '11px' }}>🔔 NEW NEWS ({toastNews.symbol})</span>
              <button onClick={() => setToastNews(null)} style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}>✕</button>
            </div>
            <p style={{ color: '#fff', fontSize: '11px', margin: 0, lineHeight: '1.4' }}>{toastNews.headline}</p>
          </div>
        )}
      </div>

      <div className="glass-panel" style={{ height: '45%', display: 'flex', flexDirection: 'column', padding: '12px', overflow: 'hidden', flexShrink: 0 }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: '#f8fafc', marginBottom: '8px' }}>🤖 AI Assistant</h3>
        
        <div ref={chatScrollRef} style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '8px', minHeight: 0 }}>
          {chatHistory.length === 0 ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#52525b', border: '1px dashed rgba(255,255,255,0.08)', borderRadius: '8px', fontSize: '10px' }}>
              Ask AI about {selectedSymbol}...
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
          {isChatLoading && <div style={{ fontSize: '10px', color: '#71717a' }}>AI is thinking...</div>}
        </div>

        <div style={{ display: 'flex', gap: '5px', marginTop: 'auto' }}>
          <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()} disabled={isChatLoading} placeholder="Type a message..." style={{ flex: 1, background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)', color: 'white', padding: '6px 10px', borderRadius: '5px', fontSize: '11px', outline: 'none' }} />
          <button onClick={handleSendMessage} disabled={isChatLoading || !chatInput.trim()} style={{ padding: '6px 10px', background: '#3b82f6', border: 'none', borderRadius: '5px', color: 'white', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}>Send</button>
        </div>
      </div>
    </div>
  );
};
