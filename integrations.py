"""
Integration modules for additional news sources
Reddit AI and Hacker News integrations
"""
import praw
import requests
from datetime import datetime
from typing import List, Dict
import os
from models import Article
import anthropic
import json


class RedditIntegration:
    """Reddit API integration for AI-related posts"""

    def __init__(self):
        self.client = None
        self._initialize()

    def _initialize(self):
        """Initialize Reddit API client"""
        try:
            # Try to get credentials from environment variables
            client_id = os.environ.get('REDDIT_CLIENT_ID')
            client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
            user_agent = os.environ.get('REDDIT_USER_AGENT', 'AI-News-Aggregator/1.0')

            if client_id and client_secret:
                self.client = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
                print("Reddit API initialized successfully")
            else:
                print("Reddit credentials not found. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.")
        except Exception as e:
            print(f"Failed to initialize Reddit API: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Reddit API is available"""
        return self.client is not None

    def fetch_ai_posts(self, subreddit_name: str = "artificial", limit: int = 50) -> List[Article]:
        """Fetch AI-related posts from Reddit"""
        articles = []

        if not self.is_available():
            return articles

        try:
            subreddit = self.client.subreddit(subreddit_name)

            # Search for AI-related content
            search_queries = [
                "AI", "artificial intelligence", "machine learning", "deep learning",
                "neural networks", "LLM", "GPT", "OpenAI", "Anthropic", "Claude"
            ]

            seen_urls = set()

            for query in search_queries:
                try:
                    # Search in hot posts
                    for post in subreddit.search(query, limit=limit // len(search_queries), sort='hot'):
                        if post.url in seen_urls:
                            continue
                        seen_urls.add(post.url)

                        # Skip self-posts without content
                        if post.is_self and not post.selftext:
                            continue

                        # Create article
                        article = self._create_article_from_post(post, "Reddit r/artificial")
                        if article:
                            articles.append(article)

                except Exception as e:
                    print(f"Error searching Reddit for '{query}': {e}")

            print(f"Fetched {len(articles)} AI-related posts from Reddit r/{subreddit_name}")
            return articles

        except Exception as e:
            print(f"Error fetching from Reddit: {e}")
            return articles

    def _create_article_from_post(self, post, source: str) -> Article:
        """Create Article object from Reddit post"""
        try:
            # Extract content
            if post.is_self:
                content = post.selftext[:2000] if post.selftext else ""
                summary = content[:500] if content else "Reddit discussion post"
            else:
                content = ""
                summary = "Link post - click to view original content"

            # Determine category based on post keywords
            title_lower = post.title.lower()
            if 'research' in title_lower or 'paper' in title_lower:
                category = 'research'
            elif 'business' in title_lower or 'startup' in title_lower or 'funding' in title_lower:
                category = 'business'
            else:
                category = 'community'

            return Article(
                title=post.title,
                url=post.url if not post.is_self else f"https://reddit.com{post.permalink}",
                summary=summary,
                source=source,
                category=category,
                published_at=datetime.fromtimestamp(post.created_utc),
                content=content
            )

        except Exception as e:
            print(f"Error creating article from Reddit post: {e}")
            return None


class HackerNewsIntegration:
    """Hacker News API integration for AI-related posts"""

    def __init__(self):
        self.base_url = "https://hn.algolia.com/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-News-Aggregator/1.0'
        })

    def fetch_ai_posts(self, limit: int = 50) -> List[Article]:
        """Fetch AI-related posts from Hacker News"""
        articles = []

        try:
            # Search for AI-related content
            search_queries = [
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "LLM", "GPT", "OpenAI", "Anthropic", "Claude"
            ]

            seen_urls = set()

            for query in search_queries:
                try:
                    # Search Hacker News
                    search_url = f"{self.base_url}/search"
                    params = {
                        'query': query,
                        'tags': 'story',
                        'hitsPerPage': limit // len(search_queries)
                    }

                    response = self.session.get(search_url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    for hit in data.get('hits', []):
                        url = hit.get('url', '')
                        if url and url in seen_urls:
                            continue
                        if url:
                            seen_urls.add(url)

                        article = self._create_article_from_hit(hit, query)
                        if article:
                            articles.append(article)

                except Exception as e:
                    print(f"Error searching Hacker News for '{query}': {e}")

            print(f"Fetched {len(articles)} AI-related posts from Hacker News")
            return articles

        except Exception as e:
            print(f"Error fetching from Hacker News: {e}")
            return articles

    def _create_article_from_hit(self, hit: Dict, query: str) -> Article:
        """Create Article object from Hacker News hit"""
        try:
            # Extract URL
            url = hit.get('url', '')
            if not url:
                url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

            # Determine category based on search query and content
            query_lower = query.lower()
            if 'research' in query_lower or 'paper' in query_lower:
                category = 'research'
            elif 'business' in query_lower or 'startup' in query_lower:
                category = 'business'
            else:
                category = 'community'

            return Article(
                title=hit.get('title', 'No Title'),
                url=url,
                summary=f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments",
                source='Hacker News AI',
                category=category,
                published_at=datetime.fromtimestamp(hit.get('created_at_i', 0)),
                content=f"Search query: {query}. {hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments"
            )

        except Exception as e:
            print(f"Error creating article from Hacker News hit: {e}")
            return None


class AISummaryGenerator:
    """AI-powered summary generation using Claude API"""

    def __init__(self):
        self.client = None
        self._initialize()

    def _initialize(self):
        """Initialize Claude API client"""
        try:
            # Try both possible environment variable names
            api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
            base_url = os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')

            if api_key:
                # Configure custom endpoint if needed
                if base_url != 'https://api.anthropic.com':
                    self.client = anthropic.Anthropic(
                        api_key=api_key,
                        base_url=base_url
                    )
                else:
                    self.client = anthropic.Anthropic(api_key=api_key)

                print(f"Claude API initialized successfully for AI summaries (using {base_url})")
            else:
                print("Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable.")
                print("AI summaries will use fallback method instead.")
        except Exception as e:
            print(f"Failed to initialize Claude API: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Claude API is available"""
        return self.client is not None

    def generate_summary(self, title: str, content: str, source: str = "") -> str:
        """Generate AI-powered summary using Claude"""
        if not self.client or not content:
            return self._fallback_summary(title, content)

        try:
            # Truncate content if too long
            if len(content) > 8000:
                content = content[:8000] + "..."

            prompt = f"""Please create a concise, informative 2-3 sentence summary of this AI/technology article.

Title: {title}
Source: {source}
Content: {content}

Focus on:
- The main AI/ML breakthrough or news
- Key implications or applications
- Technical significance (if mentioned)

Summary: """

            # Call Claude API - use custom model if configured
            model = os.environ.get('ANTHROPIC_DEFAULT_SONNET_MODEL', 'claude-3-sonnet-20240229')

            # Use beta API for thinking models if needed
            if 'thinking' in model.lower():
                response = self.client.beta.messages.create(
                    model=model,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            else:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

            summary = response.content[0].text.strip()

            # Ensure summary is reasonable length
            if len(summary) < 50 or len(summary) > 500:
                return self._fallback_summary(title, content)

            return summary

        except Exception as e:
            print(f"Error generating AI summary: {e}")
            return self._fallback_summary(title, content)

    def _fallback_summary(self, title: str, content: str) -> str:
        """Fallback summary generation without AI"""
        if not content:
            return "No summary available"

        # Simple extraction-based summary
        sentences = content.split('.')
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if sentences:
            return '. '.join(sentences[:3]) + '.'
        else:
            return content[:300]


class ArXivIntegration:
    """arXiv integration for AI research papers"""

    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.session = requests.Session()

    def fetch_ai_papers(self, limit: int = 30) -> List[Article]:
        """Fetch AI research papers from arXiv"""
        articles = []

        try:
            # Search for AI papers
            search_query = "artificial intelligence OR machine learning OR deep learning"
            params = {
                'search_query': search_query,
                'start': 0,
                'max_results': limit,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }

            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            # Parse Atom XML feed
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            # Namespace for arXiv
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}

            for entry in root.findall('atom:entry', ns):
                try:
                    title = entry.find('atom:title', ns).text.strip() if entry.find('atom:title', ns) is not None else "No Title"
                    url = entry.find('atom:id', ns).text.strip() if entry.find('atom:id', ns) is not None else ""
                    summary = entry.find('atom:summary', ns).text.strip()[:500] if entry.find('atom:summary', ns) is not None else ""

                    # Get published date
                    published_elem = entry.find('atom:published', ns)
                    published_at = None
                    if published_elem is not None and published_elem.text:
                        published_at = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))

                    # Get authors
                    authors = []
                    for author in entry.findall('atom:author/atom:name', ns):
                        if author.text:
                            authors.append(author.text.strip())
                    authors_str = ', '.join(authors[:3])  # First 3 authors

                    # Add authors to summary
                    if authors_str:
                        summary = f"Authors: {authors_str}\n\n{summary}"

                    article = Article(
                        title=title,
                        url=url,
                        summary=summary,
                        source='arXiv AI Research',
                        category='research',
                        published_at=published_at,
                        content=summary
                    )

                    articles.append(article)

                except Exception as e:
                    print(f"Error parsing arXiv entry: {e}")
                    continue

            print(f"Fetched {len(articles)} AI papers from arXiv")
            return articles

        except Exception as e:
            print(f"Error fetching from arXiv: {e}")
            return articles


# Integration test function
def test_integrations():
    """Test all integrations"""
    print("Testing integrations...")

    # Test Reddit
    reddit = RedditIntegration()
    if reddit.is_available():
        print("Testing Reddit integration...")
        articles = reddit.fetch_ai_posts(limit=5)
        print(f"Reddit: {len(articles)} articles fetched")
    else:
        print("Reddit integration not available (missing credentials)")

    # Test Hacker News
    print("Testing Hacker News integration...")
    hn = HackerNewsIntegration()
    articles = hn.fetch_ai_posts(limit=5)
    print(f"Hacker News: {len(articles)} articles fetched")

    # Test arXiv
    print("Testing arXiv integration...")
    arxiv = ArXivIntegration()
    articles = arxiv.fetch_ai_papers(limit=5)
    print(f"arXiv: {len(articles)} articles fetched")

    print("Integration tests completed")


if __name__ == "__main__":
    test_integrations()