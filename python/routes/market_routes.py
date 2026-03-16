"""
Market data routes (CoinGecko proxy + cache)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import httpx
import os
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/api/market", tags=["market"])

# CoinGecko configuration
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
IDS = "bitcoin,ethereum,solana,dogecoin,ripple,cardano,the-open-network,avalanche-2"

# Simple in-memory cache
_cache = {"market": None, "ts": 0, "price": {}, "top": {}, "deriv": {}}


@router.get("/top/{limit}")
async def get_top_coins(limit: int = 100):
    """
    Get top N coins by market cap
    Cached for 2 minutes
    Example: /api/market/top/100
    """
    cache_key = str(limit)
    
    # Check cache (2 minutes for large datasets)
    if cache_key in _cache["top"]:
        cached_data, cached_ts = _cache["top"][cache_key]
        if datetime.now().timestamp() - cached_ts < 120:
            return cached_data
    
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": min(limit, 250),  # CoinGecko max is 250
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d"
        }
        
        # Add API key if available
        if COINGECKO_API_KEY:
            params["x_cg_demo_api_key"] = COINGECKO_API_KEY
        
        # Disable proxy for CoinGecko (proxy is only for Twitter)
        async with httpx.AsyncClient(timeout=15.0, proxies={}) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Update cache
                _cache["top"][cache_key] = (data, datetime.now().timestamp())
                
                return data
            else:
                # Return cached if available
                if cache_key in _cache["top"]:
                    return _cache["top"][cache_key][0]
                
                raise HTTPException(
                    status_code=502,
                    detail="CoinGecko unavailable"
                )
    
    except Exception as e:
        # Return cached if available
        if cache_key in _cache["top"]:
            return _cache["top"][cache_key][0]
        
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch top coins: {str(e)}"
        )


@router.get("/price")
async def get_simple_price(ids: str = "bitcoin", vs_currencies: str = "usd"):
    """
    Get simple price for coins (matches CoinGecko /simple/price endpoint)
    Example: /api/market/price?ids=bitcoin&vs_currencies=usd
    """
    cache_key = f"{ids}_{vs_currencies}"
    
    # Check cache (30 seconds)
    if cache_key in _cache["price"]:
        cached_data, cached_ts = _cache["price"][cache_key]
        if datetime.now().timestamp() - cached_ts < 30:
            return cached_data
    
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": ids,
            "vs_currencies": vs_currencies
        }
        
        # Add API key if available
        if COINGECKO_API_KEY:
            params["x_cg_demo_api_key"] = COINGECKO_API_KEY
        
        # Disable proxy for CoinGecko (proxy is only for Twitter)
        async with httpx.AsyncClient(timeout=10.0, proxies={}) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Update cache
                _cache["price"][cache_key] = (data, datetime.now().timestamp())
                
                return data
            else:
                raise HTTPException(
                    status_code=502,
                    detail="CoinGecko unavailable"
                )
    
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch price data: {str(e)}"
        )


@router.get("")
async def get_market_data():
    """
    Get market data for all supported coins
    Cached for 30 seconds
    """
    # Check cache
    if _cache["market"] and (datetime.now().timestamp() - _cache["ts"] < 30):
        return _cache["market"]
    
    try:
        url = f"https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": IDS,
            "order": "market_cap_desc",
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d"
        }
        
        # Add API key if available (Demo API uses query param)
        if COINGECKO_API_KEY:
            params["x_cg_demo_api_key"] = COINGECKO_API_KEY
        
        headers = {}
        
        # Disable proxy for CoinGecko (proxy is only for Twitter)
        async with httpx.AsyncClient(timeout=10.0, proxies={}) as client:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Update cache
                _cache["market"] = data
                _cache["ts"] = datetime.now().timestamp()
                
                return data
            else:
                # Return cached if available
                if _cache["market"]:
                    return _cache["market"]
                
                raise HTTPException(
                    status_code=502,
                    detail="CoinGecko unavailable"
                )
    
    except Exception as e:
        # Return cached if available
        if _cache["market"]:
            return _cache["market"]
        
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch market data: {str(e)}"
        )


@router.get("/fng")
async def get_fear_greed_index():
    """
    Get Fear & Greed Index from alternative.me
    """
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        
        # Disable proxy for alternative.me
        async with httpx.AsyncClient(timeout=5.0, proxies={}) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [{}])[0] if data.get("data") else None
            else:
                return None
    
    except Exception:
        return None


@router.get("/cashtags")
async def get_cashtag_metrics(symbols: str = "btc,eth,sol,doge,xrp,ada,ton,avax"):
    """
    Get cashtag metrics (mentions, sentiment, velocity) for given symbols
    Example: /api/market/cashtags?symbols=btc,eth,sol
    """
    import logging
    logger = logging.getLogger(__name__)

    from services.sentiment import SentimentService

    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    logger.info(f"Fetching cashtag metrics for: {symbol_list}")

    # Get metrics from sentiment service
    sentiment_service = SentimentService()

    # Log if Twitter API is configured
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if bearer:
        logger.info(f"Twitter API configured: Bearer token length = {len(bearer)}")
    else:
        logger.error("Twitter API NOT configured - cannot fetch data")

    try:
        result = await sentiment_service.get_cashtag_metrics(symbol_list)
        logger.info(f"Cashtag result status: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Error fetching cashtags: {str(e)}")
        raise
    finally:
        await sentiment_service.close()


@router.get("/derivatives/{symbol}")
async def get_derivatives_snapshot(symbol: str):
    sym = (symbol or "").strip().upper()
    if not sym or len(sym) > 15:
        raise HTTPException(status_code=400, detail="Invalid symbol")

    cache_key = sym
    cached = _cache.get("deriv", {}).get(cache_key)
    if cached:
        cached_data, cached_ts = cached
        if datetime.now().timestamp() - cached_ts < 30:
            return cached_data

    binance_symbol = f"{sym}USDT"

    try:
        async with httpx.AsyncClient(timeout=8.0, proxies={}) as client:
            prem_r = await client.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": binance_symbol},
            )
            oi_r = await client.get(
                "https://fapi.binance.com/fapi/v1/openInterest",
                params={"symbol": binance_symbol},
            )

        prem = prem_r.json() if prem_r.status_code == 200 else None
        oi = oi_r.json() if oi_r.status_code == 200 else None

        mark_price = None
        funding_rate = None
        if isinstance(prem, dict):
            try:
                mp = prem.get("markPrice")
                fr = prem.get("lastFundingRate")
                mark_price = float(mp) if mp is not None else None
                funding_rate = float(fr) if fr is not None else None
            except Exception:
                mark_price = None
                funding_rate = None

        open_interest_base = None
        if isinstance(oi, dict):
            try:
                oiv = oi.get("openInterest")
                open_interest_base = float(oiv) if oiv is not None else None
            except Exception:
                open_interest_base = None

        open_interest_usd = None
        if open_interest_base is not None and mark_price is not None:
            open_interest_usd = open_interest_base * mark_price

        payload = {
            "symbol": sym,
            "binance_symbol": binance_symbol,
            "funding_rate": funding_rate,
            "mark_price": mark_price,
            "open_interest_base": open_interest_base,
            "open_interest_usd": open_interest_usd,
        }

        _cache["deriv"][cache_key] = (payload, datetime.now().timestamp())
        return payload

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch derivatives: {str(e)}")


@router.get("/image-proxy/{path:path}")
async def image_proxy(path: str):
    """
    Proxy for CoinGecko images to avoid CORS/connection issues
    Example: /api/market/image-proxy/coins/images/1/large/bitcoin.png?1696501400
    """
    try:
        url = f"https://coin-images.coingecko.com/{path}"
        
        async with httpx.AsyncClient(timeout=10.0, proxies={}) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type=response.headers.get("content-type", "image/png")
                )
            else:
                raise HTTPException(status_code=404, detail="Image not found")
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load image: {str(e)}"
        )


@router.get("/{coin_id}")
async def get_coin_data(coin_id: str):
    """
    Get detailed data for a specific coin
    """
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false"
        }
        
        # Add API key if available (Demo API uses query param)
        if COINGECKO_API_KEY:
            params["x_cg_demo_api_key"] = COINGECKO_API_KEY
        
        headers = {}
        
        # Disable proxy for CoinGecko (proxy is only for Twitter)
        async with httpx.AsyncClient(timeout=10.0, proxies={}) as client:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Coin not found"
                )
    
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Coin not found: {str(e)}"
        )
