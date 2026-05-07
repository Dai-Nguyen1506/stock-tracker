import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── Credential ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")

# ── Client setup ───────────────────────────────────────────────────────────────
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are a professional crypto trading analyst assistant.
When given a news headline and current price data for one or more assets,
you will:
1. Briefly assess the potential market impact of the news (bullish / bearish / neutral).
2. Identify which assets are most affected.
3. Suggest a short-term trade plan (entry zone, take-profit, stop-loss).
4. Give a confidence level (Low / Medium / High) and explain key risks.
Be concise and actionable. Do NOT give financial advice disclaimers in every reply.
""".strip()


# Single-turn: analyse one news item

def analyse_news(headline: str, summary: str, prices: dict) -> str:

    price_lines = "\n".join(f"  {sym}: ${price:,.2f}" for sym, price in prices.items())
    user_message = f"""
Headline: {headline}
Summary : {summary}

Current prices:
{price_lines}

Please provide your analysis and trade suggestion.
""".strip()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,       
            max_output_tokens=600,
        ),
        contents=user_message,
    )
    return response.text


# Multi-turn chat: interactive session

def chat_session():
    """
    Start a multi-turn chat where Gemini remembers the conversation history.
    Type 'exit' to quit.
    """
    chat = client.chats.create(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=800,
        ),
    )

    print("=" * 60)
    print(" GEMINI TRADING CHAT  (type 'exit' to quit)")
    print("=" * 60)
    print("  You can paste news + price data and ask for a trade plan.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        response = chat.send_message(user_input)
        print(f"\nGemini: {response.text}\n")


# Entry point — demo with a fake news item

if __name__ == "__main__":
    # Demo 1: Single-turn analysis
    print("=" * 60)
    print("SINGLE-TURN NEWS ANALYSIS")
    print("=" * 60)

    sample_headline = "SEC approves spot Ethereum ETF — trading begins next week"
    sample_summary  = (
        "The U.S. Securities and Exchange Commission has granted approval for "
        "the first spot Ethereum ETF, set to begin trading on major exchanges "
        "starting Monday. Analysts expect significant institutional inflows."
    )
    sample_prices = {
        "BTCUSDT" : 62_450.00,
        "ETHUSDT" : 3_120.50,
        "SOLUSDT" : 145.80,
        "BNBUSDT" : 410.25,
    }

    analysis = analyse_news(sample_headline, sample_summary, sample_prices)
    print(f"\nHeadline: {sample_headline}\n")
    print(f"Gemini Analysis:\n{analysis}")

    # Demo 2: Interactive multi-turn chat
    print("\n" + "=" * 60)
    launch = input("Launch interactive chat? (y/n): ").strip().lower()
    if launch == "y":
        chat_session()
