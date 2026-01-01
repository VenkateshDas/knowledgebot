#!/usr/bin/env python3
"""Test URL deduplication and normalization functionality."""

from core.url_utils import normalize_url
from core.database import check_url_indexed, mark_url_indexed, increment_url_share_count, init_db

print("=" * 70)
print("URL Normalization Tests")
print("=" * 70)

# Test cases for URL normalization
test_urls = [
    ("http://example.com/", "https://example.com"),
    ("https://example.com", "https://example.com"),
    ("https://Example.COM/path/", "https://example.com/path"),
    ("https://example.com?utm_source=twitter&id=123", "https://example.com?id=123"),
    ("https://example.com/?ref=homepage", "https://example.com"),
    ("https://example.com/path?fbclid=123&gclid=456", "https://example.com/path"),
    ("https://example.com/path?b=2&a=1", "https://example.com/path?a=1&b=2"),
]

print("\nTesting URL normalization:")
for original, expected in test_urls:
    result = normalize_url(original)
    status = "✓" if result == expected else "✗"
    print(f"{status} {original}")
    print(f"  → {result}")
    if result != expected:
        print(f"  Expected: {expected}")
    print()

print("=" * 70)
print("Database Deduplication Tests")
print("=" * 70)

# Initialize database
init_db()

# Test duplicate detection
test_topic = "Test Topic"
test_url1 = "https://example.com/article?utm_source=twitter"
test_url2 = "http://example.com/article/"  # Should normalize to same as url1

print("\n1. Checking if URL is indexed (should be None):")
result = check_url_indexed(test_url1, test_topic)
print(f"   Result: {result}")

print("\n2. Marking URL as indexed:")
mark_url_indexed(test_url1, test_topic, message_id=999)
print("   ✓ Marked")

print("\n3. Checking again (should find it):")
result = check_url_indexed(test_url1, test_topic)
if result:
    print(f"   ✓ Found: {result['normalized_url']}")
    print(f"   Times shared: {result['times_shared']}")
else:
    print("   ✗ Not found")

print("\n4. Checking with different format (should still find it due to normalization):")
result = check_url_indexed(test_url2, test_topic)
if result:
    print(f"   ✓ Found: {result['normalized_url']}")
    print(f"   Original URL: {result['original_url']}")
else:
    print("   ✗ Not found")

print("\n5. Incrementing share count:")
increment_url_share_count(test_url1, test_topic)
print("   ✓ Incremented")

print("\n6. Checking share count:")
result = check_url_indexed(test_url1, test_topic)
if result:
    print(f"   Times shared: {result['times_shared']} (should be 2)")
else:
    print("   ✗ Not found")

print("\n7. Checking in different topic (should be None):")
result = check_url_indexed(test_url1, "Different Topic")
print(f"   Result: {result}")

print("\n" + "=" * 70)
print("All tests completed!")
print("=" * 70)
