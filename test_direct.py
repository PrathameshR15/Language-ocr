import asyncio
from backend.services.document_parser_service import document_parser

async def main():
    with open('test_arial_rupee.pdf', 'rb') as f:
        content = f.read()
    
    try:
        res = await document_parser.process_document(content, 'test_arial_rupee.pdf')
        print("Success!", res.keys())
    except Exception as e:
        print("Direct parser error:", e)

asyncio.run(main())
