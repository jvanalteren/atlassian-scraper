import re
import os
import sys
from dotenv import load_dotenv
from atlassian import Confluence

from google import genai
from google.genai import types

def safe_filename(title):
    # Replace invalid filename characters with underscore
    return re.sub(r'[\\/:*?"<>|]', '_', title).strip()

load_dotenv(override=True)

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_PAGE_ID = os.getenv("CONFLUENCE_PAGE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def call_gemini_api(pdf_path, api_key):
    client = genai.Client(api_key=api_key)
    prompt = (
        "Please give a short and concise description of the functionality of this Bloomreach strip component. "
        "Your audience is non-technical, e.g. marketeer or UX designer. Use a maximum of 80 words and exclude technical details that are too specific. "
        "Don't mention the name of the strip component, this context will be provided elsewhere. "
        "Don't start with 'This component allows website visitors ...' but immediately start describing the functionality, like 'Allows website visitors to engage...'."
    )
    try:
        with open(pdf_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                ),
                prompt
            ]
        )
        print(response.text)
    except Exception as e:
        print(f"Gemini API call failed: {e}")

def main():
    # Check for PDF path argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if not os.path.exists(pdf_path):
            print(f"Provided PDF file does not exist: {pdf_path}")
            return
        print(f"Calling Gemini API with specified PDF: {pdf_path}")
        call_gemini_api(pdf_path, GEMINI_API_KEY)
        return

    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_USERNAME,
        password=CONFLUENCE_API_TOKEN,
        api_version="cloud"
    )

    print(f"Searching for child pages.")
    cql = f"parent = {CONFLUENCE_PAGE_ID}"
    results = confluence.cql(cql, limit=100)

    if not results or 'results' not in results:
        print("No child pages found.")
        return

    size = len(results['results'])
    print(f"Found {size} child pages.")

    for page in results['results']:
        content = page.get('content', {})
        child_page_id = content.get('id')
        title = content.get('title')
        print(f"Child page {child_page_id}, title {title}.")

        if "[" not in title:
            print(f"Non-strip component page, skipping.")
            continue

        filename = f"{safe_filename(title)}.pdf"
        if not os.path.exists(filename):
            print(f"PDF file missing, exporting page to {filename}", end="")
            try:
                pdf_content = confluence.export_page(child_page_id)
                with open(filename, "wb") as file:
                    file.write(pdf_content)
                print(f" done.")
            except Exception as e:
                print(f" failed: {e}")
                continue

        print(f"# {title}")
        call_gemini_api(filename, GEMINI_API_KEY)

if __name__ == "__main__":
    main()
