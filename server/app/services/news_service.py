"""
News ingestion and analysis service for NRT strategy.
Combines Polygon News API with RSS feeds and GPT-4o narrative analysis.
"""

from __future__ import annotations

import asyncio
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid

import httpx
import feedparser
import structlog
from openai import AsyncOpenAI

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

@dataclass
class NewsArticle:
    """Raw news article data"""
    id: str
    title: str
    summary: str
    content: str
    url: str
    source: str
    publish_time: datetime
    tickers: List[str]
    
@dataclass 
class NarrativeAnalysis:
    """GPT-4o extracted narrative insights"""
    narrative_id: str
    publish_time: datetime
    tickers: List[str]
    topics: List[str]
    tone: Dict[str, float]  # {"risk_on": 0.22, "hawkish": 0.71}
    surprises: List[Dict[str, Any]]  # [{"metric": "CPI_core", "actual": 0.3, "consensus": 0.2}]
    causal: List[Dict[str, Any]]  # [{"src": "Fed dots", "rel": "raise_expectations_for", "dst": "real yields", "p": 0.68}]
    embedding_model: str
    embedding: Optional[List[float]] = None

@dataclass
class MarketNarrative:
    """Aggregated narrative state for regime detection"""
    timestamp: datetime
    media_pessimism: float  # Daily tone metric
    policy_uncertainty: float  # EPU proxy
    news_volatility: float  # NVIX proxy
    unusual_news_score: float  # Anomaly detection
    dominant_themes: List[str]
    regime_signals: Dict[str, float]

# RSS News Sources
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://finance.yahoo.com/rss/topstories",
    "https://feeds.bloomberg.com/economics/news.rss",
    "https://feeds.fed.st.louis.org/public/general/news.xml"
]

# GPT-4o prompt for narrative extraction
NARRATIVE_EXTRACTION_PROMPT = """
Analyze this financial news article and extract structured narrative data as JSON:

Article: {article_text}

Extract the following information:

1. **Topics**: List 3-5 key financial topics (e.g., ["policy", "inflation", "earnings", "geopolitics"])

2. **Tone**: Quantify sentiment on 0-1 scale:
   - "risk_on": Market optimism/risk appetite (0=risk-off, 1=risk-on)  
   - "hawkish": Policy stance (0=dovish, 1=hawkish)

3. **Surprises**: Economic data vs expectations in format:
   [{"metric": "metric_name", "actual": number, "consensus": number, "surprise_pct": number}]

4. **Causal**: Cause-effect relationships with confidence:
   [{"src": "source_event", "rel": "relationship", "dst": "destination_impact", "p": 0.0-1.0}]

Return valid JSON only:
{{
  "topics": ["topic1", "topic2"],
  "tone": {{"risk_on": 0.0-1.0, "hawkish": 0.0-1.0}},
  "surprises": [],
  "causal": []
}}
"""

class NewsService:
    """News ingestion and narrative analysis service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None
        self.news_cache: Dict[str, NewsArticle] = {}
        self.narrative_cache: Dict[str, NarrativeAnalysis] = {}
        
    async def fetch_latest_news(self, lookback_hours: int = 24) -> List[NewsArticle]:
        """Fetch news from Polygon and RSS feeds"""
        all_articles = []
        
        # Polygon News API
        polygon_articles = await self._fetch_polygon_news(lookback_hours)
        all_articles.extend(polygon_articles)
        
        # RSS Feeds
        rss_articles = await self._fetch_rss_news(lookback_hours)
        all_articles.extend(rss_articles)
        
        # Deduplicate by content hash
        unique_articles = self._deduplicate_articles(all_articles)
        
        logger.info("news.fetch.completed", 
                   polygon_count=len(polygon_articles),
                   rss_count=len(rss_articles), 
                   unique_count=len(unique_articles))
        
        return unique_articles
    
    async def _fetch_polygon_news(self, lookback_hours: int) -> List[NewsArticle]:
        """Fetch news from Polygon News API"""
        if not self.settings.polygon_api_key:
            logger.warning("news.polygon.no_api_key")
            return []
            
        articles = []
        tickers = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT"]  # Major market movers
        
        async with httpx.AsyncClient() as client:
            for ticker in tickers:
                try:
                    url = "https://api.polygon.io/v2/reference/news"
                    params = {
                        "ticker": ticker,
                        "limit": 20,
                        "order": "desc",
                        "apiKey": self.settings.polygon_api_key
                    }
                    
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    for item in data.get("results", []):
                        # Check if article is within lookback window
                        publish_time = datetime.fromisoformat(item["published_utc"].replace("Z", "+00:00"))
                        if publish_time < datetime.now(timezone.utc) - timedelta(hours=lookback_hours):
                            continue
                            
                        article = NewsArticle(
                            id=f"polygon_{item['id']}",
                            title=item.get("title", ""),
                            summary=item.get("description", ""),
                            content=item.get("description", ""),  # Polygon doesn't provide full content
                            url=item.get("article_url", ""),
                            source="polygon",
                            publish_time=publish_time,
                            tickers=item.get("tickers", [])
                        )
                        articles.append(article)
                        
                except Exception as e:
                    logger.error("news.polygon.fetch_failed", ticker=ticker, error=str(e))
                    
        return articles
    
    async def _fetch_rss_news(self, lookback_hours: int) -> List[NewsArticle]:
        """Fetch news from RSS feeds"""
        articles = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        async with httpx.AsyncClient() as client:
            for feed_url in RSS_FEEDS:
                try:
                    response = await client.get(feed_url, timeout=10.0)
                    response.raise_for_status()
                    
                    # Parse RSS feed
                    feed = feedparser.parse(response.text)
                    
                    for entry in feed.entries[:10]:  # Limit per feed
                        # Parse publish time
                        publish_time = datetime.now(timezone.utc)  # Default
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            publish_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        
                        if publish_time < cutoff_time:
                            continue
                            
                        # Extract financial tickers from content (simple regex could be added)
                        content = entry.get('summary', '') + ' ' + entry.get('description', '')
                        tickers = self._extract_tickers(entry.title + ' ' + content)
                        
                        article = NewsArticle(
                            id=f"rss_{hashlib.md5(entry.link.encode()).hexdigest()[:8]}",
                            title=entry.get('title', ''),
                            summary=entry.get('summary', ''),
                            content=content,
                            url=entry.get('link', ''),
                            source=feed_url.split('/')[2],  # Extract domain
                            publish_time=publish_time,
                            tickers=tickers
                        )
                        articles.append(article)
                        
                except Exception as e:
                    logger.error("news.rss.fetch_failed", feed=feed_url, error=str(e))
                    
        return articles
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from text (simple implementation)"""
        import re
        
        # Common financial tickers pattern
        ticker_pattern = r'\b[A-Z]{1,5}\b'
        potential_tickers = re.findall(ticker_pattern, text)
        
        # Filter to known major tickers
        known_tickers = {"SPY", "QQQ", "IWM", "DIA", "NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META"}
        
        return [ticker for ticker in potential_tickers if ticker in known_tickers]
    
    def _deduplicate_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles based on content similarity"""
        unique_articles = {}
        
        for article in articles:
            # Create content hash for deduplication
            content_hash = hashlib.md5(
                (article.title + article.summary).lower().encode()
            ).hexdigest()
            
            # Keep most recent if duplicate
            if content_hash not in unique_articles or article.publish_time > unique_articles[content_hash].publish_time:
                unique_articles[content_hash] = article
                
        return list(unique_articles.values())
    
    async def analyze_narratives(self, articles: List[NewsArticle]) -> List[NarrativeAnalysis]:
        """Extract narrative insights using GPT-4o"""
        if not self.openai_client:
            logger.warning("news.openai.no_client")
            return []
            
        analyses = []
        
        # Process articles in batches to avoid rate limits
        for i in range(0, len(articles), 5):
            batch = articles[i:i+5]
            batch_tasks = [self._analyze_single_article(article) for article in batch]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for result in batch_results:
                    if isinstance(result, NarrativeAnalysis):
                        analyses.append(result)
                    elif isinstance(result, Exception):
                        logger.error("news.analysis.failed", error=str(result))
                        
                # Rate limiting - sleep between batches
                if i + 5 < len(articles):
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                logger.error("news.batch_analysis.failed", batch_size=len(batch), error=str(e))
                
        logger.info("news.analysis.completed", total_articles=len(articles), successful_analyses=len(analyses))
        return analyses
    
    async def _analyze_single_article(self, article: NewsArticle) -> NarrativeAnalysis:
        """Analyze single article with GPT-4o"""
        try:
            # Prepare article text
            article_text = f"Title: {article.title}\n\nSummary: {article.summary}\n\nContent: {article.content[:2000]}"
            
            # Call GPT-4o for narrative extraction
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency
                messages=[
                    {"role": "system", "content": "You are a financial narrative analyst. Extract structured data from news articles as JSON only."},
                    {"role": "user", "content": NARRATIVE_EXTRACTION_PROMPT.format(article_text=article_text)}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse JSON response
            content = response.choices[0].message.content.strip()
            
            # Clean up response to get valid JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            narrative_data = json.loads(content)
            
            # Generate embedding for content
            embedding = await self._generate_embedding(article_text)
            
            return NarrativeAnalysis(
                narrative_id=str(uuid.uuid4()),
                publish_time=article.publish_time,
                tickers=article.tickers,
                topics=narrative_data.get("topics", []),
                tone=narrative_data.get("tone", {}),
                surprises=narrative_data.get("surprises", []),
                causal=narrative_data.get("causal", []),
                embedding_model="text-embedding-3-small",
                embedding=embedding
            )
            
        except Exception as e:
            logger.error("news.single_analysis.failed", article_id=article.id, error=str(e))
            raise
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI text-embedding-3-small"""
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Truncate to model limit
                encoding_format="float"
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("news.embedding.failed", error=str(e))
            return []
    
    def compute_market_narrative(self, analyses: List[NarrativeAnalysis]) -> MarketNarrative:
        """Aggregate narrative analyses into market-level indicators"""
        if not analyses:
            return MarketNarrative(
                timestamp=datetime.now(timezone.utc),
                media_pessimism=0.5,
                policy_uncertainty=0.5,
                news_volatility=0.5,
                unusual_news_score=0.0,
                dominant_themes=[],
                regime_signals={}
            )
        
        # Compute aggregated metrics
        risk_on_scores = [a.tone.get("risk_on", 0.5) for a in analyses if a.tone]
        hawkish_scores = [a.tone.get("hawkish", 0.5) for a in analyses if a.tone]
        
        media_pessimism = 1.0 - (sum(risk_on_scores) / len(risk_on_scores)) if risk_on_scores else 0.5
        
        # Policy uncertainty from hawkish/dovish variation
        policy_uncertainty = np.std(hawkish_scores) if len(hawkish_scores) > 1 else 0.5
        
        # News volatility from topic diversity
        all_topics = [topic for a in analyses for topic in a.topics]
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
        topic_entropy = -sum((count/len(all_topics)) * np.log(count/len(all_topics) + 1e-10) 
                            for count in topic_counts.values()) if all_topics else 0
        news_volatility = min(topic_entropy / np.log(len(topic_counts) + 1), 1.0) if topic_counts else 0
        
        # Dominant themes
        dominant_themes = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        dominant_themes = [theme[0] for theme in dominant_themes]
        
        # Regime signals based on narrative content
        regime_signals = {
            "growth_on": sum(1 for a in analyses if a.tone.get("risk_on", 0) > 0.6) / len(analyses),
            "tightening": sum(1 for a in analyses if a.tone.get("hawkish", 0) > 0.6) / len(analyses),
            "inflation_shock": sum(1 for a in analyses if "inflation" in a.topics) / len(analyses),
            "liquidity_crunch": media_pessimism * news_volatility
        }
        
        return MarketNarrative(
            timestamp=datetime.now(timezone.utc),
            media_pessimism=media_pessimism,
            policy_uncertainty=policy_uncertainty,
            news_volatility=news_volatility,
            unusual_news_score=news_volatility * media_pessimism,  # Simple anomaly score
            dominant_themes=dominant_themes,
            regime_signals=regime_signals
        )


# Import numpy for calculations
import numpy as np