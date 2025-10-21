import json

import requests

print("Testing RAG API after MAX_RESULTS fix...\n")

# Test the API
try:
    response = requests.post(
        "http://localhost:8000/api/query", json={"query": "What is Python?"}, timeout=30
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        answer = result.get("answer", "No answer")
        sources = result.get("sources", [])

        print(f"\n✅ SUCCESS! Query returned results.")
        print(f"\nAnswer (first 300 chars):")
        print(f"  {answer[:300]}...")
        print(f"\nSources: {len(sources)} found")

        if sources:
            print("\nFirst source:")
            print(f"  Text: {sources[0].get('text', 'N/A')}")
            print(f"  URL: {sources[0].get('url', 'N/A')}")

        # Check if this is real content (not "query failed")
        if len(answer) > 50 and "query failed" not in answer.lower():
            print("\n🎉 FIX VERIFIED: The RAG system is now working!")
        else:
            print("\n⚠️  Warning: Response seems incomplete")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error connecting to API: {e}")
    print("\nMake sure the server is running with:")
    print("  cd backend && uv run uvicorn app:app --reload --port 8000")
