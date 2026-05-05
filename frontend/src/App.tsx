import { useState } from 'react';
import styles from './App.module.css';
import { useStockWebSocket } from './hooks/useStockWebSocket';
import { WS_BASE_URL } from './config';
import { SidebarLeft } from './components/SidebarLeft';
import { SidebarRight } from './components/SidebarRight';
import { MainChart } from './components/MainChart';
import { DepthChart } from './components/DepthChart';

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [selectedInterval, setSelectedInterval] = useState("1m");
  const { news } = useStockWebSocket(`${WS_BASE_URL}/ws/live`);

  return (
    <div className={styles.appContainer}>
      
      <div className={styles.leftCol}>
        <SidebarLeft news={news} selectedSymbol={selectedSymbol} selectedInterval={selectedInterval} />
      </div>

      <div className={styles.midCol}>
        <div className={`glass-panel ${styles.panel} ${styles.chartPanel}`}>
          <MainChart selectedSymbol={selectedSymbol} selectedInterval={selectedInterval} setSelectedInterval={setSelectedInterval} />
        </div>
        <div className={`glass-panel ${styles.panel} ${styles.depthPanel}`}>
          <DepthChart selectedSymbol={selectedSymbol} />
        </div>
      </div>

      <div className={styles.rightCol}>
        <SidebarRight selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />
      </div>

    </div>
  );
}

export default App;
