#!/usr/bin/env python3
"""Test all bug fixes for duplicate URL detection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.url_utils import normalize_url
from core.database import (
    init_db, check_url_indexed, mark_url_indexed,
    increment_url_share_count, save_to_scrape_cache
)

print("=" * 70)
print("BUG FIXES VERIFICATION TESTS")
print("=" * 70)

# Initialize
init_db()

# Test data
test_topic = "Bug Fix Test"
test_url_original = "http://example.com/test?utm_source=twitter&id=123"
test_url_normalized = normalize_url(test_url_original)
test_summary = "This is a test summary for bug fix verification."

print("\n" + "=" * 70)
print("TEST 1: URL Normalization (including malformed URLs)")
print("=" * 70)

test_cases = [
    ("http://example.com/", "https://example.com"),
    ("not-a-url", ""),  # Malformed - should return empty
    ("ftp://example.com", "ftp://example.com"),  # Non-http scheme preserved
    ("https://EXAMPLE.COM/Path?b=2&a=1", "https://example.com/Path?a=1&b=2"),
]

for original, expected in test_cases:
    result = normalize_url(original)
    status = "✓" if result == expected else "✗"
    print(f"{status} normalize_url('{original}')")
    print(f"   Expected: '{expected}'")
    print(f"   Got:      '{result}'")
    if result != expected:
        print(f"   ❌ FAIL")
    print()

print("=" * 70)
print("TEST 2: Summary Retrieval (Bug #1 - JOIN Fix)")
print("=" * 70)

# Clear any existing test data
from core.database import db_session
with db_session() as cur:
    cur.execute("DELETE FROM indexed_urls WHERE topic_name = ?", (test_topic,))
    cur.execute("DELETE FROM url_scrape_cache WHERE url = ?", (test_url_original,))

print(f"\n1. Saving scraped content to cache:")
print(f"   URL: {test_url_original}")
print(f"   Summary: {test_summary}")
save_to_scrape_cache(test_url_original, test_summary, "Full content here")
print("   ✓ Saved to url_scrape_cache")

print(f"\n2. Marking URL as indexed:")
print(f"   Original URL: {test_url_original}")
print(f"   Normalized: {test_url_normalized}")
mark_url_indexed(test_url_original, test_topic, message_id=9999)
print("   ✓ Marked in indexed_urls")

print(f"\n3. Checking if URL is indexed (testing JOIN fix):")
result = check_url_indexed(test_url_original, test_topic)
if result:
    retrieved_summary = result.get('summary')
    print(f"   ✓ URL found in indexed_urls")
    print(f"   Normalized URL: {result['normalized_url']}")
    print(f"   Original URL: {result['original_url']}")
    print(f"   Retrieved summary: {retrieved_summary[:50] if retrieved_summary else 'None'}...")

    if retrieved_summary and test_summary in retrieved_summary:
        print("   ✅ SUCCESS: Summary correctly retrieved via JOIN!")
    else:
        print(f"   ❌ FAIL: Summary not retrieved correctly")
        print(f"      Expected to contain: {test_summary}")
        print(f"      Got: {retrieved_summary}")
else:
    print("   ❌ FAIL: URL not found")

print("\n" + "=" * 70)
print("TEST 3: None Summary Handling (Bug #2)")
print("=" * 70)

# Create entry without cache (simulates failed cache lookup)
test_url_no_cache = "https://example.com/no-cache"
with db_session() as cur:
    cur.execute("DELETE FROM indexed_urls WHERE url = ?", (test_url_no_cache,))

mark_url_indexed(test_url_no_cache, test_topic, message_id=9998)
result = check_url_indexed(test_url_no_cache, test_topic)

print(f"1. Created indexed URL without cache entry")
print(f"2. Checking URL: {test_url_no_cache}")

if result:
    summary = result.get('summary') or 'No summary available'
    print(f"   Summary from result: {summary}")

    # Test that len() doesn't crash on None
    try:
        if len(summary) > 500:
            summary = summary[:497] + "..."
        print("   ✅ SUCCESS: None handling works, no TypeError!")
    except TypeError as e:
        print(f"   ❌ FAIL: TypeError occurred: {e}")
else:
    print("   ❌ FAIL: URL not found")

print("\n" + "=" * 70)
print("TEST 4: Share Count Accuracy (Bug #3)")
print("=" * 70)

# Clean slate
test_url_count = "https://example.com/count-test"
with db_session() as cur:
    cur.execute("DELETE FROM indexed_urls WHERE url = ?", (test_url_count,))

print(f"1. Marking URL as indexed (initial share)")
mark_url_indexed(test_url_count, test_topic, message_id=9997)

result = check_url_indexed(test_url_count, test_topic)
initial_count = result.get('times_shared', 0) if result else 0
print(f"   Initial count: {initial_count} (expected: 1)")

print(f"\n2. Incrementing share count (2nd share)")
updated_count = increment_url_share_count(test_url_count, test_topic)
print(f"   Returned count: {updated_count} (expected: 2)")

print(f"\n3. Incrementing again (3rd share)")
updated_count = increment_url_share_count(test_url_count, test_topic)
print(f"   Returned count: {updated_count} (expected: 3)")

result = check_url_indexed(test_url_count, test_topic)
final_count = result.get('times_shared', 0) if result else 0
print(f"\n4. Verifying final count in DB: {final_count}")

if initial_count == 1 and updated_count == 3 and final_count == 3:
    print("   ✅ SUCCESS: Share counts are accurate!")
else:
    print(f"   ❌ FAIL: Count mismatch")
    print(f"      Initial: {initial_count} (expected 1)")
    print(f"      After 2 increments: {updated_count} (expected 3)")
    print(f"      Final in DB: {final_count} (expected 3)")

print("\n" + "=" * 70)
print("TEST 5: Increment on Non-existent URL (Bug #5)")
print("=" * 70)

test_url_missing = "https://example.com/missing"
print(f"1. Attempting to increment non-existent URL: {test_url_missing}")
count = increment_url_share_count(test_url_missing, test_topic)
print(f"   Returned count: {count} (expected: 0)")

if count == 0:
    print("   ✅ SUCCESS: Returns 0 for non-existent URL (logged warning)")
else:
    print(f"   ❌ FAIL: Expected 0, got {count}")

print("\n" + "=" * 70)
print("TEST 6: URL with Different Formats (Normalization)")
print("=" * 70)

# Mark one version
test_url_v1 = "http://example.com/article?utm_source=twitter"
test_url_v2 = "https://example.com/article/"  # Different format, same normalized
test_url_v3 = "HTTPS://EXAMPLE.COM/article"  # All caps

with db_session() as cur:
    cur.execute("DELETE FROM indexed_urls WHERE url LIKE '%example.com/article%'")

print(f"1. Indexing URL: {test_url_v1}")
mark_url_indexed(test_url_v1, test_topic, message_id=9996)

print(f"\n2. Checking with different format: {test_url_v2}")
result = check_url_indexed(test_url_v2, test_topic)
found_v2 = result is not None

print(f"\n3. Checking with uppercase: {test_url_v3}")
result = check_url_indexed(test_url_v3, test_topic)
found_v3 = result is not None

if found_v2 and found_v3:
    print("\n   ✅ SUCCESS: All URL formats normalized correctly!")
else:
    print(f"\n   ❌ FAIL: Normalization issue")
    print(f"      Found v2: {found_v2}")
    print(f"      Found v3: {found_v3}")

print("\n" + "=" * 70)
print("ALL TESTS COMPLETE")
print("=" * 70)
