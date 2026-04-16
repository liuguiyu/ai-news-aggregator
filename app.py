"""
Flask web application for AI News Aggregator
Provides REST API and serves the web frontend
"""
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from models import Database, Article
from news_fetcher import NewsFetcher


class NewsAggregatorApp:
    """Main Flask application class"""

    def __init__(self, config_path: str = "config.json"):
        self.app = Flask(__name__, static_folder='static', template_folder='templates')
        CORS(self.app)

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.db = Database(self.config['database_path'])
        self.fetcher = NewsFetcher(config_path)
        self.update_thread = None
        self.is_updating = False

        self._setup_routes()
        self._start_background_updates()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route('/')
        def index():
            """Serve the main application page"""
            return render_template('index.html')

        @self.app.route('/api/articles')
        def get_articles():
            """Get articles with filtering and pagination"""
            try:
                # Get query parameters
                source = request.args.get('source', None)
                category = request.args.get('category', None)
                limit = min(int(request.args.get('limit', 50)), 200)
                offset = int(request.args.get('offset', 0))
                bookmarked_only = request.args.get('bookmarked', 'false').lower() == 'true'
                search = request.args.get('search', None)

                articles = self.db.get_articles(
                    source=source,
                    category=category,
                    limit=limit,
                    offset=offset,
                    bookmarked_only=bookmarked_only
                )

                # Convert to dict for JSON response
                articles_data = [article.to_dict() for article in articles]

                # Filter by search query if provided
                if search:
                    search_lower = search.lower()
                    articles_data = [
                        article for article in articles_data
                        if search_lower in article['title'].lower() or
                        search_lower in article['summary'].lower()
                    ]

                return jsonify({
                    'success': True,
                    'articles': articles_data,
                    'total': len(articles_data)
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/articles/<int:article_id>')
        def get_article(article_id):
            """Get single article by ID"""
            try:
                article = self.db.get_article_by_id(article_id)
                if article:
                    return jsonify({
                        'success': True,
                        'article': article.to_dict()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Article not found'
                    }), 404

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/articles/<int:article_id>/read', methods=['POST'])
        def mark_as_read(article_id):
            """Mark article as read"""
            try:
                success = self.db.mark_as_read(article_id)
                return jsonify({
                    'success': success,
                    'message': 'Article marked as read' if success else 'Article not found'
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/articles/<int:article_id>/bookmark', methods=['POST'])
        def toggle_bookmark(article_id):
            """Toggle bookmark status"""
            try:
                success = self.db.toggle_bookmark(article_id)
                return jsonify({
                    'success': success,
                    'message': 'Bookmark toggled' if success else 'Article not found'
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/articles/<int:article_id>/content')
        def get_article_content(article_id):
            """Get full article content for offline reading"""
            try:
                article = self.db.get_article_by_id(article_id)
                if not article:
                    return jsonify({
                        'success': False,
                        'error': 'Article not found'
                    }), 404

                # Fetch full content if not already available
                content = self.fetcher.fetch_article_content(article)

                return jsonify({
                    'success': True,
                    'content': content
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/sources')
        def get_sources():
            """Get information about configured news sources"""
            try:
                sources = self.fetcher.get_source_info()
                return jsonify({
                    'success': True,
                    'sources': sources
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/stats')
        def get_stats():
            """Get database statistics"""
            try:
                stats = self.db.get_stats()
                return jsonify({
                    'success': True,
                    'stats': stats
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/update', methods=['POST'])
        def trigger_update():
            """Manually trigger news update"""
            try:
                if not self.is_updating:
                    self._perform_update()
                    return jsonify({
                        'success': True,
                        'message': 'Update started'
                    })
                else:
                    return jsonify({
                        'success': True,
                        'message': 'Update already in progress'
                    })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/config', methods=['GET', 'PUT'])
        def config():
            """Get or update configuration"""
            try:
                if request.method == 'GET':
                    return jsonify({
                        'success': True,
                        'config': self.config
                    })
                elif request.method == 'PUT':
                    new_config = request.json
                    # Validate configuration
                    if 'update_interval_minutes' in new_config:
                        self.config['update_interval_minutes'] = new_config['update_interval_minutes']
                    if 'max_articles_per_source' in new_config:
                        self.config['max_articles_per_source'] = new_config['max_articles_per_source']

                    # Save to file
                    with open('config.json', 'w') as f:
                        json.dump(self.config, f, indent=2)

                    return jsonify({
                        'success': True,
                        'message': 'Configuration updated'
                    })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """Serve static files"""
            return send_from_directory('static', filename)

    def _start_background_updates(self):
        """Start background thread for periodic updates"""
        def update_worker():
            while True:
                try:
                    # Wait for the configured interval
                    time.sleep(self.config['update_interval_minutes'] * 60)
                    if not self.is_updating:
                        self._perform_update()
                except Exception as e:
                    print(f"Background update error: {e}")
                    time.sleep(60)  # Wait 1 minute on error

        self.update_thread = threading.Thread(target=update_worker, daemon=True)
        self.update_thread.start()

    def _perform_update(self):
        """Perform a news update"""
        self.is_updating = True
        try:
            print(f"Starting news update at {datetime.now()}")
            results = self.fetcher.fetch_all_sources()
            print(f"Update completed: {results}")
        except Exception as e:
            print(f"Update error: {e}")
        finally:
            self.is_updating = False

    def run(self, host='0.0.0.0', port=None, debug=False):
        """Run the Flask application"""
        if port is None:
            port = self.config.get('server_port', 5000)

        print(f"Starting AI News Aggregator on http://{host}:{port}")
        print(f"Update interval: {self.config['update_interval_minutes']} minutes")

        # Do initial update
        self._perform_update()

        self.app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    app = NewsAggregatorApp()
    app.run(debug=True)