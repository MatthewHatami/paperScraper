import arxiv
import requests
import os
import fitz  # PyMuPDF for PDF text extraction

# ✅ Load Gemini API Key from Environment Variable
GEMINI_API_KEY = "AIzaSyD593mVhnhzb4A36CQriDVF1QL7oeBW10Y"# os.getenv("GEMINI_API_KEY")

# ✅ Function to Fetch Papers from arXiv


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
        full_text = extract_pdf_text(pdf_url)  # Extract Full Text
        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,
            "pdf_url": pdf_url,
            "full_text": full_text
        })
    return papers

# ✅ Function to Extract Full Text from PDF


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

# ✅ Function to Summarize Paper with Gemini API


def gemini_summarize(title, full_text):
    if not GEMINI_API_KEY:
        print("❌ ERROR: Gemini API Key is missing.")
        return "Summary unavailable (API key missing)."

    gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-002:generateContent"
    headers = {"Content-Type": "application/json"}

    # ✅ Using API Key as a URL Parameter
    gemini_url = f"{gemini_url}?key={GEMINI_API_KEY}"

    prompt = f"""

    Act as a research assistant. Analyze the following scientific paper titled "{title}" and the full text {full_text[:8000]}
      and provide a structured summary focusing on these elements:


**1. Core Contribution**
- Identify the primary research question/hypothesis.
- Highlight the novel methodology or approach used.

**2. Key Findings**
- List 3-5 central results with quantitative data(e.g., "X method achieved 92% accuracy in Y conditions").
- Note statistically significant outcomes(p-values/confidence intervals).

**3. Technical Definitions**
- Extract and explain 2-3 domain-specific terms crucial for understanding this paper.

**4. Limitations & Future Work**
- Summarize acknowledged constraints of the study.
- Outline proposed directions for further research.

**5. Practical Implications**
- Describe how these findings could impact[your field: e.g., clinical practice/ML engineering].

Format as bullet points with bolded section headers. Prioritize clarity over completeness. Ask clarifying questions if any section needs adjustment for your use case.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(gemini_url, json=payload, headers=headers)

    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."

    data = response.json()

    # ✅ Extract the text response correctly (FIXED!)
    gemini_summary = "No summary provided by Gemini."
    if "candidates" in data:
        first_candidate = data["candidates"][0]
        if "content" in first_candidate and "parts" in first_candidate["content"]:
            gemini_summary = first_candidate["content"]["parts"][0].get(
                "text", "No summary provided by Gemini.")

    return gemini_summary

# ✅ Function to Save Research Summaries in Markdown


def save_markdown_report(papers):
    md_filename = "papers.md"
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write("# Research Paper Summaries\n\n")

        for p in papers:
            f.write(f"## {p['title']}\n\n")
            f.write(f"**👨‍💻 Authors:** {p.get('authors', 'Unknown')}\n\n")
            f.write(
                f"**📅 Published:** {p.get('published_date', 'Unknown')}\n\n")
            f.write(f"**📄 [PDF Link]({p.get('pdf_url', 'Unavailable')})**\n\n")
            f.write("### ✂️ Gemini Summary:\n\n")
            f.write(p.get("gemini_summary", "No summary generated") + "\n\n")
            f.write("---\n\n")

    print(f"✅ Markdown Report Saved: {md_filename}")


# ✅ Main Execution
if __name__ == "__main__":
    keywords = ["floods", "droughts",
                "climate extremes", "disaster resilience"]

    papers = fetch_arxiv_papers(keywords, max_results=2, operator="OR")

    for paper in papers:
        paper["gemini_summary"] = gemini_summarize(
            paper["title"], paper["full_text"])

    save_markdown_report(papers)

    # ✅ Print Results
    for p in papers:
        print(f"📌 Title: {p['title']}")
        print(f"👨‍💻 Authors: {p['authors']}")
        print(f"📅 Published: {p['published_date']}")
        print(f"📄 PDF Link: {p['pdf_url']}")
        print("✂️ Gemini Summary:")
        print(p.get("gemini_summary", "No summary generated"))
        print("-" * 50)
