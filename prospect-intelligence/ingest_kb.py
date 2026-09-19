#!/usr/bin/env python3
"""
Standalone script to ingest the knowledge base PDFs into ChromaDB.
Call this before running verification tests or the server.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from knowledge.ingestion import ingest_knowledge_base

async def main():
    print("=" * 70)
    print("COEXTEND PROSPECT INTELLIGENCE - KNOWLEDGE BASE INGESTION")
    print("=" * 70)
    
    try:
        num_chunks = await ingest_knowledge_base()
        print(f"\n✓ Ingestion complete: {num_chunks} chunks indexed")
        return 0
    except Exception as e:
        print(f"\n✗ Ingestion failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
