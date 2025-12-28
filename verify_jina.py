import telegram_bot
from unittest.mock import MagicMock, patch
import requests

def test_jina_direct():
    print("Testing Jina Direct Call...")
    res = telegram_bot.scrape_with_jina("example.com")
    # This might fail if network is down or jina is down, but we want to see if the call structure is right.
    # Since we can't easily mock inner requests in this simple script without patching, 
    # we'll rely on the fact that scrape_with_jina prints logs.
    
    # Actually, let's just test the logic by mocking requests.get
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "# Jina Content"
        
        content = telegram_bot.scrape_with_jina("example.com")
        assert content == "# Jina Content"
        mock_get.assert_called_with("https://r.jina.ai/example.com")
        print("PASS: Jina direct call logic")

def test_linkedin_routing():
    print("Testing LinkedIn Routing...")
    with patch('telegram_bot.scrape_with_jina') as mock_jina:
        mock_jina.return_value = "LinkedIn Content"
        
        # Mock OpenRouter so we don't hit API limits or need keys
        with patch('telegram_bot.client.chat.completions.create') as mock_ai:
            mock_ai.return_value.choices[0].message.content = "Summary"
            
            telegram_bot.scrape_and_summarize("https://www.linkedin.com/post/123")
            
            mock_jina.assert_called_once()
            print("PASS: LinkedIn routed to Jina")

def test_firecrawl_fallback():
    print("Testing Firecrawl Fallback...")
    # 1. Firecrawl fails
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 500 # Firecrawl error
        
        with patch('telegram_bot.scrape_with_jina') as mock_jina:
            mock_jina.return_value = "Fallback Content"
            
            with patch('telegram_bot.client.chat.completions.create') as mock_ai:
                mock_ai.return_value.choices[0].message.content = "Summary"
                
                # Assume env vars are set (mocking them might be needed if not set in env)
                telegram_bot.FIRECRAWL_API_KEY = "mock_key"
                telegram_bot.OPENROUTER_API_KEY = "mock_key"
                
                telegram_bot.scrape_and_summarize("https://other-site.com")
                
                mock_jina.assert_called_once()
                print("PASS: Fallback to Jina on Firecrawl failure")

if __name__ == "__main__":
    try:
        test_jina_direct()
        test_linkedin_routing()
        test_firecrawl_fallback()
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
