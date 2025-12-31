"""Verification script for sentiment analysis service."""

import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from phinan.config.settings import settings
    from phinan.services import services
    
    print("-" * 50)
    print("PHINAN SENTIMENT VERIFICATION")
    print("-" * 50)
    
    # Check settings
    print(f"Environment Variable Status:")
    print(f"  PHINAN_AI_SERVICES_ENABLE_SENTIMENT: {os.getenv('PHINAN_AI_SERVICES_ENABLE_SENTIMENT')}")
    print(f"  PHINAN_AI_SERVICES__ENABLE_SENTIMENT: {os.getenv('PHINAN_AI_SERVICES__ENABLE_SENTIMENT')}")
    
    print(f"\nSettings Object Status:")
    print(f"  settings.ai_services.enable_sentiment: {settings.ai_services.enable_sentiment}")
    print(f"  settings.ai_services.sentiment_model: {settings.ai_services.sentiment_model}")
    
    # Check service health
    print(f"\nService Health Check:")
    is_healthy = services.sentiment.health_check()
    print(f"  services.sentiment.health_check(): {is_healthy}")
    
    if not is_healthy:
        if not settings.ai_services.enable_sentiment:
            print("\n[!] SENTIMENT IS DISABLED in settings.")
            print("TIP: Try setting PHINAN_AI_SERVICES__ENABLE_SENTIMENT=true (with double underscore)")
            print("     or PHINAN_AI_SERVICES_ENABLE_SENTIMENT=true in your .env file.")
        else:
            print("\n[!] SENTIMENT IS ENABLED but health check failed (model load error).")
    else:
        print("\n[*] SENTIMENT IS ENABLED and HEALTHY.")
        
        # Test scoring
        print(f"\nTest Scoring:")
        test_text = "Apple reports record breaking earnings and massive growth."
        result = services.sentiment.score(test_text)
        print(f"  Input: '{test_text}'")
        print(f"  Result: {result['label']} (score: {result['score']:.2f})")
        
    print("-" * 50)

except Exception as e:
    print(f"\n[!] ERROR during verification: {e}")

    import traceback
    traceback.print_exc()
