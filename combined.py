import os
import arxiv
import fitz  # PyMuPDF for PDF text extraction
import requests
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re
import json

# --- Load Environment Variables from GitHub Secrets ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# os.getenv("GEMINI_API_KEY")

# Replace with your actual Google Doc ID
DOCUMENT_ID = os.getenv("DOCUMENT_ID")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
]

# Load Google API Credentials (from GitHub Secrets)
CREDS = service_account.Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES
)


def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    """Fetches arXiv papers based on keywords."""
    query = f" {operator} ".join([f'(\"{kw}\")' for kw in keywords])
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    papers = []
    for result in arxiv.Client().results(search):
        pdf_url = result.pdf_url
        full_text = extract_pdf_text(pdf_url)
        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,
            "pdf_url": pdf_url,
            "full_text": full_text
        })
    return papers


def extract_pdf_text(pdf_url):
    """Downloads and extracts text from an arXiv PDF."""
    response = requests.get(pdf_url)
    if response.status_code != 200:
        return "Full text unavailable."

    pdf_path = "temp_paper.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)

    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
    except Exception as e:
        return f"Error extracting text: {e}"

    return text


def gemini_summarize(title, full_text):
    """Uses Gemini API to generate a structured summary of a research paper."""
    if not GEMINI_API_KEY:
        return "Summary unavailable (API key missing)."

    url = (
        "https://generativelanguage.googleapis.com/v1/models/"
        "gemini-1.5-pro-002:generateContent"
        f"?key={GEMINI_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    prompt = f"""
    **Title**: {title}
    **Summary Request**: Summarize the paper focusing on:
    - **Novelty**: What's new about this research?
    - **Methodology**: Key methods used.
    - **Key Findings**: Quantitative results.
    - **Limitations**: Constraints & future research.

    **Full Text** (first 8000 chars): {full_text[:8000]}
    """

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        return "Summary unavailable (API error)."

    data = response.json()

    # Safely extract text from candidates->content->parts->text
    gemini_summary = None
    candidates = data.get("candidates", [])
    if candidates:
        candidate = candidates[0]  # just look at the first
        content = candidate.get("content", {})
        if isinstance(content, dict):
            # content is a dict with "parts"
            parts = content.get("parts", [])
            if parts and isinstance(parts[0], dict):
                gemini_summary = parts[0].get("text", "")
        elif isinstance(content, str):
            # content is already a string
            gemini_summary = content

    # Fallback if we didn't get a string
    if not gemini_summary or not isinstance(gemini_summary, str):
        gemini_summary = "No summary provided."

    # Convert literal "\n" to real newlines
    gemini_summary = gemini_summary.replace("\\n", "\n")

    return gemini_summary


def append_to_google_doc(papers):
    """
    Appends research summaries to a Google Doc without any Markdown or bold formatting.
    """
    try:
        service = build("docs", "v1", credentials=CREDS)

        requests_body = []
        doc_index = 1

        # Insert a simple header
        header_text = f"Research Paper Summaries ({datetime.today().strftime('%Y-%m-%d')})\n\n"
        requests_body.append({
            "insertText": {
                "location": {"index": doc_index},
                "text": header_text
            }
        })
        doc_index += len(header_text)

        # Now handle each paper
        for p in papers:
            text_block = (
                f"TITLE: {p['title']}\n"
                f"AUTHORS: {p['authors']}\n"
                f"PUBLISHED: {p['published_date']}\n"
                f"PDF LINK: {p['pdf_url']}\n\n"
                f"ABSTRACT:\n{p['summary']}\n\n"  # <-- Insert the abstract here
                f"GEMINI SUMMARY:\n\n{p.get('gemini_summary', 'No summary provided.')}\n"
                + "-" * 80 + "\n\n"
            )

            requests_body.append({
                "insertText": {
                    "location": {"index": doc_index},
                    "text": text_block
                }
            })
            doc_index += len(text_block)

        # Send the requests in one batch
        service.documents().batchUpdate(
            documentId=DOCUMENT_ID,
            body={"requests": requests_body}
        ).execute()

        print("✅ Google Docs updated successfully (plain text)!")
    except Exception as e:
        print(f"❌ ERROR: Could not update Google Docs: {e}")


def export_google_doc_to_pdf():
    """Exports the Google Docs document as a PDF."""
    drive_service = build("drive", "v3", credentials=CREDS)
    pdf_path = "research_summaries.pdf"

    try:
        request = drive_service.files().export_media(
            fileId=DOCUMENT_ID,
            mimeType="application/pdf"
        )
        with open(pdf_path, "wb") as f:
            f.write(request.execute())
        print("✅ PDF Exported Successfully!")
        return pdf_path
    except Exception as e:
        print(f"❌ ERROR: Could not export Google Doc as PDF: {e}")
        return None


def load_summarized_ids(cache_file="summarized_papers.json"):
    """Returns a set of paper IDs we've previously summarized."""
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            try:
                data = json.load(f)
                return set(data)
            except json.JSONDecodeError:
                return set()
    return set()

def save_summarized_ids(summarized_ids, cache_file="summarized_papers.json"):
    """Saves the set of summarized paper IDs to a JSON file."""
    with open(cache_file, "w") as f:
        json.dump(list(summarized_ids), f, indent=2)


def main():
    summarized_ids = load_summarized_ids()

    keywords = ["floods", "droughts", "climate extremes", "disaster resilience"]
    papers = fetch_arxiv_papers(keywords, max_results=3, operator="OR")

    new_papers = []
    for paper in papers:
        paper_id = paper["pdf_url"]  # or parse from result.entry_id
        if paper_id not in summarized_ids:
            paper["gemini_summary"] = gemini_summarize(paper["title"], paper["full_text"])
            new_papers.append(paper)
            summarized_ids.add(paper_id)

    if not new_papers:
        print("No new papers to summarize.")
        return

    append_to_google_doc(new_papers)
    pdf_path = export_google_doc_to_pdf()

    # ✅ Save Output for GitHub Actions Email
    with open("output.txt", "w") as f:
        for paper in new_papers:
            f.write(f"## {paper['title']}\n")
            f.write(f"**Authors:** {paper['authors']}\n")
            f.write(f"**Published:** {paper['published_date']}\n")
            f.write(f"**PDF Link:** [Link]({paper['pdf_url']})\n")
            f.write(f"**Gemini Summary:**\n{paper['gemini_summary']}\n")
            f.write("---\n\n")

    if pdf_path:
        os.rename(pdf_path, "research_summary.pdf")

    # Finally, save updated list of summarized IDs
    save_summarized_ids(summarized_ids)


if __name__ == "__main__":
    main()
