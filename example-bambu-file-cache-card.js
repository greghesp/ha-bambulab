/**
 * Example Bambu Lab File Cache Card
 * 
 * This is a standalone example showing how to create a custom card that
 * interacts with the Bambu Lab integration's file cache system via web interfaces.
 * 
 * Usage in Lovelace:
 * type: custom:example-bambu-file-cache-card
 * entity_id: sensor.bambu_lab_x1c_123456_file_cache
 * file_type: all
 * show_thumbnails: true
 * max_files: 20
 */

class ExampleBambuFileCacheCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this._files = [];
        this._loading = false;
        this._error = null;
        this._config = {};
    }

    static get properties() {
        return {
            hass: {},
            config: {},
            _files: { type: Array },
            _loading: { type: Boolean },
            _error: { type: String }
        };
    }

    setConfig(config) {
        this._config = {
            entity_id: '',
            file_type: 'all',
            show_thumbnails: true,
            max_files: 20,
            show_controls: true,
            ...config
        };
        
        this._files = [];
        this._loading = false;
        this._error = null;
    }

    set hass(hass) {
        this._hass = hass;
        this.updateComplete.then(() => this._updateContent());
    }

    async _updateContent() {
        if (!this._config.entity_id) return;

        const entity = this._hass.states[this._config.entity_id];
        if (!entity) return;

        // Get initial data from entity attributes
        const cacheInfo = entity.attributes;
        if (cacheInfo.recent_files) {
            this._files = cacheInfo.recent_files.slice(0, this._config.max_files);
        }

        this._render();
    }

    async _refreshFiles() {
        if (!this._config.entity_id) return;

        this._loading = true;
        this._error = null;
        this._render();

        try {
            // Extract serial from entity ID (format: sensor.bambu_lab_x1c_SERIAL_file_cache)
            const serial = this._extractSerialFromEntityId();
            
            // Use the API endpoint to get file cache data
            const response = await fetch(`/api/bambu_lab/file_cache/${serial}?file_type=${this._config.file_type}`, {
                headers: {
                    'Authorization': `Bearer ${this._hass.auth.data.access_token}`,
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result && result.files) {
                this._files = result.files.slice(0, this._config.max_files);
            }
        } catch (error) {
            this._error = error.message;
            console.error('Error fetching file cache data:', error);
        } finally {
            this._loading = false;
            this._render();
        }
    }

    async _clearCache() {
        if (!this._config.entity_id) return;

        if (!confirm('Are you sure you want to clear the file cache?')) return;

        try {
            await this._hass.callService('bambu_lab', 'clear_file_cache', {
                entity_id: this._config.entity_id,
                file_type: 'all'
            });
            
            // Refresh the file list
            await this._refreshFiles();
        } catch (error) {
            this._error = error.message;
            this._render();
        }
    }

    _extractSerialFromEntityId() {
        // Extract serial from entity ID (format: sensor.bambu_lab_x1c_SERIAL_file_cache)
        const entityParts = this._config.entity_id.split('_');
        return entityParts[entityParts.length - 2]; // Get the serial part
    }

    _getThumbnailUrl(file) {
        if (!file.thumbnail_path) return null;
        
        const serial = this._extractSerialFromEntityId();
        return `/api/bambu_lab/file_cache/${serial}/media/${file.thumbnail_path}`;
    }

    _render() {
        if (!this.shadowRoot) return;

        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    padding: 16px;
                    background: var(--ha-card-background, white);
                    border-radius: 8px;
                    box-shadow: var(--ha-card-box-shadow, 0 2px 2px 0 rgba(0, 0, 0, 0.14), 0 1px 5px 0 rgba(0, 0, 0, 0.12), 0 3px 1px -2px rgba(0, 0, 0, 0.2));
                    font-family: var(--ha-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif);
                }

                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                }

                .title {
                    font-size: 18px;
                    font-weight: 500;
                    color: var(--primary-text-color);
                }

                .controls {
                    display: flex;
                    gap: 8px;
                }

                .btn {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    background: var(--primary-color);
                    color: white;
                    cursor: pointer;
                    font-size: 14px;
                    transition: background-color 0.2s;
                }

                .btn:hover {
                    background: var(--primary-color-dark);
                }

                .btn.secondary {
                    background: var(--secondary-text-color);
                }

                .btn.secondary:hover {
                    background: var(--disabled-text-color);
                }

                .btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                }

                .loading {
                    text-align: center;
                    padding: 20px;
                    color: var(--secondary-text-color);
                }

                .error {
                    color: var(--error-color);
                    padding: 8px;
                    background: var(--error-color-light);
                    border-radius: 4px;
                    margin-bottom: 16px;
                }

                .file-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 16px;
                }

                .file-card {
                    border: 1px solid var(--divider-color);
                    border-radius: 8px;
                    overflow: hidden;
                    transition: box-shadow 0.2s;
                    background: var(--ha-card-background, white);
                }

                .file-card:hover {
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }

                .file-thumbnail {
                    width: 100%;
                    height: 120px;
                    background: var(--divider-color);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: relative;
                }

                .file-thumbnail img {
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }

                .file-thumbnail .placeholder {
                    color: var(--secondary-text-color);
                    font-size: 24px;
                }

                .file-info {
                    padding: 12px;
                }

                .file-name {
                    font-weight: 500;
                    margin-bottom: 4px;
                    color: var(--primary-text-color);
                    word-break: break-word;
                    font-size: 14px;
                    line-height: 1.3;
                }

                .file-meta {
                    font-size: 12px;
                    color: var(--secondary-text-color);
                    line-height: 1.4;
                }

                .file-type {
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: 500;
                    text-transform: uppercase;
                    margin-bottom: 4px;
                }

                .file-type.3mf { background: #e3f2fd; color: #1976d2; }
                .file-type.gcode { background: #f3e5f5; color: #7b1fa2; }
                .file-type.timelapse { background: #e8f5e8; color: #388e3c; }
                .file-type.thumbnail { background: #fff3e0; color: #f57c00; }
                .file-type.unknown { background: #f5f5f5; color: #666; }

                .empty-state {
                    text-align: center;
                    padding: 40px 20px;
                    color: var(--secondary-text-color);
                }

                .empty-state .icon {
                    font-size: 48px;
                    margin-bottom: 16px;
                }

                .stats {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 16px;
                    padding: 8px 0;
                    border-bottom: 1px solid var(--divider-color);
                    font-size: 12px;
                    color: var(--secondary-text-color);
                }

                .file-count {
                    font-weight: 500;
                }
            </style>

            <div class="header">
                <div class="title">Bambu Lab File Cache</div>
                ${this._config.show_controls ? `
                    <div class="controls">
                        <button class="btn secondary" @click="${() => this._refreshFiles()}" ${this._loading ? 'disabled' : ''}>
                            ${this._loading ? 'Loading...' : 'Refresh'}
                        </button>
                        <button class="btn secondary" @click="${() => this._clearCache()}">
                            Clear Cache
                        </button>
                    </div>
                ` : ''}
            </div>

            ${this._error ? `<div class="error">${this._error}</div>` : ''}

            ${this._files.length > 0 ? `
                <div class="stats">
                    <span class="file-count">${this._files.length} files</span>
                    <span>Filter: ${this._config.file_type}</span>
                </div>
            ` : ''}

            ${this._loading ? `
                <div class="loading">Loading files...</div>
            ` : this._files.length === 0 ? `
                <div class="empty-state">
                    <div class="icon">📁</div>
                    <div>No cached files found</div>
                    <div style="margin-top: 8px; font-size: 12px;">
                        Enable file cache in your Bambu Lab integration settings
                    </div>
                </div>
            ` : `
                <div class="file-grid">
                    ${this._files.map(file => `
                        <div class="file-card">
                            ${this._config.show_thumbnails ? `
                                <div class="file-thumbnail">
                                    ${this._getThumbnailUrl(file) ? `
                                        <img src="${this._getThumbnailUrl(file)}" 
                                             alt="${file.filename}" 
                                             @error="this.style.display='none'">
                                    ` : `
                                        <div class="placeholder">
                                            ${this._getFileIcon(file.type)}
                                        </div>
                                    `}
                                </div>
                            ` : ''}
                            <div class="file-info">
                                <div class="file-type ${file.type}">${file.type}</div>
                                <div class="file-name">${file.filename}</div>
                                <div class="file-meta">
                                    ${file.size_human} • ${this._formatDate(file.modified)}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `}
        `;

        // Add event listeners
        this.shadowRoot.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.getAttribute('@click');
                if (action) {
                    eval(action.replace('() => this.', 'this.'));
                }
            });
        });
    }

    _getFileIcon(type) {
        const icons = {
            '3mf': '📦',
            'gcode': '⚙️',
            'timelapse': '🎬',
            'thumbnail': '🖼️',
            'unknown': '📄'
        };
        return icons[type] || icons.unknown;
    }

    _formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }
}

// Register the custom element
customElements.define('example-bambu-file-cache-card', ExampleBambuFileCacheCard); 