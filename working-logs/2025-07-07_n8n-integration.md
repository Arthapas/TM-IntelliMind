# n8n Webhook Integration for External Transcription

**Date**: 2025-07-07
**Task**: Integrate n8n as an external transcription provider for the Create New Insight feature
**Status**: Completed

## Summary

Added n8n as an external API option for audio transcription. When users select n8n, the system sends audio files to a specified webhook URL (https://jaychu.app.n8n.cloud/webhook/b4dd13b9-3221-41af-b1bf-33f0f08ca062) and receives transcribed text back.

## Technical Changes

### 1. Model Updates (`core/models.py`)
- Added 'n8n' to `TRANSCRIPTION_PROVIDER_CHOICES` in Meeting model (line 27)

### 2. Frontend Updates (`core/templates/core/create_insight.html`)
- Added n8n option to API provider dropdown (line 83)
- Added n8n to `apiModels` configuration - no model selection needed (line 2077)
- Added n8n provider info with workflow integration details (lines 2095-2098)
- Modified provider selection handler to hide unnecessary fields for n8n (lines 2140-2143, 2161-2163)
- Updated validation to handle n8n without API key requirement (lines 2215-2217)
- Modified upload function to skip API key for n8n (lines 884-886, 891-894)

### 3. Backend Updates (`core/views.py`)
- Added `import requests` for webhook calls (line 14)
- Created `transcribe_with_n8n()` function (lines 437-483):
  - Sends audio file to n8n webhook
  - Handles timeout (5 minutes) and error cases
  - Extracts transcript from response (supports 'transcript', 'text' keys)
  - Updates progress during processing
- Modified `start_transcription` to check provider and route to n8n (lines 200-206)

### 4. Migration
- Created and applied migration for new provider choice

## Features Added

1. **No API Key Required**: n8n integration doesn't require API key input
2. **No Model Selection**: n8n handles transcription model selection internally
3. **Progress Tracking**: Real-time progress updates during n8n processing
4. **Error Handling**: Comprehensive error handling for webhook timeouts and failures
5. **Flexible Response Parsing**: Supports multiple response formats from n8n

## Usage

1. Select "External API" in transcription configuration
2. Choose "n8n Workflow" from the API provider dropdown
3. Upload audio file and click "Start Transcription"
4. System sends audio to n8n webhook and displays returned transcript

## Notes

- The n8n webhook URL is hardcoded in `transcribe_with_n8n()` function
- Response format expects JSON with 'transcript' or 'text' field
- 5-minute timeout configured for long audio files
- File is sent as multipart/form-data with 'audio' field name

## Next Steps

- Consider making webhook URL configurable via environment variable
- Add support for additional n8n response formats if needed
- Implement webhook authentication if required
- Add retry logic for failed webhook calls