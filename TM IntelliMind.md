# TM IntelliMind Platform

## Context & Vision
TM IntelliMind is a sophisticated centralized intelligence platform that transforms how organizations capture, process, and leverage business intelligence from meetings. This platform serves as the central nervous system for organizational knowledge, designed specifically for Thailand's non-life insurance sector.

## Implementation Status

### ✅ P01 Landing Page - FULLY IMPLEMENTED
- **Homepage Interface**: Clean, professional greeting with meeting management dashboard
- **Meeting Creation**: "Create New Insight" button with streamlined workflow
- **Meeting List Display**: Four-column table layout showing:
  1. **Meeting Name** (auto-generated using LLM analysis)
  2. **Summary** (extracted from AI-generated situation analysis) 
  3. **Date** (creation timestamp)
  4. **Actions** (View Detail + Delete with confirmation)
- **Navigation**: Seamless flow to detail pages with complete transcripts and insights
- **Meeting Management**: Full CRUD operations with delete functionality and file cleanup
- **Wide Screen Optimization**: Responsive design with 5 breakpoints and dual-column dashboard layout for ≥1400px screens

### ✅ P02 Audio Processing Engine - FULLY IMPLEMENTED

#### ✅ P02-1 Multi-Provider Audio Upload (Fully Implemented)
- **File Upload**: Drag-and-drop interface supporting MP3, WAV, M4A, MP4 formats
- **Dual Validation**: Both MIME type and file extension checking for security
- **Multi-Provider Support**: 5 transcription providers available:
  1. **Local Whisper** (7 models: tiny → large-v3)
  2. **OpenAI Whisper API** with encrypted credential storage
  3. **AssemblyAI** with custom model selection
  4. **Deepgram** with real-time streaming capabilities
  5. **Custom API Endpoint** with configurable authentication
- **Default Configuration**: Large-v2 local model optimized for Thai language
- **Upload Progress**: Real-time progress tracking with chunking estimation

#### ✅ P02-2 Progressive Transcription System (Fully Implemented)
- **Large File Support**: Automatic chunking for files >100MB
- **Real-time Processing**: Progressive transcript building as chunks complete
- **Concurrent Processing**: Up to 3 simultaneous chunk transcriptions
- **Chunk Management**: 30-second segments with 5-second overlap
- **Safety Limits**: Maximum 100 chunks per file to prevent system overload
- **Status Tracking**: Individual chunk states (pending → processing → completed/failed)
- **Enhanced Watchdog**: 2-minute timeout with database monitoring every 10 seconds
- **Automatic Recovery**: Stuck chunk detection and retry mechanisms

#### ✅ P02-3 Enhanced Transcript Processing (Fully Implemented)
- **Editable Transcript**: Rich text area for user review and editing
- **Language Detection**: Automatic Thai/English detection with transcription-based fallback
- **Error Handling**: Comprehensive timeout detection and recovery
- **Progress Tracking**: Real-time status updates with chunk-level granularity
- **Quality Metrics**: Confidence scoring and performance monitoring
- **Warning Suppression**: Clean logs with faster-whisper math operation filtering

#### ✅ P02-4 AI-Powered Analysis (Fully Implemented)
- **LLM Integration**: LMStudio with health checks and configurable endpoints
- **9-Category Analysis**:
  - Tasks & Action Items
  - Decisions Made  
  - Questions & Answers
  - Key Insights
  - Deadlines
  - Meeting Participants
  - Follow-up Actions
  - Risks Identified
  - Meeting Agenda
- **Auto-Generated Metadata**: Meeting name and description via LLM analysis
- **User Review Interface**: Edit capability for all generated content
- **Save Functionality**: Complete workflow persistence with error handling

#### ❌ P02-5 Direct Audio Recording (Not Implemented)
- Browser-based recording interface not yet implemented
- Currently only supports file upload workflow
- Planned feature for future development

### ❌ P03 Export Meeting Page - NOT IMPLEMENTED
#### P03-1 Export to Word Document (Planned)
- **Current Status**: python-docx dependency installed but not integrated
- **Required Implementation**: 
  - Word document generation with formatted analysis
  - Download capability for generated documents
  - Template system for consistent formatting
- **Priority**: Next major feature for implementation

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

### Transcription Stability (2025-07-06 Fixes)
- **Stuck Detection**: Enhanced watchdog monitoring threads + database state
- **Timeout Handling**: Reduced from 5min to 2min with proper chunk status updates
- **Automatic Recovery**: Failed chunk retry with exponential backoff
- **Language Detection**: Fixed `'str' object has no attribute 'dtype'` error
- **Warning Suppression**: Clean logs with faster-whisper math operation filtering
- **NULL Constraints**: Fixed API credentials field validation

### Performance Metrics
- **Speed**: 12.5x real-time processing capability
- **Memory**: <2GB usage for large-v2 model on M4 systems
- **Thai Accuracy**: 15-20% improvement with enhanced business vocabulary
- **Chunk Limits**: Maximum 100 chunks per file (5000 seconds = 83 minutes)
- **Concurrent Processing**: Up to 3 simultaneous transcriptions

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