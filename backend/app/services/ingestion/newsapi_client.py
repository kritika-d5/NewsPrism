import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.config import settings


class NewsAPIClient:
    # NewsAPI's free (Developer) plan only serves articles from roughly the
    # last month; any `from` older than that returns 426 Upgrade Required.
    FREE_PLAN_WINDOW_DAYS = 29

    def __init__(self):
        self.api_key = settings.NEWSAPI_KEY
        self.base_url = "https://newsapi.org/v2"

    def _clamp_to_plan_window(
        self,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        earliest = datetime.utcnow() - timedelta(days=self.FREE_PLAN_WINDOW_DAYS)

        def naive(dt: Optional[datetime]) -> Optional[datetime]:
            return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt

        date_from, date_to = naive(date_from), naive(date_to)

        if date_from and date_from < earliest:
            date_from = earliest
        # If the requested range ends before the window even starts, the plan
        # cannot serve it at all — drop the upper bound and search recent news
        # rather than hard-failing with a 426.
        if date_to and date_from and date_to < date_from:
            date_to = None
        return date_from, date_to

    async def search_articles(
        self,
        query: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sources: Optional[List[str]] = None,
        language: str = "en",
        page_size: int = 100
    ) -> List[Dict]:
        date_from, date_to = self._clamp_to_plan_window(date_from, date_to)
        async with httpx.AsyncClient() as client:
            params = {
                "apiKey": self.api_key,
                "q": query,
                "language": language,
                "pageSize": min(page_size, 100),
                "sortBy": "publishedAt",
                "searchIn": "title,description"
            }
            
            if date_from:
                params["from"] = date_from.strftime("%Y-%m-%d")
            if date_to:
                params["to"] = date_to.strftime("%Y-%m-%d")
            if sources:
                params["sources"] = ",".join(sources)
            
            try:
                response = await client.get(
                    f"{self.base_url}/everything",
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "ok":
                    return data.get("articles", [])
                else:
                    raise Exception(f"NewsAPI error: {data.get('message', 'Unknown error')}")
            except httpx.HTTPError as e:
                raise Exception(f"NewsAPI request failed: {str(e)}")
    
    async def get_top_headlines(
        self,
        country: str = "us",
        category: Optional[str] = None,
        sources: Optional[List[str]] = None,
        page_size: int = 100
    ) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            params = {
                "apiKey": self.api_key,
                "pageSize": min(page_size, 100)
            }
            
            if country:
                params["country"] = country
            if category:
                params["category"] = category
            if sources:
                params["sources"] = ",".join(sources)
            
            try:
                response = await client.get(
                    f"{self.base_url}/top-headlines",
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "ok":
                    return data.get("articles", [])
                else:
                    raise Exception(f"NewsAPI error: {data.get('message', 'Unknown error')}")
            except httpx.HTTPError as e:
                raise Exception(f"NewsAPI request failed: {str(e)}")