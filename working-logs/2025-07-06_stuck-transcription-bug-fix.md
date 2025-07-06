# Stuck Transcription Bug Fix

**Date**: 2025-07-06
**Task**: Fix stuck progressive transcription that ran for 8+ hours
**Status**: Completed

## Problem Identified

Meeting `f787a78b-5834-49a0-918e-71be8eb819bb` had been stuck processing for 8 hours with:
- 22 chunks created (3 stuck in "processing", 19 "pending")
- Audio file: 7327 seconds (~2 hours) long, 146MB
- First 3 chunks (0, 1, 2) stuck in processing state for 7.4 hours
- Progressive transcription queue blocked with max 3 concurrent threads

## Root Causes

1. **Timeout Handling Issue**: `core/chunk_transcription.py:89`
   - `transcribe_audio_with_timeout` returned None on timeout but didn't properly update chunk status
   - Progressive transcriber's watchdog (5 min timeout) couldn't detect completed-but-failed threads
   - Chunks remained stuck in "processing" state indefinitely

2. **No Chunk Limit**: `core/audio_chunking.py`
   - 2-hour audio file would create ~293 chunks (30s chunks with 5s overlap)
   - No safety limit on maximum chunks, risking system overload

## Solutions Implemented

### 1. Fixed Timeout Handling (`core/chunk_transcription.py`)
- Changed `transcribe_audio_with_timeout` to return tuple: `(success, text, timed_out)`
- Updated `transcribe_chunk` to properly handle timeout cases
- Ensures chunk status is set to "failed" with appropriate error message on timeout

### 2. Improved Watchdog (`core/progressive_transcription.py`)
- Reduced watchdog interval from 30s to 15s for faster detection
- Adjusted thread timeout to 240s (4 minutes) to be > chunk timeout (180s)
- Added debug logging for watchdog checks

### 3. Added Chunk Limits (`core/audio_chunking.py`)
- Added `max_chunks` setting (default: 100) to prevent excessive chunking
- Applied limit to both VAD-aware and time-based chunking methods
- Added warning logs when chunk limit is reached

## Files Modified

1. `core/chunk_transcription.py`:19-59, 89-104
2. `core/progressive_transcription.py`:64-67, 194-202
3. `core/audio_chunking.py`:44, 260-276, 211-215

## Testing & Validation

- Deleted stuck meeting and its 22 chunks successfully
- System now prevents runaway chunk creation
- Improved timeout detection prevents indefinite stuck states
- Chunk limit provides safety against extremely long audio files

## Next Steps

- Monitor future large file uploads for proper chunk processing
- Consider implementing progress estimation for very long files
- Add admin interface for monitoring stuck transcriptions
- Consider implementing distributed processing for files >100 chunks