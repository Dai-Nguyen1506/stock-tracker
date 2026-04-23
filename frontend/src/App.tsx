import React, { useState } from 'react';
import styles from './App.module.css';
import { useStockWebSocket } from './hooks/useStockWebSocket';

// Import Components
import { SidebarLeft } from './components/SidebarLeft';
import { SidebarRight } from './components/SidebarRight';
import { MainChart } from './components/MainChart';
import { DepthChart } from './components/DepthChart';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const { news } = useStockWebSocket("ws://127.0.0.1:8001/ws/live");

  return (
    <div className={styles.appContainer}>
      
      {/* CỘT TRÁI: News & Bot */}
      <div className={styles.leftCol}>
        <SidebarLeft news={news} selectedSymbol={selectedSymbol} />
      </div>

      {/* CỘT GIỮA: Chart & Depth */}
      <div className={styles.midCol}>
        <div className={`glass-panel ${styles.panel} ${styles.chartPanel}`}>
          <MainChart selectedSymbol={selectedSymbol} />
        </div>
        <div className={`glass-panel ${styles.panel} ${styles.depthPanel}`}>
          <DepthChart selectedSymbol={selectedSymbol} />
        </div>
      </div>

      {/* CỘT PHẢI: Market List & Test DB */}
      <div className={styles.rightCol}>
        <SidebarRight selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />
      </div>

    </div>
  );
}

export default App;

