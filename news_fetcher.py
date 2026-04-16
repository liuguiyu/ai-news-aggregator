"""
News Fetcher module for AI News Aggregator
Handles fetching articles from various sources (RSS, HTML, Reddit, Hacker News)
"""
import requests
import feedparser
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import re
import praw
from urllib.parse import urljoin, urlparse
import sqlite3

from integrations import RedditIntegration, HackerNewsIntegration, ArXivIntegration, AISummaryGenerator

from models import Article, Database


class NewsFetcher:
    """Fetches news articles from various AI news sources"""

    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.sources = self.config['news_sources']
        self.db = Database(self.config['database_path'])
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-News-Aggregator/1.0 (https://github.com/ai-news-aggregator)'
        })

        # Initialize Reddit API if credentials available
        self.reddit = None
        self._init_reddit()

    def _init_reddit(self):
        """Initialize Reddit API client"""
        try:
            # Check if Reddit credentials are available in environment or config
            import os
            client_id = os.environ.get('REDDIT_CLIENT_ID')
            client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
            user_agent = os.environ.get('REDDIT_USER_AGENT', 'AI-News-Aggregator/1.0')

            if client_id and client_secret:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
        except Exception as e:
            print(f"Failed to initialize Reddit API: {e}")
            self.reddit = None

    def fetch_all_sources(self) -> Dict[str, int]:
        """Fetch articles from all configured sources"""
        results = {}

        for source_id, source_config in self.sources.items():
            try:
                if not source_config.get('is_active', True):
                    continue

                print(f"Fetching from {source_config['name']}...")

                if source_config['type'] == 'rss':
                    articles = self._fetch_rss(source_config)
                elif source_config['type'] == 'html':
                    articles = self._fetch_html(source_config)
                elif source_config['type'] == 'reddit':
                    articles = self.reddit_integration.fetch_ai_posts(
                        limit=self.config['max_articles_per_source']
                    )
                elif source_config['type'] == 'hackernews':
                    articles = self.hn_integration.fetch_ai_posts(
                        limit=self.config['max_articles_per_source']
                    )
                elif source_config['type'] == 'arxiv':
                    articles = self.arxiv_integration.fetch_ai_papers(
                        limit=self.config['max_articles_per_source']
                    )
                else:
                    print(f"Unknown source type: {source_config['type']}")
                    continue

                new_count = self.db.save_articles(articles)
                results[source_config['name']] = new_count
                print(f"Added {new_count} new articles from {source_config['name']}")

                # Respect rate limiting
                time.sleep(2)

            except Exception as e:
                print(f"Error fetching from {source_config['name']}: {e}")
                results[source_config['name']] = 0

        # Clean up old articles
        old_removed = self.db.cleanup_old_articles(self.config['offline_storage_days'])
        if old_removed > 0:
            print(f"Removed {old_removed} old articles")

        return results

    def _fetch_rss(self, source_config: Dict) -> List[Article]:
        """Fetch articles from RSS feed"""
        articles = []
        try:
            feed_url = source_config.get('rss_url', source_config['url'])
            feed = feedparser.parse(feed_url)

            if feed.bozo:
                print(f"RSS parsing error for {source_config['name']}: {feed.bozo_exception}")
                return articles

            for entry in feed.entries[:self.config['max_articles_per_source']]:
                # Extract published date
                published_at = None
                if hasattr(entry, 'published_parsed'):
                    published_at = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                elif hasattr(entry, 'updated_parsed'):
                    published_at = datetime.fromtimestamp(time.mktime(entry.updated_parsed))

                # Extract content for summary generation
                raw_content = ""
                if hasattr(entry, 'description'):
                    raw_content = entry.description
                elif hasattr(entry, 'summary'):
                    raw_content = entry.summary
                elif hasattr(entry, 'content'):
                    raw_content = entry.content[0].value if entry.content else ""

                # Clean up HTML tags
                raw_content = re.sub(r'<[^>]+>', '', raw_content)

                # Generate proper summary
                summary = self.generate_summary(raw_content, entry.get('title', 'No Title'))

                # Use full content for the article content field
                full_content = raw_content

                article = Article(
                    title=entry.get('title', 'No Title'),
                    url=entry.get('link', ''),
                    summary=summary,
                    source=source_config['name'],
                    category=source_config.get('category', 'general'),
                    published_at=published_at,
                    content=full_content
                )

                if article.url:  # Only add if URL is valid
                    articles.append(article)

        except Exception as e:
            print(f"Error fetching RSS from {source_config['name']}: {e}")

        return articles

    def _fetch_html(self, source_config: Dict) -> List[Article]:
        """Fetch articles from HTML page"""
        articles = []
        try:
            response = self.session.get(source_config['url'], timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # This is a generic implementation - specific sites may need custom selectors
            article_selectors = [
                {'name': 'article', 'class': True},
                {'name': 'div', 'class': 'article'},
                {'name': 'div', 'class': 'post'},
                {'name': 'div', 'class': 'news-item'},
            ]

            article_elements = []
            for selector in article_selectors:
                if selector.get('class'):
                    elements = soup.find_all(selector['name'], class_=True)
                else:
                    elements = soup.find_all(selector['name'])
                article_elements.extend(elements)

            # Remove duplicates and limit results
            seen_urls = set()
            for element in article_elements[:self.config['max_articles_per_source']]:
                try:
                    # Try to find title and URL
                    title_elem = element.find(['h1', 'h2', 'h3', 'h4'])
                    link_elem = element.find('a', href=True)

                    if not title_elem or not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = link_elem['href']

                    # Make URL absolute
                    if url.startswith('/'):
                        url = urljoin(source_config['url'], url)

                    # Skip if URL already seen
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Extract summary
                    summary_elem = element.find('p')
                    summary = summary_elem.get_text(strip=True)[:500] if summary_elem else ""

                    # Skip if no meaningful title or URL
                    if not title.strip() or not url.strip():
                        continue

                    article = Article(
                        title=title,
                        url=url,
                        summary=summary,
                        source=source_config['name'],
                        category=source_config.get('category', 'general'),
                        published_at=datetime.now(),
                        content=summary
                    )

                    articles.append(article)

                except Exception as e:
                    print(f"Error parsing HTML article element: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching HTML from {source_config['name']}: {e}")

        return articles

    
    def generate_summary(self, content: str, title: str = "") -> str:
        """Generate a proper summary from full content"""
        if not content:
            return ""

        # Remove extra whitespace and normalize
        content = re.sub(r'\s+', ' ', content.strip())

        # Strategy 1: Find the first paragraph that contains key information
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not sentences:
            return content[:300]

        # Strategy 2: Look for sentences that contain important AI-related keywords
        important_keywords = [
            'ai', 'artificial intelligence', 'machine learning', 'neural network',
            'deep learning', 'llm', 'large language model', 'chatgpt', 'gpt',
            'algorithm', 'model', 'training', 'dataset', 'research', 'study',
            'breakthrough', 'innovation', 'technology', 'future'
        ]

        # Score sentences based on keywords and position
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0
            lower_sentence = sentence.lower()

            # Higher score for keywords
            for keyword in important_keywords:
                if keyword in lower_sentence:
                    score += 2

            # Lower score for later sentences (prefer first paragraphs)
            score += max(0, 3 - (i / 5))

            # Bonus for sentences that are neither too short nor too long
            if 50 <= len(sentence) <= 200:
                score += 1

            scored_sentences.append((score, sentence))

        # Sort by score and take top 2-3 sentences
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        best_sentences = [s[1] for s in scored_sentences[:3]]

        if not best_sentences:
            # Fallback: take first 2-3 sentences
            best_sentences = sentences[:3]

        # Create summary
        summary = '. '.join(best_sentences) + '.'

        # Limit length
        return summary[:400]

    def fetch_article_content(self, article: Article) -> str:
        """Fetch full content of an article for offline reading"""
        try:
            if article.content and len(article.content) > 500:
                return article.content  # Already have content

            response = self.session.get(article.url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Try to find main content
            content_selectors = [
                {'name': 'article'},
                {'name': 'div', 'class': 'article-content'},
                {'name': 'div', 'class': 'post-content'},
                {'name': 'div', 'class': 'entry-content'},
                {'name': 'main'},
                {'name': 'div', 'id': 'content'},
            ]

            content = ""
            for selector in content_selectors:
                if 'class' in selector:
                    element = soup.find(selector['name'], class_=selector['class'])
                elif 'id' in selector:
                    element = soup.find(selector['name'], id=selector['id'])
                else:
                    element = soup.find(selector['name'])

                if element:
                    content = element.get_text(strip=True)
                    if len(content) > 200:  # Found meaningful content
                        break

            # Fallback: get all paragraphs
            if len(content) < 200:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs])

            # Save to database
            article.content = content[:10000]  # Limit content size
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute("UPDATE articles SET content = ? WHERE id = ?", (article.content, article.id))

            return article.content

        except Exception as e:
            print(f"Error fetching article content from {article.url}: {e}")
            return article.content

    def get_source_info(self) -> Dict:
        """Get information about configured sources"""
        source_info = {}
        for source_id, config in self.sources.items():
            source_info[source_id] = {
                'name': config['name'],
                'type': config['type'],
                'category': config.get('category', 'general'),
                'url': config['url'],
                'is_active': config.get('is_active', True)
            }
        return source_info


if __name__ == "__main__":
    # Test the news fetcher
    fetcher = NewsFetcher()
    print("Starting news fetch...")
    results = fetcher.fetch_all_sources()
    print(f"Fetch results: {results}")

    # Show database stats
    db = Database()
    stats = db.get_stats()
    print(f"Database stats: {stats}")