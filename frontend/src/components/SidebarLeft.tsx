import React, { useEffect, useRef, useState } from 'react';

interface SidebarLeftProps {
  news: NewsItem[];
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

export const SidebarLeft: React.FC<SidebarLeftProps> = ({ news: liveNews, selectedSymbol, selectedInterval }) => {
  const [sections, setSections] = useState<NewsSection[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  
  const newsCacheRef = useRef<Record<string, { sections: NewsSection[], cursor: {year: number, month: number} | null }>>({});
  const currentCursorRef = useRef<{year: number, month: number} | null>(null);
  
  const scrollRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: 'user' | 'ai', text: string}[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [toastNews, setToastNews] = useState<NewsItem | null>(null);

  // ── Create mock news ─────────────────────────
  const generateMockNews = (symbol: string, year: number, month: number): NewsItem[] => {
    const mockCount = Math.floor(Math.random() * 5) + 1; // Sinh 1 đến 5 tin mỗi tháng
    const items: NewsItem[] = [];
    const baseSymbol = symbol.replace('USDT', '');
    
    const sampleHeadlines = [
      `${baseSymbol} surges following new partnership announcement`,
      `Whale moves 10,000 ${baseSymbol} to unknown wallet`,
      `Technical analysis suggests ${baseSymbol} might break resistance`,
      `${baseSymbol} developer team announces upcoming protocol upgrade`,
      `Market volatility affects ${baseSymbol} trading volume`
    ];

    for (let i = 0; i < mockCount; i++) {
      // Random date within the month
      const date = new Date(year, month - 1, Math.floor(Math.random() * 28) + 1);
      items.push({
        symbol: baseSymbol,
        headline: sampleHeadlines[Math.floor(Math.random() * sampleHeadlines.length)],
        url: "#",
        timestamp: date.getTime()
      });
    }
    
    // Newest news first
    return items.sort((a, b) => b.timestamp - a.timestamp);
  };

  const fetchMonth = async (year?: number, month?: number, isStartup: boolean = false, depth: number = 0) => {
    if (depth > 12) {
        setInitialLoading(false);
        return;
    }

    const isLoadMore = !isStartup;
    if (isLoadMore) setLoadingMore(true);
    else {
        const cached = newsCacheRef.current[selectedSymbol];
        if (cached && !year && !month) {
            setSections(cached.sections);
            currentCursorRef.current = cached.cursor;
            setInitialLoading(false);
            return;
        }
        setInitialLoading(true);
    }

    try {
        // Simulate network delay (300ms)
        await new Promise(resolve => setTimeout(resolve, 300));

        // Determine target year and month for fetching news
        const targetYear = year || new Date().getUTCFullYear();
        const targetMonth = month || (new Date().getUTCMonth() + 1);

        const mockItems = generateMockNews(selectedSymbol, targetYear, targetMonth);
        
        const newSection: NewsSection = {
            year: targetYear,
            month: targetMonth,
            items: mockItems
        };

        setSections(prev => {
            if (prev.some(s => s.year === newSection.year && s.month === newSection.month)) return prev;
            const updated = [...prev, newSection];
            newsCacheRef.current[selectedSymbol] = {
                sections: updated,
                cursor: currentCursorRef.current
            };
            return updated;
        });

        let nextYear = newSection.year;
        let nextMonth = newSection.month - 1;
        if (nextMonth === 0) {
            nextMonth = 12;
            nextYear -= 1;
        }
        currentCursorRef.current = { year: nextYear, month: nextMonth };

        if (isStartup && newSection.items.length === 0) {
            await fetchMonth(nextYear, nextMonth, true, depth + 1);
        }
    } catch (e) {
        console.error("Fetch news error", e);
    } finally {
        setInitialLoading(false);
        setLoadingMore(false);
    }
  };

  useEffect(() => {
    const cached = newsCacheRef.current[selectedSymbol];
    if (cached) {
        setSections(cached.sections);
        currentCursorRef.current = cached.cursor;
        setInitialLoading(false);
    } else {
        setSections([]);
        currentCursorRef.current = null;
        fetchMonth(undefined, undefined, true);
    }
  }, [selectedSymbol]);

  const handleLoadMore = () => {
    if (loadingMore || initialLoading || !currentCursorRef.current) return;
    fetchMonth(currentCursorRef.current.year, currentCursorRef.current.month, false);
  };

  // ── XỬ LÝ TOAST NEWS KHI CÓ TIN REALTIME TỪ PROPS ──
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

  // ── Mock AI Assistant ────────────────────────
  const handleSendMessage = async () => {
    if (!chatInput.trim() || isChatLoading) return;
    const userMsg = chatInput.trim();
    
    const updatedHistory = [...chatHistory, { role: 'user' as const, text: userMsg }];
    setChatHistory(updatedHistory);
    setChatInput('');
    setIsChatLoading(true);
    
    try {
      // Simulate AI thinking delay (1 second)
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // AI response logic (mocked)
      const mockResponses = [
        `Based on the current ${selectedInterval} interval, ${selectedSymbol} is showing strong momentum.`,
        `I noticed that ${selectedSymbol} usually experiences high volatility at this time.`,
        `That's an interesting question about ${selectedSymbol}. The market depth suggests buyers are currently stepping in.`,
        `Looking at the recent mock data, the trend for ${selectedSymbol} appears neutral to bullish.`
      ];
      const randomResponse = mockResponses[Math.floor(Math.random() * mockResponses.length)];
      
      setChatHistory(prev => [...prev, { role: 'ai', text: randomResponse }]);
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

  // ── RENDER ─────────────────────────────────
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
          <a 
            href={toastNews.url} 
            target="_blank" 
            rel="noopener noreferrer"
            style={{
              position: 'absolute', 
              bottom: '20px', 
              left: '10px', 
              right: '10px',
              background: 'rgba(6, 78, 59, 0.95)', 
              backdropFilter: 'blur(8px)',
              color: '#10b981', 
              padding: '12px', 
              borderRadius: '8px',
              fontSize: '11px', 
              borderLeft: '4px solid #10b981', 
              zIndex: 1000,
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 0 15px rgba(16, 185, 129, 0.2)',
              textDecoration: 'none',
              display: 'block',
              cursor: 'pointer',
              animation: 'toastSlideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
              transition: 'transform 0.2s ease, background 0.2s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.background = 'rgba(6, 95, 70, 1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.background = 'rgba(6, 78, 59, 0.95)';
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <strong style={{ color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                ⚡ New Alert: {toastNews.symbol}
              </strong>
              <span style={{ color: '#059669', fontSize: '9px' }}>Just now</span>
            </div>
            <div style={{ color: '#ecfdf5', lineHeight: '1.4', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
              {toastNews.headline}
            </div>
            
            <style>{`
              @keyframes toastSlideUp {
                from { transform: translateY(100%); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
              }
            `}</style>
          </a>
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