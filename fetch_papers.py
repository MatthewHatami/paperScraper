import arxiv
import requests
import os
import fitz  # PyMuPDF for PDF text extraction

# ✅ Replace OAuth with an API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ ERROR: Gemini API Key is missing from environment variables.")
    exit(1)

def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    """ Fetches papers from arXiv using multiple keywords. """
    query = f" {operator} ".join([f'(\"{kw}\")' for kw in keywords])

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    papers = []
    for result in client.results(search):
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
    """ Downloads and extracts text from a given PDF URL. """
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
    """ Uses Gemini API to summarize a research paper with a structured response. """
    if not GEMINI_API_KEY:
        print("❌ ERROR: Gemini API Key is missing.")
        return "Summary unavailable (API key missing)."

    gemini_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-002:generateContent?key={GEMINI_API_KEY}"

    headers = {"Content-Type": "application/json"}

    prompt = f"""

    Act as a research assistant. Analyze the following scientific paper titled "{title}" and the full text {full_text[:8000]}
      and provide a structured summary focusing on these elements:

**1. Core Contribution**  
- Identify the primary research question/hypothesis.  
- Highlight the novel methodology or approach used.  

**2. Key Findings**  
- List 3-5 central results with quantitative data (e.g., "X method achieved 92% accuracy in Y conditions").  
- Note statistically significant outcomes (p-values/confidence intervals).  

**3. Technical Definitions**  
- Extract and explain 2-3 domain-specific terms crucial for understanding this paper.  

**4. Limitations & Future Work**  
- Summarize acknowledged constraints of the study.  
- Outline proposed directions for further research.  

**5. Practical Implications**  
- Describe how these findings could impact [your field: e.g., clinical practice/ML engineering].  

Format as bullet points with bolded section headers. Prioritize clarity over completeness. Ask clarifying questions if any section needs adjustment for your use case.
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(gemini_url, json=payload, headers=headers)

    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."

    data = response.json()
    return data.get("candidates", [{}])[0].get("content", "No summary provided by Gemini.")


# ✅ Main Script Execution
if __name__ == "__main__":
    keywords = ["extreme event", "compound risk", "compound hazard", "floods", "droughts", "heatwaves", "wildfires", "climate extremes", "hydrological extremes",
                "natural disasters", "flood forecasting", "drought indicators", "water resource management", "precipitation extremes", "flood risk", "drought risk",
                "hazard mitigation", "disaster resilience", "hydroclimatic extremes", "climate variability", "climate change adaptation", "extreme weather events", "compound climate extremes", "multi-hazard risk assessment",
                "extreme weather events"]

    papers = fetch_arxiv_papers(keywords, max_results=5, operator="OR")

    for paper in papers:
        paper["gemini_summary"] = gemini_summarize(
            paper["title"], paper["full_text"])

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
