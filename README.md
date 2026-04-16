# AI News Aggregator

A comprehensive AI news aggregator that collects articles from top AI news sources including Reddit AI and Hacker News.

## Features

- **Multiple News Sources**: Fetches from top AI news websites, Reddit AI discussions, Hacker News, and arXiv research papers
- **Real-time Updates**: Automatic background fetching with configurable intervals
- **Offline Reading**: Full article content storage for offline access
- **Search & Filtering**: Search articles by keyword and filter by source/category/bookmarks
- **Bookmarking**: Save articles for later reading
- **Modern Web Interface**: Responsive Vue.js frontend with real-time updates
- **REST API**: Full-featured API for integration and extension

## Tech Stack

- **Backend**: Python 3 with Flask
- **Frontend**: Vue.js 3 with modern CSS
- **Database**: SQLite
- **Scraping**: BeautifulSoup4, feedparser, requests

## Installation

1. **Clone and navigate to the project**:
```bash
cd ai-news-aggregator
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Optional Reddit Integration**:
Set up Reddit API credentials for full Reddit AI integration:
```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USER_AGENT="AI-News-Aggregator/1.0"
```

## Usage

### Start the Application
```bash
python app.py
```

The application will start on `http://localhost:5000`

### Configuration
Edit `config.json` to customize:
- Update intervals
- News sources
- Number of articles per source
- Offline storage duration

### API Endpoints

- `GET /api/articles` - Get articles with filtering
- `GET /api/articles/{id}` - Get single article
- `POST /api/articles/{id}/read` - Mark as read
- `POST /api/articles/{id}/bookmark` - Toggle bookmark
- `GET /api/articles/{id}/content` - Get full content
- `GET /api/sources` - Get configured sources
- `GET /api/stats` - Get database statistics
- `POST /api/update` - Manual update trigger

## News Sources

- **AI News** (ai-news.net) - Industry trends
- **MIT Technology Review AI** - Research breakthroughs
- **VentureBeat AI** - Business applications
- **The Verge AI** - Consumer technology
- **Synced Review** - Global AI developments
- **Reddit r/artificial** - Community discussions
- **Hacker News AI** - Tech community insights
- **arXiv** - Academic research papers

## Development

### Project Structure
```
ai-news-aggregator/
├── app.py                 # Flask application
├── news_fetcher.py        # Core news collection logic
├── models.py             # Database models
├── integrations.py       # Reddit/HN/arXiv integrations
├── config.json           # Configuration
├── requirements.txt      # Python dependencies
├── static/
│   ├── css/style.css     # Frontend styles
│   └── js/app.js        # Vue.js application
└── templates/
    └── index.html        # Main page template
```

### Testing
```python
# Test news fetcher
python -c "from news_fetcher import NewsFetcher; f = NewsFetcher(); print(f.fetch_all_sources())"

# Test integrations
python integrations.py
```

### Database Management
```python
from models import Database
db = Database()
stats = db.get_stats()
print(stats)
```

## Features in Detail

### Real-time Updates
- Background thread automatically fetches new articles
- Configurable update interval (default: 30 minutes)
- Manual refresh button for instant updates

### Offline Reading
- Full article content is cached when viewed
- Articles stored for configurable duration (default: 7 days)
- Automatic cleanup of old articles

### Search & Filtering
- Full-text search across titles and summaries
- Filter by source, category, and bookmarked status
- Real-time filtering with Vue.js reactivity

### Bookmark System
- Save articles for later reading
- Bookmarked articles never auto-delete
- Easy toggle from article list or modal

## Troubleshooting

### Reddit API Issues
- Ensure Reddit credentials are set in environment variables
- Check Reddit API rate limits
- Verify user agent is properly configured

### RSS Feed Issues
- Some feeds may be blocked - check firewall/proxy settings
- Verify feed URLs in `config.json`
- Check network connectivity

### Database Issues
- Delete `ai_news.db` and restart to recreate database
- Check disk space for large article collections
- Ensure write permissions in application directory

## Future Enhancements

- Email notifications for breaking news
- Mobile app with React Native
- Advanced NLP for article summarization
- User accounts and personalized feeds
- Social sharing features
- Advanced analytics and trending topics

## License

MIT License - feel free to use and modify as needed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and feature requests, please use GitHub issues or contact the development team.