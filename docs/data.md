# Nguồn dữ liệu
- vnstock: các mã chứng khoán của việt nam
- binance API: 439 mã crypto dữ liệu thời gian thực
- finnhub: api dữ liệu tin tức

# Vnstock
Do vnstock chỉ hỗ trợ được 60 call API cho mã chứng khoán, do đó tôi muốn sử dụng để lấy dữ liệu liên tục từ 1500 mã chứng khoán của Việt Nam để bù cho chứng khoán bị lệch múi giờ của finnhub. Hiện tại tạm thời không sử dụng stock nên không sử dụng

# Binance API
Binance API chỉ hỗ trợ các symbols crypto, tôi sẽ sử dụng websockets của binance API dể đổ dữ liệu trade về, ngoài ra tôi sẽ thêm dữ liệu depth để tăng dữ liệu đổ về. Sau đó sử dụng api được cung cấp để lấy dữ liệu quá khứ về và thông tin tin tức của mã crypto đó

Cụ thể:
- Websockets trade + order book cho toàn bộ mã crypto binance hỗ trợ (878)
- Sử dụng api để lấy dữ liệu quá khứ nến

# Finnhub
Finnhub có hỗ trợ websockets cho các mã chứng khoán US nhưng bị lệch múi giờ. Nhu cầu là từ 9h30 - 12h. Vì vậy finnhub websocket sẽ chỉ lấy US để bù vào mã chứng khoán cho nước ngoài. Sau đó 60 call API của finnhub chỉ để lấy dữ liệu tin tức hỗ trợ cho Binance API ở trên vì tin tức chi tiết hơn

Cụ thể:
- Websocket cho sàn chứng khoán US
- 60 call API được dùng để lấy tin tức
( Có thể dùng để lấy stock )

# Alpaca
Alpaca có hỗ trợ websocket cho một vài symbols để lấy news đồng thời cả api lấy tin tức lịch sử nữa. Do đó sẽ được sử dụng để hỗ trợ cho RAG và chatbot

Cụ thể:
- Websocket cho news cho một vài symbols bên Binance API
- API để lấy dữ liệu quá khứ về