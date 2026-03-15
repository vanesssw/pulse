"""
AI Agent routes (DeepSeek integration)
No authentication required
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from openai import OpenAI
import sys
import uuid

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import signals cache
try:
    import signals_cache
except ImportError:
    signals_cache = None
    print("⚠️  signals_cache module not available")

router = APIRouter(prefix="/api/agent", tags=["agent"])

# DeepSeek client (OpenAI-compatible)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

deepseek_client = None

if DEEPSEEK_API_KEY:
    deepseek_client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )

# System prompt for AI agent (English only)
SYSTEM_PROMPT = """You are PULSΞ — an elite AI crypto market intelligence agent. You synthesize market data, whale movements, social sentiment, funding rates, and $CASHTAG activity into actionable intelligence. Sharp, precise, no fluff. Always respond in English only.

ANALYSIS FRAMEWORK:
1. VERDICT: BULLISH / BEARISH / NEUTRAL / CAUTION
2. CONFIDENCE: 0-100%
3. CONTEXT: 2-3 sentences on what's happening now
4. KEY SIGNALS (◆ bullets): price momentum, volume, whales, social/$cashtag velocity, funding/OI, S/R levels
5. RISK: LOW / MEDIUM / HIGH / EXTREME
6. OUTLOOK: 24-72h forecast
7. ACTION: 1 sentence clear recommendation

Rules:
- Always use $CASHTAG format for tickers
- Be data-driven and precise
- No marketing fluff or generic advice
- Focus on actionable intelligence
- Respond in English only

Example format:
**BULLISH** — $BTC
Confidence: 85%

Price broke above $68K resistance with strong volume. Whales accumulated 2,400 BTC in 24h. Social sentiment spike (+340% mentions). Funding rate neutral at 0.01%.

◆ Price momentum: Strong uptrend, RSI 72
◆ Volume: Above 20D MA by 180%
◆ Whale activity: Net inflow to exchanges -$420M
◆ Support: $67.2K (previous resistance)
◆ Resistance: $70K psychological

Risk: MEDIUM (overheated RSI)
Outlook: Likely test $70K within 48h, possible consolidation at $72K

ACTION: Strong buy on dips to $67K. Set stops below $66K."""

# Signal generation prompt
SIGNAL_PROMPT = """You are an elite crypto trading signal generator for PULSΞ. Analyze market data and generate 5-7 ACTIONABLE trading signals with entry/exit strategies.

For each signal, provide:
- action: BUY / SELL / HOLD / CLOSE
- ticker: Symbol only (e.g., BTC, not $BTC)
- confidence: 0-100 (numerical confidence level)
- entry: Entry price point (use current price if immediate)
- target: Take-profit target price
- stop: Stop-loss price
- timeframe: Position timeframe (e.g., "1-3 days", "Immediate", "4-7 days")
- reason: 1-2 sentences with SPECIFIC data (price %, volume change, Fear&Greed, momentum)

Trade Logic:
- BUY: Strong uptrend, high volume, positive sentiment → open long
- SELL: Downtrend, distribution signs, negative sentiment → open short or exit longs
- CLOSE: Take profit or cut losses on existing position
- HOLD: Consolidation, wait for clearer signals

Use REAL numbers from provided data. Calculate entry/target/stop based on:
- Support/resistance levels (±2-5% from current)
- ATH distances
- Volume patterns
- Fear & Greed extremes

Format as JSON array:
[{"action": "BUY", "ticker": "SOL", "confidence": 78, "entry": 142.50, "target": 165.00, "stop": 135.00, "timeframe": "2-4 days", "reason": "Volume surge +240% with RSI at 58. Breaking $140 resistance. F&G at 72 (Greed) suggests momentum. Target previous local high."}]

Return 5-7 signals. Mix actions (BUY/SELL/HOLD). Prioritize high-confidence setups. English only."""


class ChatRequest(BaseModel):
    message: str
    context: str = ""


class ChatResponse(BaseModel):
    reply: str | None
    error: str | None = None


class MissionRequest(BaseModel):
    task: str


class MissionResponse(BaseModel):
    synthesis: str | None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Chat with AI agent (DeepSeek)
    Analyze market data, answer crypto questions
    """
    
    if not request.message:
        raise HTTPException(status_code=400, detail="No message provided")
    
    # Check if API key is configured
    if not deepseek_client:
        return ChatResponse(
            reply=None,
            error="Set DEEPSEEK_API_KEY env var"
        )
    
    try:
        # Combine message with context
        full_message = request.message
        if request.context:
            full_message += f"\n\nMarket Data:\n{request.context}"
        
        # Call DeepSeek API
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_message}
            ],
            max_tokens=1024,
            temperature=0.7
        )
        
        # Extract reply
        reply = response.choices[0].message.content
        
        return ChatResponse(reply=reply, error=None)
    
    except Exception as e:
        return ChatResponse(
            reply=None,
            error=str(e)
        )


@router.post("/mission", response_model=MissionResponse)
async def run_mission(request: MissionRequest):
    """
    Multi-agent mission
    Complex analysis with multiple specialized agents
    """
    
    if not request.task:
        raise HTTPException(status_code=400, detail="No task provided")
    
    # Check if API key is configured
    if not deepseek_client:
        return MissionResponse(synthesis=None)
    
    try:
        # Multi-agent system prompt
        multi_agent_prompt = """You are a multi-agent crypto orchestrator. Analyze as if 4 agents contributed: 
        
1. Market Analyst: Price action, volume, technical indicators
2. Whale Tracker: Large transactions, exchange flows, whale behavior
3. $Cashtag Scanner: Social sentiment, mentions velocity, influencer activity
4. Risk Assessor: Market structure, funding rates, liquidation levels

DATA RULES (STRICT):
- If the user message contains a section like "LIVE MARKET SNAPSHOT", treat it as ground truth.
- Use ONLY the factual numbers/metrics explicitly present in the user's message.
- If a metric is not provided (RSI, funding rate, OI, liquidation levels, whale tx counts, exchange flows, mention velocity, influencer names, etc.), write "Unknown" and do NOT guess.
- Do NOT cite specific third-party sources (e.g., Hyblock, Glassnode) unless they are explicitly provided in the user's message.

OUTPUT:
- Give each agent a section with their analysis, then provide a final SYNTHESIS with clear verdict and action.
- Keep it concise, actionable, and consistent with provided data.
- English only."""
        
        # Call DeepSeek API
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": multi_agent_prompt},
                {"role": "user", "content": request.task}
            ],
            max_tokens=2048,
            temperature=0.8
        )
        
        # Extract synthesis
        synthesis = response.choices[0].message.content
        
        return MissionResponse(synthesis=synthesis)
    
    except Exception as e:
        return MissionResponse(synthesis=None)


class Signal(BaseModel):
    action: str  # BUY / SELL / HOLD / CLOSE
    ticker: str
    confidence: int  # 0-100
    entry: float
    target: float
    stop: float
    timeframe: str
    reason: str


class SignalsRequest(BaseModel):
    market_data: str = ""


class SignalsResponse(BaseModel):
    signals: list[Signal] | None
    error: str | None = None


@router.post("/signals", response_model=SignalsResponse)
async def generate_signals(request: SignalsRequest):
    """
    Generate AI trading signals with entry/exit strategies
    """
    
    # Check if API key is configured
    if not deepseek_client:
        return SignalsResponse(
            signals=None,
            error="Set DEEPSEEK_API_KEY env var"
        )
    
    try:
        import json
        
        # Parse market data if provided
        market_context = "Current crypto market overview:\n\n"
        
        if request.market_data:
            try:
                # Try to parse as JSON array
                coins = json.loads(request.market_data)
                
                # Calculate aggregate metrics
                total_mcap = sum(c.get('market_cap', 0) for c in coins)
                total_volume = sum(c.get('total_volume', 0) for c in coins)
                avg_24h = sum(c.get('price_change_percentage_24h_in_currency', 0) for c in coins) / len(coins)
                
                # Find top movers
                top_gainers = sorted(coins, key=lambda x: x.get('price_change_percentage_24h_in_currency', 0), reverse=True)[:3]
                top_losers = sorted(coins, key=lambda x: x.get('price_change_percentage_24h_in_currency', 0))[:3]
                
                market_context += f"Total Market Cap: ${total_mcap/1e9:.1f}B\n"
                market_context += f"24h Volume: ${total_volume/1e9:.1f}B\n"
                market_context += f"Average 24h Change: {avg_24h:+.2f}%\n\n"
                
                market_context += "Top Gainers (24h):\n"
                for c in top_gainers:
                    market_context += f"- {c.get('symbol', '').upper()}: ${c.get('current_price', 0):.4f} ({c.get('price_change_percentage_24h_in_currency', 0):+.2f}%), Vol: ${c.get('total_volume', 0)/1e9:.2f}B\n"
                
                market_context += "\nTop Losers (24h):\n"
                for c in top_losers:
                    market_context += f"- {c.get('symbol', '').upper()}: ${c.get('current_price', 0):.4f} ({c.get('price_change_percentage_24h_in_currency', 0):+.2f}%), Vol: ${c.get('total_volume', 0)/1e9:.2f}B\n"
                
                # Add detailed coin data
                market_context += "\n\nTop 8 Assets (detailed):\n"
                for c in coins[:8]:
                    sym = c.get('symbol', '').upper()
                    price = c.get('current_price', 0)
                    ch_1h = c.get('price_change_percentage_1h_in_currency', 0)
                    ch_24h = c.get('price_change_percentage_24h_in_currency', 0)
                    ch_7d = c.get('price_change_percentage_7d_in_currency', 0)
                    vol = c.get('total_volume', 0) / 1e9
                    mcap = c.get('market_cap', 0) / 1e9
                    ath_dist = c.get('ath_change_percentage', 0)
                    market_context += f"{sym}: ${price:.4f} | 1h: {ch_1h:+.2f}% | 24h: {ch_24h:+.2f}% | 7d: {ch_7d:+.2f}% | Vol: ${vol:.2f}B | MCap: ${mcap:.1f}B | ATH Δ: {ath_dist:.1f}%\n"
                
            except:
                # Fallback if parsing fails
                market_context += request.market_data[:1000]
        
        # Try to get Fear & Greed Index
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                fng_resp = await client.get('https://api.alternative.me/fng/')
                if fng_resp.status_code == 200:
                    fng_data = fng_resp.json()
                    fng_value = fng_data['data'][0]['value']
                    fng_class = fng_data['data'][0]['value_classification']
                    market_context += f"\nFear & Greed Index: {fng_value}/100 ({fng_class})\n"
        except:
            pass
        
        prompt = f"{market_context}\n\nGenerate 5-7 trading signals with entry/exit strategies based on this data."
        
        # Call DeepSeek API
        response = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SIGNAL_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        # Parse response
        content = response.choices[0].message.content
        
        # Try to extract JSON array from response
        try:
            # Look for JSON array in the response
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                signals_data = json.loads(content[start:end])
                signals = [Signal(**sig) for sig in signals_data]
                
                # Save signals to cache
                if signals_cache and signals:
                    try:
                        generation_id = str(uuid.uuid4())
                        market_hash = signals_cache.generate_market_hash(market_context[:500])
                        signals_dict = [sig.dict() for sig in signals]
                        signals_cache.save_signals(signals_dict, market_hash, generation_id)
                    except Exception as cache_err:
                        print(f"Cache save error: {cache_err}")
                
                return SignalsResponse(signals=signals, error=None)
        except Exception as parse_err:
            print(f"Signal parsing error: {parse_err}")
            print(f"AI Response: {content[:500]}")
        
        # Fallback: return empty if parsing failed
        return SignalsResponse(signals=[], error=None)
    
    except Exception as e:
        return SignalsResponse(
            signals=None,
            error=str(e)
        )


@router.get("/signals/cached")
async def get_cached_signals(hours: int = 24, limit: int = 50):
    """
    Get cached signals from database
    
    Args:
        hours: Get signals from last N hours (default: 24)
        limit: Maximum number of signals to return
    """
    if not signals_cache:
        return {"signals": [], "error": "Cache not available"}
    
    try:
        signals = signals_cache.get_recent_signals(hours=hours, limit=limit)
        return {
            "signals": signals,
            "count": len(signals),
            "hours": hours
        }
    except Exception as e:
        return {
            "signals": [],
            "error": str(e)
        }


@router.get("/signals/latest")
async def get_latest_signals(limit: int = 20):
    """
    Get signals from the most recent generation
    """
    if not signals_cache:
        return {"signals": [], "error": "Cache not available"}
    
    try:
        signals = signals_cache.get_latest_generation_signals(limit=limit)
        return {
            "signals": signals,
            "count": len(signals)
        }
    except Exception as e:
        return {
            "signals": [],
            "error": str(e)
        }


@router.get("/signals/ticker/{ticker}")
async def get_ticker_signals(ticker: str, hours: int = 24):
    """
    Get signals for specific ticker
    """
    if not signals_cache:
        return {"signals": [], "error": "Cache not available"}
    
    try:
        signals = signals_cache.get_signals_by_ticker(ticker, hours=hours)
        return {
            "ticker": ticker.upper(),
            "signals": signals,
            "count": len(signals),
            "hours": hours
        }
    except Exception as e:
        return {
            "signals": [],
            "error": str(e)
        }


@router.delete("/signals/cleanup")
async def cleanup_signals(hours: int = 168):
    """
    Manually trigger cleanup of old signals
    Default: Delete signals older than 7 days (168 hours)
    """
    if not signals_cache:
        return {"deleted": 0, "error": "Cache not available"}
    
    try:
        deleted = signals_cache.cleanup_old_signals(hours=hours)
        return {
            "deleted": deleted,
            "hours": hours,
            "message": f"Deleted {deleted} signals older than {hours} hours"
        }
    except Exception as e:
        return {
            "deleted": 0,
            "error": str(e)
        }


@router.get("/signals/stats")
async def get_signals_stats():
    """
    Get database statistics
    """
    if not signals_cache:
        return {"error": "Cache not available"}
    
    try:
        stats = signals_cache.get_db_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}
