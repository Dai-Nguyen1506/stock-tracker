import { useState, useEffect } from 'react';

export interface StockData {
  symbol: string;
  price: number;
  changePercent: number;
}

export const useStockWebSocket = (symbol: string = 'AAPL') => {
  const [stockData, setStockData] = useState<StockData | null>(null);

  useEffect(() => {
    let currentPrice = 150.0; 

    const intervalId = setInterval(() => {
      const change = (Math.random() - 0.5) * 2; 
      currentPrice += change;
      
      const changePercent = (change / currentPrice) * 100;

      setStockData({
        symbol,
        price: Number(currentPrice.toFixed(2)),
        changePercent: Number(changePercent.toFixed(2)),
      });
    }, 2000); 

    return () => clearInterval(intervalId);
  }, [symbol]);

  return stockData;
};