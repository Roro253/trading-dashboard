"""
Narrative Regime Tilt (NRT) Agent - Phase 1: Price-Only Regimes
Implementation of hedge-fund grade regime detection with factor tilting.
"""

from __future__ import annotations

import asyncio
import math
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import structlog
from sklearn.preprocessing import StandardScaler
import cvxpy as cp

from app.core.config import get_settings
from app.services.agents.base import AgentOutput, Decision
from app.services.news_service import NewsService, MarketNarrative

logger = structlog.get_logger(__name__)

# ETF Universe for NRT Strategy
NRT_ETFS = {
    # Core Equity Factors
    'MTUM': 'Momentum',
    'VLUE': 'Value', 
    'QUAL': 'Quality',
    'USMV': 'Low Volatility',
    # Duration (critical for regime hedging)
    'TLT': 'Long Duration',
    'IEF': 'Medium Duration',
    # Macro Diversifiers 
    'SPY': 'Equity Beta',
    'VIX': 'Volatility Index',
    'DXY': 'US Dollar'
}

# Static Policy Matrix (Phase 1)
# Regime -> Factor mapping (risk units before optimizer)
REGIME_POLICY_MATRIX = {
    'growth_on': {
        'MTUM': 0.4, 'VLUE': -0.1, 'QUAL': -0.1, 'USMV': 0.0,
        'TLT': -0.3, 'IEF': -0.2, 'SPY': 0.3
    },
    'tightening': {
        'MTUM': -0.2, 'VLUE': 0.1, 'QUAL': 0.3, 'USMV': 0.2,
        'TLT': 0.3, 'IEF': 0.2, 'SPY': -0.1
    },
    'inflation_shock': {
        'MTUM': -0.2, 'VLUE': 0.3, 'QUAL': 0.0, 'USMV': 0.1,
        'TLT': -0.4, 'IEF': -0.3, 'SPY': -0.2
    },
    'liquidity_crunch': {
        'MTUM': -0.3, 'VLUE': 0.1, 'QUAL': 0.5, 'USMV': 0.5,
        'TLT': 0.4, 'IEF': 0.3, 'SPY': -0.4
    }
}

@dataclass
class RegimeState:
    name: str
    probability: float
    confidence: float
    duration_days: int
    
@dataclass
class NRTSignal:
    regime_probs: Dict[str, float]
    dominant_regime: RegimeState
    factor_tilts: Dict[str, float]
    target_weights: Dict[str, float]
    confidence: float
    risk_budget_used: float


class NRTAgent:
    """Narrative Regime Tilt Agent - Phase 2: News + Price regime detection"""
    
    key = "nrt"
    resolution = "1d"
    
    def __init__(self, settings=None, news_service=None, lookback_days: int = 1800) -> None:  # ~7 years
        self.agent_id = "nrt"
        self.lookback_days = lookback_days
        self.settings = settings or get_settings()
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.regime_model = None
        self.regime_probs_cache: Optional[pd.DataFrame] = None
        self.last_update: Optional[datetime] = None
        self.news_service = news_service or NewsService()
        self.narrative_cache: Optional[MarketNarrative] = None
        
        # Risk parameters
        self.max_position = 0.25  # 25% per sleeve
        self.max_gross = 1.2      # 120% gross exposure
        self.target_te = 0.02     # 2% daily tracking error
        self.max_turnover = 0.15  # 15% daily turnover
        
    async def run(self, market: Dict[str, Any]) -> AgentOutput:
        """Main entry point - returns NRT trading decision with news analysis"""
        try:
            # Step 1: Fetch/update market data
            await self._update_market_data()
            
            # Step 2: Fetch and analyze latest news (Phase 2 addition)
            await self._update_narrative_data()
            
            # Step 3: Detect current regime probabilities (now includes narratives)
            regime_signal = await self._detect_regimes()
            
            if not regime_signal:
                return self._output("NO_TRADE", 0.0, {}, "Insufficient data for regime detection")
            
            # Step 4: Map regimes to factor tilts
            factor_tilts = self._compute_factor_tilts(regime_signal.regime_probs)
            
            # Step 5: Optimize portfolio weights
            target_weights = self._optimize_portfolio(factor_tilts)
            
            # Step 6: Generate trading decision
            decision, confidence = self._generate_decision(target_weights, regime_signal)
            
            inputs = {
                "regime_probabilities": regime_signal.regime_probs,
                "dominant_regime": regime_signal.dominant_regime.name,
                "regime_confidence": regime_signal.dominant_regime.confidence,
                "factor_tilts": factor_tilts,
                "target_weights": target_weights,
                "risk_budget": regime_signal.risk_budget_used,
                "narrative_signals": self._get_narrative_summary() if self.narrative_cache else {}
            }
            
            notes = f"Regime: {regime_signal.dominant_regime.name} ({regime_signal.dominant_regime.confidence:.1%} conf)"
            if self.narrative_cache:
                notes += f" | News: {self.narrative_cache.dominant_themes[:2]}"
            
            return self._output(decision, confidence, inputs, notes)
            
        except Exception as e:
            logger.error("nrt.run.failed", error=str(e))
            return self._output("NO_TRADE", 0.0, {}, f"NRT error: {str(e)}")
    
    async def _update_market_data(self) -> None:
        """Fetch latest market data for all NRT ETFs"""
        if self.last_update and (datetime.now(timezone.utc) - self.last_update).seconds < 3600:
            return  # Use cache if less than 1 hour old
        
        async with httpx.AsyncClient() as client:
            tasks = []
            for ticker in NRT_ETFS.keys():
                if ticker not in ['VIX', 'DXY']:  # Skip non-polygon tickers for now
                    tasks.append(self._fetch_etf_data(client, ticker))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ticker, result in zip(NRT_ETFS.keys(), results):
                if isinstance(result, Exception):
                    logger.warning("nrt.data.fetch_failed", ticker=ticker, error=str(result))
                else:
                    self.data_cache[ticker] = result
        
        # Add synthetic VIX/DXY proxies for now
        if 'SPY' in self.data_cache:
            self.data_cache['VIX'] = self._create_vix_proxy(self.data_cache['SPY'])
            self.data_cache['DXY'] = self._create_dxy_proxy(self.data_cache['SPY'])
        
        self.last_update = datetime.now(timezone.utc)
    
    async def _update_narrative_data(self) -> None:
        """Phase 2: Fetch and analyze latest news for narrative signals"""
        try:
            # Skip if updated recently (cache for 30 minutes)
            if (self.narrative_cache and 
                hasattr(self.narrative_cache, 'timestamp') and 
                (datetime.now(timezone.utc) - self.narrative_cache.timestamp).seconds < 1800):
                return
            
            logger.info("nrt.narrative.updating")
            
            # Fetch latest news (last 24 hours)
            articles = await self.news_service.fetch_latest_news(lookback_hours=24)
            
            if not articles:
                logger.warning("nrt.narrative.no_articles")
                return
            
            # Analyze narratives with GPT-4o
            analyses = await self.news_service.analyze_narratives(articles)
            
            if not analyses:
                logger.warning("nrt.narrative.no_analyses") 
                return
            
            # Compute market-level narrative indicators
            self.narrative_cache = self.news_service.compute_market_narrative(analyses)
            
            logger.info("nrt.narrative.updated",
                       articles_count=len(articles),
                       analyses_count=len(analyses),
                       dominant_themes=self.narrative_cache.dominant_themes[:3])
            
        except Exception as e:
            logger.error("nrt.narrative.update_failed", error=str(e))
            # Continue without narratives if news analysis fails
        
    async def _fetch_etf_data(self, client: httpx.AsyncClient, ticker: str) -> pd.DataFrame:
        """Fetch historical data for a single ETF"""
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=self.lookback_days)
        
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            "adjusted": "true",
            "sort": "asc", 
            "limit": 50000,
            "apiKey": self.settings.polygon_api_key
        }
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            raise ValueError(f"No data returned for {ticker}")
        
        # Convert to DataFrame
        df = pd.DataFrame(data["results"])
        df['date'] = pd.to_datetime(df['t'], unit='ms')
        df = df.set_index('date')[['o', 'h', 'l', 'c', 'v']]
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Calculate returns
        df['return'] = df['close'].pct_change()
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        
        return df.dropna()
    
    def _create_vix_proxy(self, spy_data: pd.DataFrame) -> pd.DataFrame:
        """Create VIX proxy using SPY volatility"""
        vix_proxy = spy_data.copy()
        # 21-day rolling volatility * sqrt(252) * 100
        vix_proxy['close'] = spy_data['return'].rolling(21).std() * np.sqrt(252) * 100
        vix_proxy['return'] = vix_proxy['close'].pct_change()
        return vix_proxy
    
    def _create_dxy_proxy(self, spy_data: pd.DataFrame) -> pd.DataFrame:
        """Create DXY proxy (inverse SPY for now)"""
        dxy_proxy = spy_data.copy()
        dxy_proxy['close'] = 100 - spy_data['close'].pct_change().cumsum() * 10
        dxy_proxy['return'] = dxy_proxy['close'].pct_change()
        return dxy_proxy
    
    async def _detect_regimes(self) -> Optional[NRTSignal]:
        """Phase 2: Enhanced regime detection using price + narrative signals"""
        try:
            # Get key market indicators
            if 'SPY' not in self.data_cache or len(self.data_cache['SPY']) < 100:
                return None
                
            spy_data = self.data_cache['SPY']
            vix_data = self.data_cache.get('VIX', spy_data)
            
            # Create regime indicators
            spy_ret = spy_data['return'].iloc[-60:]  # Last 60 days
            vix_level = vix_data['close'].iloc[-60:]  # VIX level
            
            recent_spy_mean = spy_ret.mean()
            recent_spy_vol = spy_ret.std()
            recent_vix_mean = vix_level.mean()
            
            # Base regime probabilities from price data (Phase 1 logic)
            base_regime_probs = {}
            
            if recent_spy_mean > 0.001 and recent_vix_mean < 20:
                base_regime_probs = {'growth_on': 0.6, 'tightening': 0.2, 'inflation_shock': 0.1, 'liquidity_crunch': 0.1}
            elif recent_spy_mean > -0.001 and 20 <= recent_vix_mean < 30:
                base_regime_probs = {'growth_on': 0.2, 'tightening': 0.5, 'inflation_shock': 0.2, 'liquidity_crunch': 0.1}
            elif recent_spy_mean < -0.001 and recent_vix_mean >= 30:
                base_regime_probs = {'growth_on': 0.05, 'tightening': 0.15, 'inflation_shock': 0.2, 'liquidity_crunch': 0.6}
            else:
                base_regime_probs = {'growth_on': 0.15, 'tightening': 0.25, 'inflation_shock': 0.4, 'liquidity_crunch': 0.2}
            
            # Phase 2: Adjust probabilities using narrative signals
            if self.narrative_cache:
                regime_probs = self._blend_narrative_signals(base_regime_probs, self.narrative_cache)
            else:
                regime_probs = base_regime_probs
            
            # Find dominant regime
            dominant_name = max(regime_probs.items(), key=lambda x: x[1])[0]
            dominant_prob = regime_probs[dominant_name]
            
            # Calculate confidence (higher with narrative confirmation)
            entropy = -sum(p * np.log(p + 1e-10) for p in regime_probs.values())
            max_entropy = np.log(len(regime_probs))
            base_confidence = 1.0 - (entropy / max_entropy)
            
            # Boost confidence if narratives confirm price signals
            narrative_boost = 0.0
            if self.narrative_cache and dominant_name in self.narrative_cache.regime_signals:
                narrative_signal = self.narrative_cache.regime_signals[dominant_name]
                narrative_boost = narrative_signal * 0.2  # Up to 20% boost
            
            confidence = min(base_confidence + narrative_boost, 1.0)
            
            dominant_regime = RegimeState(
                name=dominant_name,
                probability=dominant_prob,
                confidence=confidence,
                duration_days=10  # Default TTL
            )
            
            return NRTSignal(
                regime_probs=regime_probs,
                dominant_regime=dominant_regime,
                factor_tilts={},  # Will be computed next
                target_weights={},  # Will be computed next
                confidence=confidence,
                risk_budget_used=0.0
            )
            
        except Exception as e:
            logger.error("nrt.regime_detection.failed", error=str(e))
            return None
    
    def _blend_narrative_signals(self, base_probs: Dict[str, float], 
                                narrative: MarketNarrative) -> Dict[str, float]:
        """Blend price-based regime probs with narrative signals"""
        # Start with base probabilities
        blended_probs = base_probs.copy()
        
        # Apply narrative adjustments (weighted by confidence)
        narrative_weight = 0.3  # 30% weight to narratives, 70% to price
        
        for regime, narrative_signal in narrative.regime_signals.items():
            if regime in blended_probs:
                # Adjust probability based on narrative signal
                adjustment = (narrative_signal - 0.5) * narrative_weight  # -0.15 to +0.15
                blended_probs[regime] = max(0.01, blended_probs[regime] + adjustment)
        
        # Renormalize probabilities
        total_prob = sum(blended_probs.values())
        if total_prob > 0:
            blended_probs = {k: v/total_prob for k, v in blended_probs.items()}
        
        return blended_probs
    
    def _get_narrative_summary(self) -> Dict[str, Any]:
        """Get summary of current narrative state"""
        if not self.narrative_cache:
            return {}
            
        return {
            "media_pessimism": round(self.narrative_cache.media_pessimism, 3),
            "policy_uncertainty": round(self.narrative_cache.policy_uncertainty, 3),
            "news_volatility": round(self.narrative_cache.news_volatility, 3),
            "unusual_news_score": round(self.narrative_cache.unusual_news_score, 3),
            "dominant_themes": self.narrative_cache.dominant_themes[:5],
            "regime_signals": {k: round(v, 3) for k, v in self.narrative_cache.regime_signals.items()}
        }
    
    def _compute_factor_tilts(self, regime_probs: Dict[str, float]) -> Dict[str, float]:
        """Map regime probabilities to factor tilts using policy matrix"""
        factor_tilts = {}
        
        # Get all factors from policy matrix
        all_factors = set()
        for regime_policy in REGIME_POLICY_MATRIX.values():
            all_factors.update(regime_policy.keys())
        
        # Compute expected tilts: sum(prob_r * tilt_r) for each factor
        for factor in all_factors:
            expected_tilt = 0.0
            for regime, prob in regime_probs.items():
                if factor in REGIME_POLICY_MATRIX.get(regime, {}):
                    expected_tilt += prob * REGIME_POLICY_MATRIX[regime][factor]
            factor_tilts[factor] = expected_tilt
            
        return factor_tilts
    
    def _optimize_portfolio(self, factor_tilts: Dict[str, float]) -> Dict[str, float]:
        """Phase 1: Simple proportional allocation (before full cvxpy optimizer)"""
        target_weights = {}
        
        # Simple risk budgeting approach
        total_abs_tilts = sum(abs(tilt) for tilt in factor_tilts.values())
        
        if total_abs_tilts == 0:
            # No tilts, equal risk allocation
            n_assets = len([f for f in factor_tilts.keys() if f in ['MTUM', 'VLUE', 'QUAL', 'USMV']])
            equal_weight = 0.8 / n_assets if n_assets > 0 else 0
            
            for factor in ['MTUM', 'VLUE', 'QUAL', 'USMV']:
                if factor in factor_tilts:
                    target_weights[factor] = equal_weight
        else:
            # Scale tilts to target gross exposure
            scale_factor = min(self.max_gross, 0.8) / total_abs_tilts
            
            for factor, tilt in factor_tilts.items():
                if factor in NRT_ETFS:  # Only trade available ETFs
                    weight = tilt * scale_factor
                    # Apply position limits
                    weight = np.clip(weight, -self.max_position, self.max_position)
                    target_weights[factor] = weight
        
        return target_weights
    
    def _generate_decision(self, target_weights: Dict[str, float], 
                          regime_signal: NRTSignal) -> Tuple[Decision, float]:
        """Generate final trading decision based on target weights"""
        
        # Calculate net exposure and conviction
        long_exposure = sum(w for w in target_weights.values() if w > 0)
        short_exposure = abs(sum(w for w in target_weights.values() if w < 0))
        net_exposure = long_exposure - short_exposure
        gross_exposure = long_exposure + short_exposure
        
        # Decision logic based on net exposure
        if net_exposure > 0.1:
            decision = "BUY"
        elif net_exposure < -0.1:
            decision = "SELL"  
        else:
            decision = "HOLD"
        
        # Confidence based on regime confidence and position conviction
        regime_confidence = regime_signal.dominant_regime.confidence
        position_conviction = min(gross_exposure / self.max_gross, 1.0)
        
        confidence = (regime_confidence * 0.7) + (position_conviction * 0.3)
        confidence = max(0.0, min(1.0, confidence))
        
        return decision, confidence
    
    @staticmethod
    def _output(decision: Decision, confidence: float, inputs: Dict[str, Any], notes: str) -> AgentOutput:
        return AgentOutput(
            agent_id="nrt",
            decision=decision,
            confidence=float(min(max(confidence, 0.0), 1.0)),
            inputs=inputs,
            notes=notes,
        )