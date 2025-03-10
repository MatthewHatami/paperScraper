# next task: connect mfetch_papers.py to github workflow to add summaries to google drive
# fix the formatting of google drive text
# come up with a better prompt for data extraction from the paper
# add the papers to the google sheet(maybe?)

from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import arxiv
import requests
import os
import fitz  # PyMuPDF for PDF text extraction
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

# --- Gemini Summarization Part ---
# Load Gemini API Key from Environment Variable (set via GitHub Secrets or locally)
#GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = "AIzaSyD593mVhnhzb4A36CQriDVF1QL7oeBW10Y"


def fetch_arxiv_papers(keywords, max_results=10, operator="AND"):
    query = f" {operator} ".join([f'(\"{kw}\")' for kw in keywords])
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    # Get today's date in UTC format
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    papers = []
    for result in client.results(search):
        paper_date = result.published.strftime("%Y-%m-%d")  # Convert to string

        # Only include papers published today
        if paper_date == today_utc:
            pdf_url = result.pdf_url  # Get PDF link
            full_text = extract_pdf_text(pdf_url)  # Extract full text

            papers.append({
                "title": result.title,
                "authors": ", ".join([a.name for a in result.authors]),
                "published_date": paper_date,
                "summary": result.summary,
                "pdf_url": pdf_url,
                "full_text": full_text
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
    gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-002:generateContent"
    headers = {"Content-Type": "application/json"}
    # Use the API key as URL parameter
    gemini_url = f"{gemini_url}?key={GEMINI_API_KEY}"
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
    response = requests.post(gemini_url, json=payload, headers=headers)
    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."
    data = response.json()
    # Extract text properly from response
    gemini_summary = "No summary provided by Gemini."
    try:
        gemini_summary = data["candidates"][0]["content"]["parts"][0].get(
            "text", gemini_summary)
    except (KeyError, IndexError, TypeError):
        pass
    return gemini_summary


# --- Google Docs Update Part ---

# Set your Google Docs Document ID (see steps below for how to get this)
# Replace with your actual Google Doc ID
DOCUMENT_ID = "14p892Xm1xvLIH2c1awYAYfT2_yWMYWUiKPRSo8XOcqA"

# Scopes required for Google Docs API
DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]


def append_to_google_doc(content):
    """
    Appends content to the beginning of a Google Docs document.
    """
    try:


        creds = service_account.Credentials.from_service_account_file(
            "gen-lang-client-0505672252-66ab127135ad.json", scopes=DOCS_SCOPES
        )

        service = build("docs", "v1", credentials=creds)
        # Insert at the very beginning after the document header (index 1)
        requests_body = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": content + "\n\n"
                }
            }
        ]
        service.documents().batchUpdate(documentId=DOCUMENT_ID,
                                        body={"requests": requests_body}).execute()
        print("✅ Google Docs updated successfully!")
    except HttpError as error:
        print(f"❌ ERROR: Could not update Google Docs: {error}")

# --- Main Execution ---


def main():
    keywords = ["extreme event", "compound risk", "compound hazard", "floods", "droughts", "heatwaves", "wildfires", "climate extremes", "hydrological extremes",
                "natural disasters", "flood forecasting", "drought indicators", "water resource management", "precipitation extremes", "flood risk", "drought risk",
                "hazard mitigation", "disaster resilience", "hydroclimatic extremes", "climate variability", "climate change adaptation", "extreme weather events", "compound climate extremes", "multi-hazard risk assessment",
                "extreme weather events"]
    papers = fetch_arxiv_papers(keywords, max_results=10, operator="OR")
    for paper in papers:
        paper["gemini_summary"] = gemini_summarize(
            paper["title"], paper["full_text"])

    # Generate a Markdown formatted report
    md_content = "# Research Paper Summaries (Latest First)\n\n"
    for p in papers:
        md_content += f"## {p['title']}\n\n"
        md_content += f"**Authors:** {p['authors']}\n\n"
        md_content += f"**Published:** {p['published_date']}\n\n"
        md_content += f"**PDF Link:** [Link]({p['pdf_url']})\n\n"
        md_content += f"**Gemini Summary:**\n\n{p.get('gemini_summary', 'No summary generated')}\n\n"
        md_content += "---\n\n"

    # Append the new summaries to the Google Doc (at the beginning)
    append_to_google_doc(md_content)

    # Also, print the results locally
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
