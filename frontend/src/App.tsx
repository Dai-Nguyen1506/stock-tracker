import React, { useState } from 'react';
import { SidebarLeft } from './components/SidebarLeft';
import { MainChart } from './components/MainChart';
import { DepthChart } from './components/DepthChart';
import { SidebarRight } from './components/SidebarRight';
import './index.css';

function App() {
  // 1. State to track the selected trading pair and interval for the chart
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  const [selectedInterval, setSelectedInterval] = useState('1m');

  return (
    <div style={{
      display: 'flex',
      gap: '15px',
      padding: '15px',
      height: '100vh',         
      background: '#09090b',    
      color: 'white',
      boxSizing: 'border-box',
      overflow: 'hidden'
    }}>
      
      {/* ── LEFT COLUMN (News & AI) ── */}
      <div style={{ width: '320px', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <SidebarLeft
          news={[]} 
          selectedSymbol={selectedSymbol}
          selectedInterval={selectedInterval}
        />
      </div>

      {/* ── MAIN COLUMN (Charts) ── */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: '15px', minWidth: 0 }}>
        
        {/* Main Chart */}
        <div style={{ flex: 2, background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <MainChart
            selectedSymbol={selectedSymbol}
            selectedInterval={selectedInterval}
            setSelectedInterval={setSelectedInterval}
          />
        </div>
        
        {/* Depth Chart */}
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <DepthChart
            selectedSymbol={selectedSymbol}
          />
        </div>

      </div>

      {/* ── RIGHT COLUMN (Market & Test) ── */}
      <div style={{ width: '320px', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <SidebarRight
          selectedSymbol={selectedSymbol}
          onSelectSymbol={setSelectedSymbol} // 
        />
      </div>

    </div>
  );
}

export default App;