/**
 * AI News Aggregator - Vue.js Application
 */

const { createApp } = Vue;

createApp({
    delimiters: ['${', '}'],
    data() {
        return {
            // State
            articles: [],
            sources: [],
            stats: {},
            isLoading: false,
            isLoadingContent: false,
            selectedArticle: null,
            articleContent: '',

            // Filters
            filters: {
                source: '',
                category: '',
                bookmarkedOnly: false,
                search: ''
            },

            // Pagination
            currentPage: 1,
            articlesPerPage: 50,
            totalArticles: 0,
            unreadArticles: 0,

            // API
            apiBaseUrl: '/api',
            updateInterval: null
        };
    },

    computed: {
        filteredArticles() {
            let filtered = this.articles;

            // Apply source filter
            if (this.filters.source) {
                filtered = filtered.filter(article => article.source === this.filters.source);
            }

            // Apply category filter
            if (this.filters.category) {
                filtered = filtered.filter(article => article.category === this.filters.category);
            }

            // Apply bookmarked filter
            if (this.filters.bookmarkedOnly) {
                filtered = filtered.filter(article => article.is_bookmarked);
            }

            // Apply search filter
            if (this.filters.search) {
                const searchLower = this.filters.search.toLowerCase();
                filtered = filtered.filter(article =>
                    article.title.toLowerCase().includes(searchLower) ||
                    article.summary.toLowerCase().includes(searchLower)
                );
            }

            return filtered;
        }
    },

    watch: {
        // Watch for filter changes and reload articles
        filters: {
            deep: true,
            handler() {
                this.loadArticles();
            }
        }
    },

    methods: {
        // API Methods
        async apiRequest(endpoint, options = {}) {
            try {
                const response = await axios.get(`${this.apiBaseUrl}${endpoint}`, options);
                return response.data;
            } catch (error) {
                console.error('API request failed:', error);
                throw error;
            }
        },

        async apiPost(endpoint, data = {}) {
            try {
                const response = await axios.post(`${this.apiBaseUrl}${endpoint}`, data);
                return response.data;
            } catch (error) {
                console.error('API POST failed:', error);
                throw error;
            }
        },

        // Article Loading
        async loadArticles() {
            this.isLoading = true;
            try {
                const params = new URLSearchParams({
                    limit: this.articlesPerPage,
                    offset: (this.currentPage - 1) * this.articlesPerPage
                });

                // Add filters
                if (this.filters.source) params.append('source', this.filters.source);
                if (this.filters.category) params.append('category', this.filters.category);
                if (this.filters.bookmarkedOnly) params.append('bookmarked', 'true');

                const data = await this.apiRequest(`/articles?${params}`);
                if (data.success) {
                    this.articles = data.articles;
                    this.totalArticles = data.total;
                }
            } catch (error) {
                console.error('Failed to load articles:', error);
            } finally {
                this.isLoading = false;
            }
        },

        async loadArticleContent(article) {
            this.isLoadingContent = true;
            try {
                const data = await this.apiRequest(`/articles/${article.id}/content`);
                if (data.success) {
                    this.articleContent = data.content || article.summary;
                }
            } catch (error) {
                console.error('Failed to load article content:', error);
                this.articleContent = '<p>Failed to load content. <a href="' + article.url + '" target="_blank">Open original article</a> instead.</p>';
            } finally {
                this.isLoadingContent = false;
            }
        },

        // Actions
        async markAsRead(articleId) {
            try {
                await this.apiPost(`/articles/${articleId}/read`);
                // Update local state
                const article = this.articles.find(a => a.id === articleId);
                if (article) {
                    article.is_read = true;
                }
                // Update unread count
                await this.loadStats();
            } catch (error) {
                console.error('Failed to mark as read:', error);
            }
        },

        async toggleBookmark(articleId) {
            try {
                await this.apiPost(`/articles/${articleId}/bookmark`);
                // Update local state
                const article = this.articles.find(a => a.id === articleId);
                if (article) {
                    article.is_bookmarked = !article.is_bookmarked;
                }
            } catch (error) {
                console.error('Failed to toggle bookmark:', error);
            }
        },

        async showArticleContent(article) {
            this.selectedArticle = article;
            this.articleContent = '<p>Loading content...</p>';

            // Fetch full content
            await this.loadArticleContent(article);

            // Mark as read when viewing content
            if (!article.is_read) {
                await this.markAsRead(article.id);
            }
        },

        closeModal() {
            this.selectedArticle = null;
            this.articleContent = '';
        },

        async refreshArticles() {
            this.isLoading = true;
            try {
                const data = await this.apiPost('/update');
                if (data.success) {
                    // Wait a moment for the update to complete
                    setTimeout(() => {
                        this.loadArticles();
                        this.loadStats();
                    }, 2000);
                }
            } catch (error) {
                console.error('Failed to refresh articles:', error);
            } finally {
                setTimeout(() => {
                    this.isLoading = false;
                }, 2000);
            }
        },

        // Configuration
        async loadSources() {
            try {
                const data = await this.apiRequest('/sources');
                if (data.success) {
                    this.sources = Object.entries(data.sources).map(([id, source]) => ({
                        id,
                        ...source
                    }));
                }
            } catch (error) {
                console.error('Failed to load sources:', error);
            }
        },

        async loadStats() {
            try {
                const data = await this.apiRequest('/stats');
                if (data.success) {
                    this.unreadArticles = data.stats.unread_articles || 0;
                }
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        },

        // Utilities
        formatDate(dateString) {
            if (!dateString) return 'Unknown date';
            try {
                const date = new Date(dateString);
                const now = new Date();
                const diffTime = Math.abs(now - date);
                const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

                if (diffDays === 0) {
                    return `Today ${date.toLocaleTimeString()}`;
                } else if (diffDays === 1) {
                    return `Yesterday ${date.toLocaleTimeString()}`;
                } else if (diffDays < 7) {
                    return `${diffDays} days ago ${date.toLocaleTimeString()}`;
                } else {
                    return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
                }
            } catch (error) {
                return 'Invalid date';
            }
        },

        // Auto-update setup
        setupAutoUpdate() {
            // Update every 30 seconds for real-time feel
            this.updateInterval = setInterval(() => {
                this.loadArticles();
                this.loadStats();
            }, 30000);
        },

        cleanup() {
            if (this.updateInterval) {
                clearInterval(this.updateInterval);
            }
        }
    },

    // Lifecycle hooks
    async mounted() {
        // Load initial data
        await Promise.all([
            this.loadArticles(),
            this.loadSources(),
            this.loadStats()
        ]);

        // Setup auto-update
        this.setupAutoUpdate();

        // Handle escape key for modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.selectedArticle) {
                this.closeModal();
            }
        });

        // Handle browser back/forward buttons
        window.addEventListener('popstate', (e) => {
            if (this.selectedArticle) {
                this.closeModal();
            }
        });
    },

    beforeUnmount() {
        this.cleanup();
    }
}).mount('#app');