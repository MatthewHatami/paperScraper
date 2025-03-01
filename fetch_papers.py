import arxiv
import requests
import os
import fitz  # PyMuPDF for PDF text extraction

# Load Gemini API Key from GitHub Secrets or Environment Variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")


def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    """
    Fetches papers from arXiv using multiple keywords.
    """
    query = f" {operator} ".join([f'(\"{kw}\")' for kw in keywords])

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    papers = []
    for result in client.results(search):
        pdf_url = result.pdf_url  # Get the full paper PDF link

        # Extract full text from the PDF
        full_text = extract_pdf_text(pdf_url)

        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,  # Original abstract
            "pdf_url": pdf_url,
            "full_text": full_text  # Full extracted text
        })

    return papers


def extract_pdf_text(pdf_url):
    """
    Downloads and extracts text from a given PDF URL.
    """
    response = requests.get(pdf_url)
    if response.status_code != 200:
        print(f"❌ ERROR: Could not download PDF: {pdf_url}")
        return "Full text unavailable."

    # Save the PDF temporarily
    pdf_path = "temp_paper.pdf"
    with open(pdf_path, "wb") as f:
        f.write(response.content)

    # Extract text using PyMuPDF
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text") + "\n"
        doc.close()
    except Exception as e:
        print(f"❌ ERROR: Could not extract text from PDF: {e}")
        return "Full text extraction failed."

    return full_text


def gemini_summarize(title, full_text):
    """
    Uses Gemini API to summarize a research paper with a structured response.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your-gemini-api-key":
        print("❌ ERROR: Gemini API Key is missing.")
        return "Summary unavailable (API key missing)."

    # Replace with actual Gemini API URL
    gemini_url = "https://api.gemini.example.com/generate-text"

    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    # Custom prompt to structure the summary
    prompt = f"""
    You are an AI assistant summarizing research papers. Given the title and full text, provide a structured summary:
    
    - **Novelty**: Describe what is new or unique about this research.
    - **Methodology**: Explain the approach and methods used.
    - **Data**: Describe the datasets or sources of data used.
    - **Conclusion**: Summarize the main findings and contributions.

    **Title**: {title}
    **Full Text**: {full_text[:8000]}  # Truncate to avoid exceeding API limits

    Please return the response in a structured format with bullet points.
    """

    payload = {"text": prompt}

    response = requests.post(gemini_url, json=payload, headers=headers)

    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."

    data = response.json()
    return data.get("summary", "No summary provided by Gemini.")


# Example Usage
keywords = ["floods", "droughts", "climate extremes", "disaster resilience"]

# Fetch papers from arXiv
papers = fetch_arxiv_papers(keywords, max_results=5, operator="OR")

# Summarize each paper using the full text
for paper in papers:
    paper["gemini_summary"] = gemini_summarize(
        paper["title"], paper["full_text"])  # ✅ Now using full text

# Print Results
for p in papers:
    print(f"📌 Title: {p['title']}")
    print(f"👨‍💻 Authors: {p['authors']}")
    print(f"📅 Published: {p['published_date']}")
    print(f"📄 PDF Link: {p['pdf_url']}")
    print("📝 Original Summary:")
    print(p['summary'])
    print("✂️ Gemini Summary:")
    print(p.get("gemini_summary", "No summary generated"))
    print("-" * 50)
