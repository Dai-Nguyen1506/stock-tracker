import { useState, useEffect } from 'react';

// Data structure for Kline (Candlestick) data
export interface KlineData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export const useBinanceKlineStream = (symbol: string = 'BTCUSDT') => {
  const [klineData, setKlineData] = useState<KlineData | null>(null);

  useEffect(() => {
    // Set an initial price to generate mock data around it
    let currentPrice = 60000;

    const intervalId = setInterval(() => {
      // Create a new mock Kline data point every second with some random volatility
      const volatility = (Math.random() - 0.5) * 30;
      
      const open = currentPrice;
      const close = open + volatility;
      
      const high = Math.max(open, close) + (Math.random() * 10);
      const low = Math.min(open, close) - (Math.random() * 10);
      
      // 2. Update the current price to be the starting point for the next candle
      currentPrice = close;

      // 3. Package the data
      const mockData: KlineData = {
        time: Date.now(),
        open: Number(open.toFixed(2)),
        high: Number(high.toFixed(2)),
        low: Number(low.toFixed(2)),
        close: Number(close.toFixed(2)),
        volume: Number((Math.random() * 5).toFixed(4)), 
      };

      // 4. Update the state to trigger a re-render of the chart
      setKlineData(mockData);
      
    }, 1000); // 1000ms = 1 second to create a new data point

    // Cleanup function: Clear the interval when the component unmounts to prevent memory leaks
    return () => clearInterval(intervalId);
  }, [symbol]); // Re-initialize if the trading pair (symbol) changes

  return klineData;
};