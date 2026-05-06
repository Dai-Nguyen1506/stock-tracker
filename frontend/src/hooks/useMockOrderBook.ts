// This hook generates mock order book data for testing purposes. It creates random bid and ask prices around a given current price, simulating a realistic order book.
const generateMockDepth = (currentPrice: number) => {
  const bids = Array.from({ length: 20 }).map((_, i) => ({
    price: currentPrice - (i * 10) - Math.random() * 5,
    quantity: Math.random() * 2 + 0.1,
  }));
  
  const asks = Array.from({ length: 20 }).map((_, i) => ({
    price: currentPrice + (i * 10) + Math.random() * 5,
    quantity: Math.random() * 2 + 0.1,
  }));

  return { bids, asks };
};