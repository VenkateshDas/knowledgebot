#!/usr/bin/env python3
"""
Test script for Parallel AI web search integration.

Usage:
    python test_parallel_search.py
"""

import os
from dotenv import load_dotenv
from tools.common_tools import web_search

# Load environment variables
load_dotenv()

def test_web_search():
    """Test the new Parallel AI web search implementation."""

    # Check if API key is configured
    api_key = os.getenv("PARALLEL_API_KEY", "").strip()
    if not api_key:
        print("❌ ERROR: PARALLEL_API_KEY not found in .env file")
        print("\nPlease add to your .env file:")
        print("PARALLEL_API_KEY=your_api_key_here")
        return False

    print("✅ Parallel API key found")
    print(f"   Key preview: {api_key[:8]}...{api_key[-4:]}")
    print()

    # Test query
    test_query = "What are the latest developments in AI agents in 2024?"

    print(f"🔍 Testing web search with query:")
    print(f"   '{test_query}'")
    print()
    print("⏳ Searching...")
    print()

    # Perform search
    result = web_search(test_query, max_results=3)

    # Display results
    print("=" * 80)
    print("SEARCH RESULTS")
    print("=" * 80)
    print(result)
    print("=" * 80)
    print()

    # Check if search was successful
    if "Error:" in result:
        print("❌ Search failed")
        return False
    else:
        print("✅ Search successful!")
        return True

if __name__ == "__main__":
    print("=" * 80)
    print("PARALLEL AI WEB SEARCH TEST")
    print("=" * 80)
    print()

    success = test_web_search()

    print()
    if success:
        print("🎉 All tests passed! Web search is working correctly.")
    else:
        print("⚠️  Tests failed. Please check the error messages above.")
