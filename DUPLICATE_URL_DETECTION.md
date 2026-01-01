# Duplicate URL Detection Feature

## Overview
Detects when a URL has already been indexed in a topic and immediately notifies the user with the cached summary, skipping redundant agent processing and indexing.

## Implementation Summary

### 1. Files Created
- **`core/url_utils.py`** - URL normalization utilities
- **`scripts/migrate_indexed_urls.py`** - Migration script (already executed)
- **`test_url_deduplication.py`** - Test suite

### 2. Files Modified
- **`core/database.py`** - Added `indexed_urls` table and 3 new methods
- **`telegram_bot.py`** - Added early duplicate detection in message handler
- **`indexing_worker.py`** - Added duplicate check before indexing

### 3. Database Schema
```sql
CREATE TABLE indexed_urls (
    url TEXT NOT NULL,              -- Normalized URL
    original_url TEXT NOT NULL,     -- User's original URL
    topic_name TEXT NOT NULL,       -- Topic isolation
    first_indexed_at TEXT NOT NULL, -- When first indexed
    first_message_id INTEGER NOT NULL,
    last_seen_at TEXT,              -- Last time shared
    times_shared INTEGER DEFAULT 1, -- Share counter
    PRIMARY KEY (url, topic_name)
);
```

## Features

### URL Normalization
Automatically normalizes URLs to detect duplicates:
- ✅ `http://` → `https://`
- ✅ Lowercase domains: `Example.COM` → `example.com`
- ✅ Remove trailing slashes: `/path/` → `/path`
- ✅ Remove tracking parameters: `?utm_source=twitter&ref=123`
- ✅ Sort query parameters: `?b=2&a=1` → `?a=1&b=2`

**Tracking parameters removed:**
- utm_* (Google Analytics)
- fbclid, gclid, msclkid (Ad platforms)
- ref, referrer, source
- _ga, _gl (Google Analytics)
- mc_cid, mc_eid (Mailchimp)
- pk_campaign, pk_kwd (Piwik)

### User Experience
When a duplicate URL is detected:
```
✅ Already Indexed!

📎 This link is already in the Health knowledge base.

📝 Summary:
[LLM-generated summary from cache]

📅 First indexed: 2025-12-29
🔄 Shared 3 times in this topic
```

### Topic Isolation
- Same URL can be indexed in **different topics** independently
- Duplicate detection is **per-topic** only
- Example: Health article can exist in both "Health" and "AI Engineering" topics

### Performance Optimization
- **Early detection**: Checks before agent processing (saves API calls)
- **Fast lookup**: O(1) database query on indexed (url, topic_name)
- **Cache reuse**: Shows cached summary (no LightRAG query needed)
- **No redundant indexing**: Background worker skips duplicates

## Workflow

### 1. User Sends Duplicate URL
```
User → Telegram Bot
         ↓
Extract URL & normalize
         ↓
Check indexed_urls table
         ↓
If found:
  ├─ Increment share count
  ├─ Send notification with summary
  └─ RETURN (skip agent)
```

### 2. Background Worker
```
Pending URLs (every 10s)
         ↓
Check indexed_urls table
         ↓
If duplicate:
  ├─ Mark message as indexed (indexed_by="duplicate")
  └─ Skip LightRAG indexing
If new:
  ├─ Index to LightRAG
  └─ Add to indexed_urls table
```

## Migration

Migration already executed successfully:
```
✓ Total URLs tracked: 7
✓ Topics with indexed URLs: 1
✓ New entries: 7
✓ Skipped (duplicates): 1
```

All existing indexed URLs have been backfilled into the `indexed_urls` table.

## Testing

Run tests:
```bash
uv run python test_url_deduplication.py
```

All tests passing:
- ✅ URL normalization (7/7 tests)
- ✅ Database duplicate detection
- ✅ Share count incrementing
- ✅ Topic isolation

## Code Statistics
- **Total changes**: ~150 lines of code
- **New files**: 3
- **Modified files**: 3
- **Database tables**: +1 (`indexed_urls`)
- **New methods**: 3 (`check_url_indexed`, `mark_url_indexed`, `increment_url_share_count`)

## Configuration
No configuration required - feature is automatically enabled.

## Edge Cases Handled
- ✅ Same URL with different tracking params
- ✅ HTTP vs HTTPS versions
- ✅ Trailing slash variations
- ✅ Case-insensitive domain matching
- ✅ URL shared before indexing completes (background worker detects)
- ✅ Same URL in different topics (both indexed)
- ✅ Query parameter ordering differences

## Future Enhancements (Optional)
- [ ] Add "re-index" button for outdated content
- [ ] Track content hash to detect updated articles
- [ ] Add user preference to disable duplicate detection
- [ ] Show "last updated" timestamp in notification
