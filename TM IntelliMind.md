# TM IntelliMind Platform

## Context & Vision
TM IntelliMind is a sophisticated centralized intelligence platform that transforms how organizations capture, process, and leverage business intelligence from meetings. This platform serves as the central nervous system for organizational knowledge, designed specifically for Thailand's non-life insurance sector.

## Implementation Status

### ✅ P01 Landing Page - FULLY IMPLEMENTED
- **P01-1 Homepage Interface**: Clean, professional greeting with meeting management dashboard `core/templates/core/home.html`
- **P01-2 Meeting Creation**: "Create New Insight" button with streamlined workflow `core/views.py:create_insight`
- **P01-3 Meeting List Display**: Four-column table layout:
  1. **Meeting Name** (auto-generated using LLM analysis) `core/models.py:Meeting.title`
  2. **Summary** (extracted from AI-generated situation analysis) `core/models.py:Insight.situation`
  3. **Date** (creation timestamp) `core/models.py:Meeting.created_at`
  4. **Actions** (View Detail + Delete with confirmation) `core/views.py:delete_meeting`
- **P01-4 Navigation**: Seamless flow to detail pages with complete transcripts and insights `core/urls.py`
- **P01-5 Meeting Management**: Full CRUD operations with delete functionality and file cleanup `core/views.py:delete_meeting`
- **P01-6 Wide Screen Optimization**: Responsive design with 5 breakpoints and dual-column dashboard layout ≥1400px `static/css/wide-screen.css`

### ✅ P02 Audio Processing Engine - FULLY IMPLEMENTED

#### ✅ P02-1 Multi-Provider Audio Upload (Fully Implemented)
- **P02-1-1 File Upload**: Drag-and-drop interface supporting MP3, WAV, M4A, MP4 formats `core/templates/core/create_insight.html:upload-area`
- **P02-1-2 Dual Validation**: Both MIME type and file extension checking for security `core/views.py:upload_audio`
- **P02-1-3 Multi-Provider Support**: 5 transcription providers available:
  1. **Local Whisper** (7 models: tiny → large-v3) `core/utils.py:transcribe_audio`
  2. **OpenAI Whisper API** with encrypted credential storage `core/openai_transcriber.py`
  3. **AssemblyAI** with custom model selection `core/assemblyai_transcriber.py`
  4. **Deepgram** with real-time streaming capabilities `core/deepgram_transcriber.py`
  5. **Custom API Endpoint** with configurable authentication `core/custom_transcriber.py`
- **P02-1-4 Default Configuration**: Large-v2 local model optimized for Thai language `core/models.py:Meeting.transcription_model`
- **P02-1-5 Upload Progress**: Real-time progress tracking with chunking estimation `core/views.py:upload_audio`

#### ✅ P02-2 Progressive Transcription System (Fully Implemented)
- **P02-2-1 Large File Support**: Automatic chunking for files >100MB `core/audio_chunking.py:should_chunk_file`
- **P02-2-2 Real-time Processing**: Progressive transcript building as chunks complete `core/progressive_transcription.py:_update_progressive_transcript`
- **P02-2-3 Concurrent Processing**: Up to 2 simultaneous chunk transcriptions `core/progressive_transcription.py:35`
- **P02-2-4 Chunk Management**: 30-second segments with 5-second overlap `core/audio_chunking.py:40-41`
- **P02-2-5 Safety Limits**: Maximum 150 chunks per file to prevent system overload `core/audio_chunking.py:44`
- **P02-2-6 Status Tracking**: Individual chunk states (pending → processing → completed/failed) `core/models.py:AudioChunk.status`
- **P02-2-7 Enhanced Watchdog**: 100s timeout with database monitoring every 5 seconds `core/progressive_transcription.py:68-71`
- **P02-2-8 Automatic Recovery**: Stuck chunk detection and retry mechanisms `core/progressive_transcription.py:_check_stuck_threads`

#### ✅ P02-3 Enhanced Transcript Processing (Fully Implemented)
- **P02-3-1 Editable Transcript**: Rich text area for user review and editing `core/templates/core/create_insight.html:transcript-text`
- **P02-3-2 Language Detection**: Automatic Thai/English detection with transcription-based fallback `core/utils.py:transcribe_audio`
- **P02-3-3 Error Handling**: Comprehensive timeout detection and recovery `core/chunk_transcription.py:transcribe_audio_with_timeout`
- **P02-3-4 Progress Tracking**: Real-time status updates with chunk-level granularity `core/views.py:chunking_progress`
- **P02-3-5 Quality Metrics**: Confidence scoring and performance monitoring `core/progressive_transcription.py:309-318`
- **P02-3-6 Warning Suppression**: Clean logs with faster-whisper math operation filtering `core/utils.py:warnings.filterwarnings`

#### ✅ P02-4 AI-Powered Analysis (Fully Implemented)
- **P02-4-1 LLM Integration**: LMStudio with health checks and configurable endpoints `core/utils.py:call_llm_api`
- **P02-4-2 9-Category Analysis**: `core/templates/core/create_insight.html:analysis-sections`
  - Tasks & Action Items
  - Decisions Made  
  - Questions & Answers
  - Key Insights
  - Deadlines
  - Meeting Participants
  - Follow-up Actions
  - Risks Identified
  - Meeting Agenda
- **P02-4-3 Auto-Generated Metadata**: Meeting name and description via LLM analysis `core/utils.py:generate_meeting_metadata`
- **P02-4-4 User Review Interface**: Edit capability for all generated content `core/templates/core/create_insight.html:editable-fields`
- **P02-4-5 Save Functionality**: Complete workflow persistence with error handling `core/views.py:save_analysis`

#### ❌ P02-5 Direct Audio Recording (Not Implemented)
- **P02-5-1 Recording Interface**: Browser-based recording interface not yet implemented
- **P02-5-2 Current Status**: Only supports file upload workflow
- **P02-5-3 Planned**: WebRTC integration for future development

### ❌ P03 Export Meeting Page - NOT IMPLEMENTED
#### P03-1 Export to Word Document (Planned)
- **P03-1-1 Current Status**: python-docx dependency installed but not integrated `requirements.txt:python-docx`
- **P03-1-2 Document Generation**: Word document generation with formatted analysis (planned)
- **P03-1-3 Download Capability**: Download capability for generated documents (planned)
- **P03-1-4 Template System**: Consistent formatting templates (planned)
- **P03-1-5 Priority**: Next major feature for implementation

## Enhanced Technical Stack

### Backend Architecture
- **Framework**: Python Django 4.2.23 with production-ready configuration
- **Database**: 
  - **Development**: SQLite3 for rapid development
  - **Production**: PostgreSQL with environment-based credentials
- **Models**: Meeting, AudioChunk, Transcript, Insight with UUID primary keys
- **Security**: Environment variable configuration, CSRF protection, production headers
- **Admin Interface**: Fully configured Django admin for all data models

### Audio Processing Engine
- **Core Library**: faster-whisper 1.1.1 with BatchedInferencePipeline
- **Performance**: 12.5x real-time processing (1 minute audio in ~5 seconds)
- **Optimization**: Apple Silicon M4 specific optimizations with unified memory
- **Progressive System**: `core/progressive_transcription.py` with queue-based processing
- **Chunking Engine**: `core/audio_chunking.py` with VAD-aware segmentation
- **External APIs**: `core/external_transcribers.py` supporting 4 cloud providers
- **Language Support**: Enhanced Thai processing with 32+ business terms
- **Advanced Features**: 21 processing parameters with word timestamps and confidence

### LLM Integration
- **Service**: LMStudio with configurable endpoints (default: http://localhost:1234/v1)
- **Health Monitoring**: Automatic service availability checking
- **Error Handling**: Comprehensive fallback mechanisms and timeout management
- **Analysis Engine**: Structured insight generation with business context optimization

### Frontend Technology
- **Framework**: Bootstrap 5.1.3 with vanilla JavaScript
- **Responsive Design**: Custom wide-screen CSS with 5 breakpoints (1200px → 1920px+)
- **Progress System**: Real-time chunk status grid with color-coded states
- **Error Prevention**: JSON parsing boundaries, DOM element null checking
- **Memory Management**: Automatic cleanup of timeouts and intervals
- **AJAX Operations**: Proper CSRF token handling (`X-CSRFToken` header format)

## System Reliability & Performance

### Transcription Stability (2025-07-07 Fixes)
- **Stuck Detection**: Enhanced watchdog monitoring threads + database state `core/progressive_transcription.py:_check_stuck_threads`
- **Timeout Handling**: Reduced from 180s to 90s chunk timeout with proper status updates `core/chunk_transcription.py:90`
- **Automatic Recovery**: Failed chunk retry with faster detection `core/progressive_transcription.py:252-283`
- **Language Detection**: Fixed `'str' object has no attribute 'dtype'` error `core/utils.py:transcribe_audio`
- **Warning Suppression**: Clean logs with faster-whisper math operation filtering `core/utils.py:warnings.filterwarnings`
- **Performance Optimization**: Reduced concurrency 3→2 threads, enhanced monitoring `core/progressive_transcription.py:35,309-318`

### Performance Metrics
- **Speed**: 12.5x real-time processing capability
- **Memory**: <2GB usage for large-v2 model on M4 systems
- **Thai Accuracy**: 15-20% improvement with enhanced business vocabulary
- **Chunk Limits**: Maximum 150 chunks per file (7500 seconds = 2.08 hours)
- **Concurrent Processing**: Up to 2 simultaneous transcriptions (optimized)

## Security & Production Readiness

### Security Features
- **Multi-Provider Auth**: Encrypted credential storage for external APIs
- **File Validation**: Dual MIME type and extension checking
- **CSRF Protection**: Exact header format validation (`X-CSRFToken`)
- **Input Sanitization**: Path traversal prevention and filename sanitization
- **Data Deletion**: Complete file system cleanup with CASCADE relationships
- **Error Boundaries**: Graceful fallbacks for all external dependencies

### Monitoring & Troubleshooting
- **System Logging**: File-based logging to `logs/django.log`
- **Chunk Recovery**: Django shell commands for debugging stuck transcriptions
- **Health Checks**: Automatic validation of external service availability
- **Working Logs**: Development continuity documentation in `working-logs/`

## Development Commands

### Daily Operations
```bash
# Start development server (auto-port detection)
./runserver.sh

# Manual server start
python3 manage.py runserver 8006

# Model pre-loading for production
python3 manage.py preload_whisper_models --models medium large-v2 --validate

# System health validation
python3 manage.py check
```

### Troubleshooting
```bash
# Check stuck transcriptions
python3 manage.py shell -c "
from core.models import AudioChunk
stuck = AudioChunk.objects.filter(status='processing')
print(f'Stuck chunks: {stuck.count()}')
"

# Reset stuck chunks
python3 manage.py shell -c "
from core.models import AudioChunk
AudioChunk.objects.filter(status='processing').update(status='pending')
"

# Re-queue pending chunks
python3 manage.py shell -c "
from core.progressive_transcription import add_chunk_to_transcription_queue
from core.models import AudioChunk
for chunk in AudioChunk.objects.filter(status='pending'):
    add_chunk_to_transcription_queue(chunk)
"
```

## Currency & Localization
All financial components use Thai Baht (฿) as the default currency, reflecting the platform's focus on Thailand's non-life insurance sector.

## Recent Enhancements (July 2025)

### ✅ Transcription System Reliability
1. **Progressive Transcription**: Large file chunking with real-time assembly
2. **Enhanced Watchdog**: Database + thread monitoring with 2-minute timeouts
3. **Automatic Recovery**: Stuck chunk detection and retry mechanisms
4. **Multi-Provider Support**: 5 transcription services with encrypted credentials
5. **Language Detection Fix**: Transcription-based detection replacing direct API calls
6. **Warning Suppression**: Clean logs with math operation filtering

### ✅ User Interface Improvements
1. **Wide Screen Optimization**: 5 breakpoints with dual-column dashboard
2. **Chunk Progress Grid**: Visual status tracking with color-coded states
3. **Meeting Management**: Complete CRUD with file cleanup and confirmations
4. **Responsive Design**: Progressive enhancement for large displays

### ✅ Development Infrastructure
1. **Working Logs System**: Continuity documentation in `working-logs/`
2. **Enhanced Error Handling**: NULL constraint fixes and timeout detection
3. **Troubleshooting Tools**: Django shell commands for maintenance
4. **Server Startup Script**: Automatic port detection and health checks

## Roadmap & Next Steps

### Immediate Priority
1. **P03 Word Export**: Implement document generation using existing python-docx dependency
2. **Direct Recording**: Browser-based audio capture with WebRTC integration

### Future Enhancements
- Real-time collaboration features
- Advanced analytics dashboard
- Multi-language support expansion
- API endpoints for third-party integrations

---

*This document reflects the current implementation status as of July 7, 2025, incorporating progressive transcription with chunking system, multi-provider audio processing, enhanced watchdog reliability, and comprehensive troubleshooting infrastructure.*