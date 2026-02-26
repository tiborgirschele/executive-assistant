#!/bin/bash
set -e

echo "🔍 STAGE 1: WEB SERVER HEALTH"
curl -fsS "http://127.0.0.1:8090/health" && echo -e "\n✅ Server Responsive."

echo "🔍 STAGE 2: BRIEFING DEDUPLICATION CHECK"
docker exec ea-daemon python3 -c "
import asyncio
from app.briefings import build_briefing_for_tenant
async def test():
    res = await build_briefing_for_tenant('tibor')
    text = res.get('text', '')
    occurrences = text.count('Boulderbar')
    print(f'\n--- BRIEFING ---\n{text}')
    if occurrences > 1:
        print(f'\n❌ DEDUPLICATION FAILED: Found {occurrences} Boulderkurs entries.')
    else:
        print('\n✅ DEDUPLICATION SUCCESS: Only one entry found.')
asyncio.run(test())"

echo -e "\n🏁 TEST COMPLETE. Now type /brief in Telegram."
