"""
Database models for AI News Aggregator
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict
import hashlib


class Article:
    """Represents a news article"""

    def __init__(self,
                 id: Optional[int] = None,
                 title: str = "",
                 url: str = "",
                 summary: str = "",
                 source: str = "",
                 category: str = "",
                 published_at: Optional[datetime] = None,
                 content: str = "",
                 is_read: bool = False,
                 is_bookmarked: bool = False,
                 created_at: Optional[datetime] = None):
        self.id = id
        self.title = title
        self.url = url
        self.summary = summary
        self.source = source
        self.category = category
        self.published_at = published_at or datetime.now()
        self.content = content
        self.is_read = is_read
        self.is_bookmarked = is_bookmarked
        self.created_at = created_at or datetime.now()

    @property
    def url_hash(self) -> str:
        """Generate hash for duplicate detection"""
        return hashlib.md5(self.url.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert article to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'summary': self.summary,
            'source': self.source,
            'category': self.category,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'content': self.content,
            'is_read': self.is_read,
            'is_bookmarked': self.is_bookmarked,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Article':
        """Create article from dictionary"""
        # Handle both string and datetime objects for published_at/created_at
        published_at = data.get('published_at')
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at) if published_at else None

        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at) if created_at else None

        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            url=data.get('url', ''),
            summary=data.get('summary', ''),
            source=data.get('source', ''),
            category=data.get('category', ''),
            published_at=published_at,
            content=data.get('content', ''),
            is_read=data.get('is_read', False),
            is_bookmarked=data.get('is_bookmarked', False),
            created_at=created_at
        )


class Database:
    """SQLite database for storing articles"""

    def __init__(self, db_path: str = "ai_news.db"):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    url_hash TEXT UNIQUE NOT NULL,
                    summary TEXT,
                    source TEXT NOT NULL,
                    category TEXT,
                    published_at TIMESTAMP,
                    content TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    is_bookmarked BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    type TEXT NOT NULL,
                    category TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_fetched TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_articles_bookmarked ON articles(is_bookmarked)
            """)

    def save_article(self, article: Article) -> bool:
        """Save article to database, returns True if new article was inserted"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO articles
                    (title, url, url_hash, summary, source, category, published_at, content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.title,
                    article.url,
                    article.url_hash,
                    article.summary,
                    article.source,
                    article.category,
                    article.published_at,
                    article.content
                ))

                if cursor.rowcount > 0:
                    return True
                return False
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def save_articles(self, articles: List[Article]) -> int:
        """Save multiple articles, returns number of new articles inserted"""
        count = 0
        for article in articles:
            if self.save_article(article):
                count += 1
        return count

    def get_articles(self,
                     source: Optional[str] = None,
                     category: Optional[str] = None,
                     limit: int = 50,
                     offset: int = 0,
                     bookmarked_only: bool = False) -> List[Article]:
        """Get articles with filtering"""
        query = "SELECT * FROM articles WHERE 1=1"
        params = []

        if source:
            query += " AND source = ?"
            params.append(source)

        if category:
            query += " AND category = ?"
            params.append(category)

        if bookmarked_only:
            query += " AND is_bookmarked = 1"

        query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        articles = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    article_data = dict(row)
                    article_data['published_at'] = datetime.fromisoformat(article_data['published_at']) if article_data['published_at'] else None
                    article_data['created_at'] = datetime.fromisoformat(article_data['created_at']) if article_data['created_at'] else None
                    articles.append(Article.from_dict(article_data))
        except sqlite3.Error as e:
            print(f"Database error: {e}")

        return articles

    def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Get single article by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM articles WHERE id = ?", (article_id,))

                row = cursor.fetchone()
                if row:
                    article_data = dict(row)
                    article_data['published_at'] = datetime.fromisoformat(article_data['published_at']) if article_data['published_at'] else None
                    article_data['created_at'] = datetime.fromisoformat(article_data['created_at']) if article_data['created_at'] else None
                    return Article.from_dict(article_data)
        except sqlite3.Error as e:
            print(f"Database error: {e}")

        return None

    def mark_as_read(self, article_id: int) -> bool:
        """Mark article as read"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (article_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def toggle_bookmark(self, article_id: int) -> bool:
        """Toggle bookmark status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE articles SET is_bookmarked = NOT is_bookmarked WHERE id = ?", (article_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM articles")
                total_articles = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0")
                unread_articles = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM articles WHERE is_bookmarked = 1")
                bookmarked_articles = cursor.fetchone()[0]

                cursor.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source")
                source_counts = dict(cursor.fetchall())

                return {
                    'total_articles': total_articles,
                    'unread_articles': unread_articles,
                    'bookmarked_articles': bookmarked_articles,
                    'source_counts': source_counts
                }
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return {}

    def cleanup_old_articles(self, days: int = 7):
        """Remove old articles based on offline storage setting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM articles
                    WHERE created_at < datetime('now', '-' || ? || ' days')
                    AND is_bookmarked = 0
                """, (days,))
                return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return 0


if __name__ == "__main__":
    # Test the database
    db = Database()
    stats = db.get_stats()
    print(f"Database stats: {stats}")