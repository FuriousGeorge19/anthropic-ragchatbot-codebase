import requests

print("Testing course-specific query (should use search tool)...\n")

response = requests.post(
    "http://localhost:8000/api/query",
    json={
        "query": "What does lesson 2 of the Python course teach about data structures?"
    },
    timeout=30,
)

print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    answer = result.get("answer", "No answer")
    sources = result.get("sources", [])

    print(f"\n✅ Query successful!")
    print(f"\nAnswer (first 400 chars):")
    print(f"{answer[:400]}...")
    print(f"\nSources: {len(sources)} found")

    if sources:
        print("\nSource details:")
        for i, source in enumerate(sources[:3], 1):
            print(f"  {i}. {source.get('text', 'N/A')}")
            print(f"     URL: {source.get('url', 'N/A')[:80]}...")

    if sources and "Python" in answer:
        print("\n✅ PERFECT! Course content retrieved with sources!")
    elif "Python" in answer:
        print("\n✅ Content retrieved (sources may vary)")
    else:
        print("\n⚠️  Unexpected response")
else:
    print(f"❌ Error: {response.status_code}")
