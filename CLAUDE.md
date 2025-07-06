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

## Development Setup

### Quick Start

```bash
# First-time setup
pip3 install -r requirements.txt
cp .env.example .env.development

# Start development server (automatically finds available port)
./runserver.sh

# Alternative: Manual start
python3 manage.py runserver 8006
```

### Environment Configuration

The project uses python-dotenv for environment management:

- **`.env.development`**: Local development settings (auto-loaded, DEBUG=true by default)
- **`.env`**: Production settings
- **`.env.example`**: Template for environment variables

Priority: `.env.development` > `.env` > environment variables > defaults

## Common Commands

```bash
# Development server - RECOMMENDED: Use the startup script
./runserver.sh  # Automatically finds available port, checks LMStudio, validates environment

# Alternative: Manual server start
python3 manage.py runserver 8006

# Server script features:
# - Automatic port detection (starts at 8006, increments if busy)
# - LMStudio connectivity check with warnings
# - Environment file validation (.env.development)

# Database operations
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py createsuperuser

# Configuration validation
python3 manage.py check

# Dependency management
pip3 install -r requirements.txt

# Model pre-loading (recommended on first setup)
python3 manage.py preload_whisper_models --models medium large-v2 --validate

# Performance testing with example audio
python3 test_enhanced_whisper.py
# Uses example-audio/Commute-from-home.wav for consistent testing

# Model cache management
python3 manage.py whisper_cache_info --detailed
python3 manage.py whisper_cache_info --cleanup

# Testing
python3 manage.py test core
python3 manage.py test

# Production environment setup (use .env file instead)
export DEBUG=false
export SECRET_KEY="your-secret-key-here"
export DB_NAME="tm_intellimind_db"
export LLM_API_BASE="http://localhost:1234/v1"
```

## Core Architecture

### Database Models & Relationships

The application follows a linear workflow: Meeting → Transcript → Insight
For large files: Meeting → AudioChunk (1:N) → Transcript → Insight

**Meeting** (`core.models.Meeting`):
- UUID primary key with audio file upload to `media/audio/{meeting_id}/`
- Optional user association via `created_by` (not `user`)
- Metadata fields: `title`, `description`, `original_filename`, `file_size`, `duration`
- Transcription model selection via `transcription_model` field

**AudioChunk** (`core.models.AudioChunk`):
- ForeignKey relationship with Meeting (1:N for large files)
- Sequential chunk processing with `chunk_index` ordering
- Time-based segmentation: `start_time`, `end_time` (usually 30-second chunks)
- Individual chunk status: pending → processing → completed/failed
- Transcript text storage and confidence scoring per chunk

**Transcript** (`core.models.Transcript`):
- OneToOne relationship with Meeting
- Whisper model selection via `whisper_model` field (not `model`)
- Status tracking: pending → processing → completed/failed
- Progress percentage (0-100) and error handling
- Final assembled transcript from all chunks

**Insight** (`core.models.Insight`):
- OneToOne relationship with Meeting
- Structured analysis with `situation` and `insights` fields
- Status and progress tracking similar to Transcript
- Error message storage for debugging

### Core Workflow & API Design

**Standard Flow** (Small Files <100MB):
1. **File Upload** (`POST /upload-audio/`): Multi-format validation with security checks
2. **Transcription** (`POST /start-transcription/`): Background processing with real-time progress
3. **Progress Polling** (`GET /transcription-progress/`): Non-blocking status updates

**Enhanced Flow** (Large Files >100MB):
1. **File Upload** (`POST /upload-audio/`): Automatic progressive transcription initialization
2. **Chunking Progress** (`GET /chunking-progress/`): Unified progress tracking for chunking + transcription
3. **Real-time Updates**: Progressive transcript building as chunks complete

**Common Endpoints**:
4. **Insight Generation** (`POST /generate-insights/`): LLM-powered analysis
5. **Final Storage** (`POST /save-analysis/`): Persist complete workflow results
6. **Meeting Management** (`DELETE /meeting/<uuid>/delete/`): Complete deletion with file cleanup

**Enhanced Progress API** (`GET /chunking-progress/`):
- Detailed chunk-level status information
- Quality metrics with confidence scores
- Dynamic time estimation with phase breakdown
- Processing rate tracking and optimization

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

**Progressive Transcription System** (`core/progressive_transcription.py`):
- Real-time transcription of large files through chunking (>100MB files)
- Queue-based processing with up to 3 concurrent transcriptions
- Sequential chunk reassembly with overlap removal
- Status tracking: pending → processing → completed/failed per chunk

**Audio Chunking Engine** (`core/audio_chunking.py`):
- Automatic file segmentation based on size thresholds (default: 30-second chunks)
- VAD-aware chunking to preserve speech boundaries
- Format-aware duration estimation for different audio codecs
- Concurrent chunk creation with progress tracking

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

**Enhanced Progress Display**:
- **Chunk Status Grid**: Visual grid showing individual chunk states (pending/processing/completed/failed)
- **Quality Indicators**: Confidence scores with color-coded progress bars
- **Detailed Timing**: Phase-specific time estimates with processing rates
- **Real-time Updates**: Progressive transcript building as chunks complete

**Polling Architecture**:
- WebSocket-like polling with exponential backoff (every 2 seconds)
- Dual progress tracking: chunking progress + transcription progress
- Tab visibility detection to reduce server load
- Session state persistence across browser refreshes
- Background task cancellation support

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

### Test Audio Files

**Example Audio**: Use `example-audio/Commute-from-home.wav` for consistent testing across all audio processing features. This file is specifically referenced in CLAUDE.md instructions for standardized testing.

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

**Core Modules**:

**Utils Module** (`core/utils.py`):
- Centralized transcription logic with error handling
- LMStudio integration with health checks
- Memory management and performance monitoring
- Version-aware parameter selection

**Views Module** (`core/views.py`):
- API endpoints with standardized JSON responses
- Background task management via threading
- Enhanced progress tracking with detailed chunk information
- File upload handling with security validation
- Meeting deletion with file system cleanup

**Progressive Transcription** (`core/progressive_transcription.py`):
- `ProgressiveTranscriber` class for managing concurrent chunk processing
- Queue-based transcription with resource limits (max 3 concurrent)
- Sequential chunk reassembly with overlap removal
- Real-time transcript building and status updates

**Audio Processing** (`core/audio_chunking.py`):
- `AudioChunker` class for intelligent file segmentation
- VAD-aware chunking with configurable duration (default: 30 seconds)
- Format-aware duration estimation and validation
- Concurrent chunk creation with progress tracking

**Chunk Transcription** (`core/chunk_transcription.py`):
- `ChunkTranscriber` for individual chunk processing
- Whisper model integration with confidence scoring
- Error handling and retry mechanisms
- Overlap detection and removal algorithms

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

**Port Conflicts**: 
- **Problem**: Ports 8004-8005 often occupied by other services
- **Solution**: Use `./runserver.sh` which automatically finds available ports
- **Manual Check**: `lsof -i :8004` to see what's using a port
- **Default**: Development now uses port 8006 by default

**Development Server Setup**:
- **Problem**: Django requires `DEBUG=true` environment variable for development
- **Solution**: `.env.development` file automatically sets DEBUG=true
- **Quick Fix**: Run `./runserver.sh` instead of manual commands

**SSL Warnings**: urllib3 LibreSSL warnings are cosmetic and don't affect functionality

**Model Loading**: First-time model downloads may take several minutes; use preload commands for production deployment

**Memory Management**: Large models require >4GB RAM; system automatically monitors and cleans up when usage exceeds 85%

**CSRF Token Capitalization**: Django strictly requires `X-CSRFToken` header format; `X-Csrftoken` will fail with 403 Forbidden

**Wide Screen Implementation**: Only apply layout optimizations, avoid adding dashboard features unless specifically requested

**Progressive Transcription Display**:
- **Problem**: Users need real-time feedback on chunk-level transcription progress
- **Solution**: Enhanced sidebar with chunk status grid, quality indicators, and timing details
- **Components**: Chunk grid (16x16px colored squares), confidence score averaging, phase-specific time estimates
- **Visual States**: Pending (gray), Processing (animated yellow), Completed (green), Failed (red)

**Session Management**:
- **Problem**: Old transcripts persist across browser sessions causing confusion
- **Solution**: Smart session restoration with user confirmation dialogs
- **Features**: Time-based auto-restore (10 minutes), UI reset functionality, localStorage cleanup