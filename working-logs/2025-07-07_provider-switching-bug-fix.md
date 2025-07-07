# Provider Switching Bug Fix

**Date**: 2025-07-07
**Task**: Fix bug where switching transcription providers during re-transcription didn't work
**Status**: Completed

## Problem Description

Users reported that when they:
1. Start with n8n workflow for transcription
2. Switch to local model in the UI
3. Click re-transcribe
4. System still uses n8n instead of the selected local model

## Root Cause Analysis

The issue was in the `start_transcription` view (lines 210-217 in `core/views.py`):

1. **Frontend Issue**: The start transcription button only sent `meeting_id`, `whisper_model`, and `language` to the backend, but not the current provider selection
2. **Backend Issue**: The `start_transcription` view used `meeting.transcription_provider` (stored when file was uploaded) instead of checking the current UI selection

## Technical Changes

### 1. Frontend Fix (`core/templates/core/create_insight.html`)

**Lines 1036-1064**: Updated start transcription event handler to send current provider selection:

```javascript
// Get current provider selection
const provider = document.querySelector('input[name="transcription_provider"]:checked').value;
const apiProvider = document.getElementById('api-provider').value;

// Send in request body
body: JSON.stringify({
    meeting_id: currentMeetingId,
    whisper_model: model,
    language: language !== 'auto' ? language : null,
    transcription_provider: provider,        // Added
    api_provider: apiProvider || null        // Added
})
```

### 2. Backend Fix (`core/views.py`)

**Lines 197-217**: Updated `start_transcription` view to use current selection:

```python
# Get current provider selection from request
current_provider = data.get('transcription_provider', 'local')
current_api_provider = data.get('api_provider', None)

# Update meeting record for consistency
if current_provider == 'api' and current_api_provider:
    meeting.transcription_provider = current_api_provider  # n8n, openai, etc.
else:
    meeting.transcription_provider = current_provider  # local
meeting.save()

# Use current provider selection instead of stored meeting provider
if current_provider == 'api' and current_api_provider == 'n8n':
    text = transcribe_with_n8n(audio_path, transcript)
else:
    text = transcribe_audio(audio_path, whisper_model, transcript, language)
```

## Features Added

1. **Dynamic Provider Selection**: Re-transcription now uses the currently selected provider, not the stored one
2. **Meeting Record Updates**: Meeting record is updated with the new provider when re-transcribing
3. **Backward Compatibility**: Original upload flow remains unchanged

## Testing Scenarios

The fix enables these workflows:
1. Upload with n8n → Switch to local → Re-transcribe with local ✅
2. Upload with local → Switch to n8n → Re-transcribe with n8n ✅  
3. Upload with n8n → Re-transcribe with n8n (no change) ✅
4. Upload with local → Re-transcribe with local (no change) ✅

## Impact

- **User Experience**: Provider switching now works as expected during re-transcription
- **Data Consistency**: Meeting records reflect the actual provider used for transcription
- **Debugging**: Easier to trace which provider was used for each transcription

## Notes

- The fix maintains backward compatibility with existing workflows
- No database migration required
- Changes affect both initial transcription and re-transcription flows