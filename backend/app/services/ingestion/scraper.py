import aiohttp
from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle
from typing import Optional, Dict
import re
from datetime import datetime


class ArticleScraper:
    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        
        noise_patterns = [
            r'Representative Image[^.]*\.',
            r'Photo Credit[^.]*\.',
            r'Photo:\s*[^.]*\.',
            r'Image:\s*[^.]*\.',
            r'None\.\.\.',
            r'Breaking News[^.]*\.',
            r'LIVE[^.]*\.',
            r'Click here[^.]*\.',
            r'Read more[^.]*\.',
            r'Subscribe[^.]*\.',
            r'Follow us[^.]*\.',
            r'Share this[^.]*\.',
            r'ADVERTISEMENT[^.]*\.',
            r'AD[^.]*\.',
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    @staticmethod
    async def scrape_article(url: str) -> Optional[Dict]:
        try:
            article = NewspaperArticle(url)
            article.download()
            article.parse()
            
            if not article.text or len(article.text) < 100:
                result = await ArticleScraper._scrape_with_bs4(url)
            else:
                result = {
                    "title": article.title,
                    "text": article.text,
                    "author": ", ".join(article.authors) if article.authors else None,
                    "published_at": article.publish_date or datetime.utcnow(),
                    "raw_html": article.html,
                    "images": article.images,
                    "keywords": article.keywords
                }
            
            if result and result.get("text"):
                result["text"] = ArticleScraper._clean_text(result["text"])
            
            return result
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            result = await ArticleScraper._scrape_with_bs4(url)
            if result and result.get("text"):
                result["text"] = ArticleScraper._clean_text(result["text"])
            return result
    
    @staticmethod
    async def _scrape_with_bs4(url: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    noise_selectors = [
                        '.caption', '.image-credit', '.photo-credit', '.credit',
                        '.breaking-news-banner', '.alert', '.notification',
                        '.sidebar', '.advertisement', '.ad', '.sponsored',
                        '.social-share', '.share-buttons', '.newsletter',
                        'nav', 'footer', 'header', '.menu', '.navigation'
                    ]
                    
                    for selector in noise_selectors:
                        for elem in soup.select(selector):
                            elem.decompose()
                    
                    title = None
                    if soup.title:
                        title = soup.title.get_text()
                    elif soup.find("h1"):
                        title = soup.find("h1").get_text()
                    
                    content_selectors = [
                        'article',
                        '[role="article"]',
                        '.article-content',
                        '.post-content',
                        '.entry-content',
                        'main',
                        '.content'
                    ]
                    
                    text = ""
                    for selector in content_selectors:
                        content = soup.select_one(selector)
                        if content:
                            text = content.get_text(separator=' ', strip=True)
                            break
                    
                    if not text:
                        text = soup.get_text(separator=' ', strip=True)
                    
                    text = ArticleScraper._clean_text(text)
                    
                    author = None
                    author_selectors = [
                        '[rel="author"]',
                        '.author',
                        '[itemprop="author"]',
                        'meta[name="author"]'
                    ]
                    for selector in author_selectors:
                        author_elem = soup.select_one(selector)
                        if author_elem:
                            author = author_elem.get_text() if hasattr(author_elem, 'get_text') else author_elem.get('content')
                            break
                    
                    published_at = datetime.utcnow()
                    date_selectors = [
                        'time[datetime]',
                        '[itemprop="datePublished"]',
                        'meta[property="article:published_time"]'
                    ]
                    for selector in date_selectors:
                        date_elem = soup.select_one(selector)
                        if date_elem:
                            date_str = date_elem.get('datetime') or date_elem.get('content')
                            if date_str:
                                try:
                                    published_at = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                except:
                                    pass
                            break
                    
                    return {
                        "title": title or "Untitled",
                        "text": text,
                        "author": author,
                        "published_at": published_at,
                        "raw_html": html
                    }
        except Exception as e:
            print(f"Error in BS4 scrape for {url}: {str(e)}")
            return None

