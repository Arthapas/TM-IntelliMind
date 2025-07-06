# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TM IntelliMind is a centralized intelligence platform that transforms how organizations capture, process, and leverage business intelligence from meetings. The platform serves as the central nervous system for organizational knowledge, designed specifically for Thailand's non-life insurance sector.

## Technical Stack

- **Backend**: Python Django 4.2.23 with environment-based configuration
- **Database**: SQLite3 (development), PostgreSQL (production)
- **LLM Integration**: LMStudio with configurable endpoint and health checking
- **Audio Transcription**: faster-whisper 1.1.1 with VAD batching and M4 optimization
- **Language Support**: Thai and English with auto-detection and business vocabulary
- **Audio Formats**: MP3, WAV, M4A, MP4 with dual validation (MIME + extension)
- **Frontend**: Bootstrap 5.1.3, vanilla JavaScript with error boundaries
- **Responsive Design**: Wide screen CSS with 5 breakpoints (1200px → 1920px+)
- **Admin Interface**: Fully configured Django admin for all models

## Common Commands

```bash
# Development server (port 8004 may be occupied, use alternatives)
python3 manage.py runserver 8005

# Database operations
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser

# Configuration validation
python3 manage.py check

# Dependency management
pip install -r requirements.txt

# Model pre-loading (recommended on first setup)
python3 manage.py preload_whisper_models --models medium large-v2 --validate

# Performance testing
python3 test_enhanced_whisper.py

# Model cache management
python3 manage.py whisper_cache_info --detailed
python3 manage.py whisper_cache_info --cleanup

# Testing
python3 manage.py test core
python3 manage.py test

# Environment setup for production
export DEBUG=false
export SECRET_KEY="your-secret-key-here"
export DB_NAME="tm_intellimind_db"
export LLM_API_BASE="http://localhost:1234/v1"
```

## Core Architecture

### Database Models & Relationships

The application follows a linear workflow: Meeting → Transcript → Insight

**Meeting** (`core.models.Meeting`):
- UUID primary key with audio file upload to `media/audio/{meeting_id}/`
- Optional user association via `created_by` (not `user`)
- Metadata fields: `title`, `description`, `original_filename`, `file_size`, `duration`

**Transcript** (`core.models.Transcript`):
- OneToOne relationship with Meeting
- Whisper model selection via `whisper_model` field (not `model`)
- Status tracking: pending → processing → completed/failed
- Progress percentage (0-100) and error handling

**Insight** (`core.models.Insight`):
- OneToOne relationship with Meeting
- Structured analysis with `situation` and `insights` fields
- Status and progress tracking similar to Transcript
- Error message storage for debugging

### Core Workflow & API Design

1. **File Upload** (`POST /upload-audio/`): Multi-format validation with security checks
2. **Transcription** (`POST /start-transcription/`): Background processing with real-time progress
3. **Progress Polling** (`GET /transcription-progress/`): Non-blocking status updates
4. **Insight Generation** (`POST /generate-insights/`): LLM-powered analysis
5. **Final Storage** (`POST /save-analysis/`): Persist complete workflow results
6. **Meeting Management** (`DELETE /meeting/<uuid>/delete/`): Complete deletion with file cleanup

All endpoints return standardized JSON with `success` boolean and error handling.

### CSRF Token Handling

**Critical**: CSRF header must use exact format `X-CSRFToken` (not `X-Csrftoken`). Frontend AJAX requests:
```javascript
headers: {
    'X-CSRFToken': csrfToken,  // Exact capitalization required
    'Content-Type': 'application/json',
}
```

### Enhanced Audio Processing

**VAD Batching with M4 Optimization**:
- 12.5x performance improvement through BatchedInferencePipeline
- Automatic Apple Silicon detection and memory optimization
- Dynamic parameter selection based on faster-whisper version (21 parameters vs 6 basic)

**Thai Language Specialization**:
- Business vocabulary integration (32+ insurance terms)
- Enhanced beam search (size 10) with confidence scoring
- Large-v2 model default for 15-20% accuracy improvement
- Automatic language detection with fallback handling

### Security & Error Handling

**Production-Ready Security**:
- Environment-based configuration (DEBUG, SECRET_KEY, database credentials)
- Dual file validation (MIME type AND extension matching required)
- CSRF protection with proper token handling
- Production security headers when DEBUG=False

**Comprehensive Error Handling**:
- LMStudio health checks before API calls
- JSON parsing error boundaries in frontend
- Memory leak prevention in progress polling
- Graceful fallbacks for all external dependencies

## Frontend Architecture

### JavaScript Error Prevention

The frontend uses defensive programming patterns:
- DOM element null checking before manipulation
- Browser compatibility (no optional chaining)
- API error standardization across all endpoints
- Memory cleanup on page unload (timeout clearing)

### Progress Tracking System

Real-time updates for long-running operations:
- WebSocket-like polling with exponential backoff
- Visual progress indicators with status messages
- Background task cancellation support
- Session state persistence across browser refreshes

### Wide Screen Responsive Architecture

**CSS Framework** (`static/css/wide-screen.css`):
- **5 Responsive Breakpoints**: 1200px, 1400px, 1600px, 1920px+ for progressive enhancement
- **Layout Classes**: `home-layout-wide`, `meeting-table-wide`, dashboard layouts
- **Component System**: Meeting cards, dashboard panels, responsive grids
- **Mobile-First**: Maintains compatibility while enhancing wide screen experience

**Key Responsive Patterns**:
```css
/* Standard view (< 1400px) */
.d-xl-none { /* Mobile/tablet layout */ }

/* Wide screen (≥ 1400px) */  
.d-none.d-xl-block { /* Enhanced dashboard layout */ }
```

## Configuration Management

### Environment Variables

**Development** (DEBUG=True):
- SQLite3 database at `db.sqlite3`
- Local file storage
- Console logging

**Production** (DEBUG=False):
- PostgreSQL with environment credentials
- Static file collection required
- Security headers enabled
- File logging to `logs/django.log`

### LMStudio Integration

**Required Configuration**:
- Service running at configurable endpoint (default: `http://localhost:1234/v1`)
- Health check validation before insight generation
- Timeout configuration via `LLM_TIMEOUT` (default: 300s)
- Error handling for connection failures and invalid responses

### Whisper Model Management

**Model Storage**: `~/.cache/huggingface/hub/`
- Primary models: medium (1.4GB), large-v2 (2.9GB)
- Automatic download on first use
- Cache cleanup commands available
- Version compatibility checking

## Testing & Validation

### System Health Checks

```bash
# Validate Django configuration
python3 manage.py check

# Test Whisper installation
python3 -c "from core.utils import BATCHED_INFERENCE_AVAILABLE; print(f'VAD Batching: {BATCHED_INFERENCE_AVAILABLE}')"

# Check M4 optimization
python3 -c "from core.utils import is_apple_silicon; print(f'Apple Silicon: {is_apple_silicon()}')"

# Validate LMStudio connectivity
curl http://localhost:1234/v1/models
```

### Performance Benchmarks

**Expected Performance**:
- 12.5x real-time transcription (1 minute audio in ~5 seconds)
- <2GB memory usage for large-v2 model on M4
- Thai language accuracy: 15-20% improvement over base models

## Development Guidelines

### Daily Working Logs

**IMPORTANT**: At the end of each development session, create a working log in `/working-logs/` following this pattern:

**File Naming**: `YYYY-MM-DD_task-description.md`
**Location**: `/working-logs/` (examples: `2025-07-06_wide-screen-implementation.md`, `2025-07-06_enhanced-landing-page.md`)

**Required Content**:
- Brief, straight-to-the-point documentation for future development reference
- Date, task overview, and completion status
- Technical changes with file references and line numbers
- Features added/modified (what actually changed)
- Next steps or potential future enhancements
- Performance notes and validation results

**Purpose**: Maintain project continuity across chat sessions and serve as reference for future development work.

**Git Integration**: After writing the working log, ALWAYS commit and push changes to maintain repository synchronization:
```bash
git add .
git commit -m "Add working log: [brief task description]

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### TM IntelliMind.md Alignment Check

**MANDATORY**: After completing any development work, always review and update `TM IntelliMind.md` to maintain alignment:

**Required Steps**:
1. **Review Current Status**: Check if implemented features match documented status
2. **Update Implementation Status**: Modify P01/P02/P03 sections to reflect actual state
3. **Technical Stack Updates**: Add new technologies, frameworks, or architectural changes
4. **Security & Performance**: Document new security measures or performance improvements
5. **Roadmap Adjustments**: Move completed items from "Future" to "Recent Enhancements"

**Key Sections to Verify**:
- Implementation Status (P01/P02/P03)
- Technical Stack accuracy
- Security Features completeness
- Recent Enhancements section
- Final timestamp update

**Purpose**: Ensure TM IntelliMind.md remains the authoritative reference for project status and capabilities.

### Code Organization

**Utils Module** (`core/utils.py`):
- Centralized transcription logic with error handling
- LMStudio integration with health checks
- Memory management and performance monitoring
- Version-aware parameter selection

**Views Module** (`core/views.py`):
- API endpoints with standardized JSON responses
- Background task management via threading
- File upload handling with security validation
- Progress tracking for long-running operations
- Meeting deletion with file system cleanup

**Deletion Pattern**:
```python
# Complete meeting deletion with file cleanup
@require_http_methods(["DELETE"])
def delete_meeting(request, meeting_id):
    # 1. Get meeting object
    # 2. Clean up audio files from filesystem  
    # 3. Delete meeting (CASCADE handles related objects)
    # 4. Return success/error JSON response
```

### Common Patterns

**Error Handling Pattern**:
```python
try:
    # Operation code
    if obj:
        obj.status = 'completed'
        obj.save()
except Exception as e:
    if obj:
        obj.status = 'failed'
        obj.error_message = str(e)
        obj.save()
    logger.error(f"Operation failed: {str(e)}")
    raise e
```

**API Response Pattern**:
```python
return JsonResponse({
    'success': True/False,
    'message': 'Status message',
    'data': {...}  # Optional payload
})
```

## Currency Configuration

All financial components use Thai Baht (฿) as the default currency, as the system is designed for Thailand's non-life insurance sector.

## Known Issues & Solutions

**Port Conflicts**: Port 8004 may be occupied; use port 8005 or check with `lsof -i :8004`

**SSL Warnings**: urllib3 LibreSSL warnings are cosmetic and don't affect functionality

**Model Loading**: First-time model downloads may take several minutes; use preload commands for production deployment

**Memory Management**: Large models require >4GB RAM; system automatically monitors and cleans up when usage exceeds 85%

**CSRF Token Capitalization**: Django strictly requires `X-CSRFToken` header format; `X-Csrftoken` will fail with 403 Forbidden

**Wide Screen Implementation**: Only apply layout optimizations, avoid adding dashboard features unless specifically requested