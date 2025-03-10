from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import arxiv
import requests
import os
import fitz  # PyMuPDF for PDF text extraction
from datetime import datetime

# --- Gemini Summarization Part ---
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AIzaSyD593mVhnhzb4A36CQriDVF1QL7oeBW10Y")


def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    query = f" {operator} ".join([f'(\"{kw}\")' for kw in keywords])
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    papers = []
    for result in client.results(search):
        pdf_url = result.pdf_url  # Get PDF link
        full_text = extract_pdf_text(pdf_url)  # Extract full text
        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,
            "pdf_url": pdf_url,
            "full_text": full_text,
            # Use the search terms as keywords
            "keywords": [kw.capitalize() for kw in keywords]
        })
    return papers


def extract_pdf_text(pdf_url):
    response = requests.get(pdf_url)
    if response.status_code != 200:
        print(f"❌ ERROR: Could not download PDF: {pdf_url}")
        return "Full text unavailable."
    pdf_path = "temp_paper.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
    except Exception as e:
        print(f"❌ ERROR: Could not extract text from PDF: {e}")
        return "Full text extraction failed."
    return full_text


def gemini_summarize(title, full_text):
    if not GEMINI_API_KEY:
        print("❌ ERROR: Gemini API Key is missing.")
        return "Summary unavailable (API key missing)."

    gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-002:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""
    You are an AI assistant summarizing research papers. Given the title and full text, provide a structured summary:

    - **Novelty**: Describe what is new or unique about this research.
    - **Methodology**: Explain the approach and methods used.
    - **Data**: Describe the datasets or sources of data used.
    - **Conclusion**: Summarize the main findings and contributions.

    **Title**: {title}
    **Full Text**: {full_text[:8000]}  

    Please return the response in a structured format with bullet points.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(gemini_url, json=payload, headers={
                             "Content-Type": "application/json"})

    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0].get("text", "No summary provided by Gemini.")
    except (KeyError, IndexError, TypeError):
        return "No summary provided by Gemini."

# --- Google Docs Update Part ---


DOCUMENT_ID = "14p892Xm1xvLIH2c1awYAYfT2_yWMYWUiKPRSo8XOcqA"

DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]


def append_to_google_doc(papers):
    """
    Appends structured paper summaries to Google Docs with proper formatting.
    Each paper is on a separate page.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            "gen-lang-client-0505672252-66ab127135ad.json", scopes=DOCS_SCOPES
        )
        service = build("docs", "v1", credentials=creds)

        requests_body = []

        for paper in papers:
            # Get the current date in Italian format
            date_added = datetime.now().strftime("%d %B %Y")

            requests_body += [
                # Add date of entry in italics
                {"insertText": {"location": {"index": 1},
                                "text": f"\n\n{date_added}\n"}},
                {"updateTextStyle": {
                    "range": {"startIndex": 1, "endIndex": 1 + len(date_added)},
                    "textStyle": {"italic": True},
                    "fields": "italic"
                }},

                # Add Title (Bold)
                {"insertText": {"location": {"index": 1},
                                "text": f"{paper['title']}\n"}},
                {"updateTextStyle": {
                    "range": {"startIndex": 1, "endIndex": 1 + len(paper['title'])},
                    "textStyle": {"bold": True},
                    "fields": "bold"
                }},

                # Add Authors
                {"insertText": {"location": {"index": 1},
                                "text": f"Authors: {paper['authors']}\n"}},

                # Add Keywords
                {"insertText": {"location": {"index": 1},
                                "text": f"Keywords: {', '.join(paper['keywords'])}\n"}},

                # Add Abstract
                {"insertText": {"location": {"index": 1},
                                "text": f"Abstract: {paper['summary']}\n"}},

                # Add Date Published (Bold)
                {"insertText": {"location": {"index": 1},
                                "text": f"Published: {paper['published_date']}\n"}},
                {"updateTextStyle": {
                    "range": {"startIndex": 1, "endIndex": 1 + len(f'Published: {paper["published_date"]}')},
                    "textStyle": {"bold": True},
                    "fields": "bold"
                }},

                # Add Gemini Summary
                {"insertText": {"location": {"index": 1}, "text": "Gemini Summary:\n"}},
                {"updateTextStyle": {
                    "range": {"startIndex": 1, "endIndex": 1 + len("Gemini Summary:")},
                    "textStyle": {"bold": True},
                    "fields": "bold"
                }},
                {"insertText": {"location": {"index": 1}, "text": paper.get(
                    "gemini_summary", "No summary generated") + "\n\n"}},

                # Add Page Break
                {"insertPageBreak": {"location": {"index": 1}}}
            ]

        service.documents().batchUpdate(documentId=DOCUMENT_ID,
                                        body={"requests": requests_body}).execute()
        print("✅ Google Docs updated successfully!")
    except HttpError as error:
        print(f"❌ ERROR: Could not update Google Docs: {error}")

# --- Main Execution ---


def main():
    keywords = ["floods", "droughts",
                "climate extremes", "disaster resilience"]
    papers = fetch_arxiv_papers(keywords, max_results=2, operator="OR")

    for paper in papers:
        paper["gemini_summary"] = gemini_summarize(
            paper["title"], paper["full_text"])

    # Append structured summaries to Google Docs
    append_to_google_doc(papers)

    # Print results locally
    for p in papers:
        print(f"📌 Title: {p['title']}")
        print(f"👨‍💻 Authors: {p['authors']}")
        print(f"📅 Published: {p['published_date']}")
        print(f"📄 PDF Link: {p['pdf_url']}")
        print("✂️ Gemini Summary:")
        print(p.get("gemini_summary", "No summary generated"))
        print("-" * 50)


if __name__ == "__main__":
    main()
