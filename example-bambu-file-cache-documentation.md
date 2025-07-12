# Bambu Lab File Cache Card Example

This is a complete example showing how to create a custom card that interacts with the Bambu Lab integration's file cache system via web interfaces.

## Overview

The example consists of:
1. **Custom Card** (`example-bambu-file-cache-card.js`) - Frontend TypeScript/JavaScript card
2. **API Endpoints** (`example-bambu-file-cache-api.py`) - Backend Python API implementation
3. **Documentation** (this file) - Usage instructions and examples

## Prerequisites

1. **Bambu Lab Integration**: Make sure you have the Bambu Lab integration installed and configured
2. **File Cache Enabled**: Enable the file cache option in your Bambu Lab integration settings
3. **Custom Card Support**: Your Home Assistant instance must support custom cards

## API Endpoints

### 1. File Cache Data API

**Endpoint**: `GET /api/bambu_lab/file_cache/{serial}`

**Description**: Returns a list of cached files for a specific printer.

**Parameters**:
- `serial` (path): The printer's serial number
- `file_type` (query): Filter by file type (`all`, `3mf`, `gcode`, `timelapse`, `thumbnail`)

**Example Request**:
```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "http://your-ha-instance:8123/api/bambu_lab/file_cache/123456?file_type=all"
```

**Example Response**:
```json
{
  "serial": "123456",
  "file_type": "all",
  "files": [
    {
      "filename": "example.3mf",
      "path": "example.3mf",
      "type": "3mf",
      "size": 2048576,
      "size_human": "2.0 MB",
      "modified": "2024-01-15T10:30:00",
      "thumbnail_path": "example.jpg"
    }
  ],
  "total_files": 1,
  "timestamp": "2024-01-15T10:30:00"
}
```

### 2. Media File API

**Endpoint**: `GET /api/bambu_lab/file_cache/{serial}/media/{filepath}`

**Description**: Serves media files (thumbnails) securely.

**Parameters**:
- `serial` (path): The printer's serial number
- `filepath` (path): The relative path to the media file

**Example Request**:
```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "http://your-ha-instance:8123/api/bambu_lab/file_cache/123456/media/example.jpg"
```

**Response**: Binary file content with appropriate headers.

## Custom Card Usage

### Installation

1. Copy the `example-bambu-file-cache-card.js` file to your custom cards directory
2. Add it as a resource in your Lovelace dashboard configuration:

```yaml
# In your Lovelace dashboard configuration
resources:
  - url: /local/custom_cards/example-bambu-file-cache-card.js
    type: module
```

### Basic Configuration

```yaml
type: custom:example-bambu-file-cache-card
entity_id: sensor.bambu_lab_x1c_123456_file_cache
```

### Advanced Configuration

```yaml
type: custom:example-bambu-file-cache-card
entity_id: sensor.bambu_lab_x1c_123456_file_cache
file_type: 3mf  # Filter by file type: all, 3mf, gcode, timelapse, thumbnail
show_thumbnails: true  # Show/hide thumbnails
max_files: 20  # Maximum number of files to display
show_controls: true  # Show refresh and clear cache buttons
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity_id` | string | required | The file cache sensor entity ID |
| `file_type` | string | `all` | Filter files by type |
| `show_thumbnails` | boolean | `true` | Show file thumbnails |
| `max_files` | number | `20` | Maximum files to display |
| `show_controls` | boolean | `true` | Show control buttons |

## Integration Implementation

### 1. Add API Endpoints to Your Integration

Copy the API classes from `example-bambu-file-cache-api.py` into your integration's `__init__.py`:

```python
# In your __init__.py
from .example_bambu_file_cache_api import FileCacheAPIView, FileCacheMediaView

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # ... existing setup code ...
    
    # Register API endpoints
    hass.http.register_view(FileCacheAPIView(hass))
    hass.http.register_view(FileCacheMediaView(hass))
    
    # ... rest of setup code ...
```

### 2. Add Coordinator Methods

Add the example coordinator methods to your `BambuDataUpdateCoordinator` class:

```python
# In your coordinator.py
from .example_bambu_file_cache_api import ExampleCoordinatorMethods

class BambuDataUpdateCoordinator(DataUpdateCoordinator):
    # ... existing code ...
    
    # Add these methods from ExampleCoordinatorMethods
    def get_file_cache_directory(self) -> Optional[str]:
        # Implementation from example
    
    async def get_cached_files(self, file_type: str = 'all') -> List[Dict[str, Any]]:
        # Implementation from example
    
    async def clear_file_cache(self, file_type: str = 'all') -> Dict[str, Any]:
        # Implementation from example
```

### 3. Add File Cache Option

Add the file cache option to your constants and config flow:

```python
# In const.py
class Options(Enum):
    # ... existing options ...
    FILE_CACHE = "file_cache"

OPTION_NAME = {
    # ... existing mappings ...
    Options.FILE_CACHE: "file_cache",
}
```

## Security Considerations

### Authentication
- All API endpoints require authentication via Home Assistant's auth system
- Use Bearer tokens for API access
- The card automatically uses the current user's access token

### File Access Security
- Media files are served through a secure API endpoint
- Path traversal attacks are prevented by checking file paths
- Only files within the cache directory are accessible

### CORS and CSP
- The API endpoints respect Home Assistant's CORS and CSP policies
- No additional configuration needed for security headers

## Error Handling

### API Errors
The API endpoints return appropriate HTTP status codes:
- `200` - Success
- `400` - Bad request (file cache not enabled)
- `403` - Access denied (path traversal attempt)
- `404` - Not found (printer or file not found)
- `500` - Internal server error

### Card Error Handling
The card handles various error scenarios:
- Network errors during API calls
- Missing or invalid entity IDs
- Empty file lists
- Missing thumbnails

## File Types Supported

| Type | Extensions | Description |
|------|------------|-------------|
| `3mf` | `.3mf` | 3D model files |
| `gcode` | `.gcode` | G-code files |
| `timelapse` | `.mp4`, `.avi`, `.mov` | Video files |
| `thumbnail` | `.jpg`, `.jpeg`, `.png`, `.bmp` | Image files |
| `unknown` | Other | Unrecognized file types |

## Thumbnail Support

The system automatically looks for thumbnails for 3MF and G-code files:
- Thumbnails should have the same name as the file with image extensions
- Supported formats: `.jpg`, `.jpeg`, `.png`
- Thumbnails are served through the media API endpoint

## Performance Considerations

### Caching
- Media files are cached for 1 hour by browsers
- File metadata is cached in the card until refresh
- Large file lists are paginated via `max_files` parameter

### File Size Limits
- No hard limits on file sizes
- Consider browser memory limits for large files
- Use appropriate `max_files` setting for performance

## Troubleshooting

### Common Issues

1. **Card not loading**
   - Check that the card file is properly loaded as a resource
   - Verify the entity ID exists and is correct

2. **No files showing**
   - Ensure file cache is enabled in integration settings
   - Check that files exist in the cache directory
   - Verify the printer serial number in the entity ID

3. **Thumbnails not loading**
   - Check that thumbnail files exist alongside the main files
   - Verify file permissions on the cache directory
   - Check browser console for network errors

4. **API errors**
   - Verify authentication token is valid
   - Check Home Assistant logs for backend errors
   - Ensure API endpoints are properly registered

### Debug Mode

Enable debug logging in your Home Assistant configuration:

```yaml
logger:
  default: info
  logs:
    custom_components.bambu_lab: debug
```

## Advanced Usage

### Custom Styling

The card uses CSS custom properties for theming. You can override them:

```css
example-bambu-file-cache-card {
  --primary-color: #your-color;
  --secondary-text-color: #your-color;
  --divider-color: #your-color;
}
```

### Service Integration

The card integrates with existing Bambu Lab services:

```yaml
# Clear cache via service
service: bambu_lab.clear_file_cache
data:
  entity_id: sensor.bambu_lab_x1c_123456_file_cache
  file_type: all
```

### Automation Examples

```yaml
# Refresh file cache when new files are detected
automation:
  - alias: "Refresh file cache on new files"
    trigger:
      platform: state
      entity_id: sensor.bambu_lab_x1c_123456_file_cache
    action:
      - service: homeassistant.reload_config_entry
        target:
          entity_id: sensor.bambu_lab_x1c_123456_file_cache
```

## Contributing

When adapting this example for your own use:

1. **Customize the card name** and element registration
2. **Adjust the API endpoints** to match your integration's domain
3. **Modify file type detection** for your specific use case
4. **Add additional features** like file preview, download, or delete
5. **Implement proper error handling** for your specific requirements

## License

This example is provided as-is for educational purposes. Adapt and modify as needed for your specific use case. 