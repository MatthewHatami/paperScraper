import arxiv
import requests
import os

# Load Gemini API Key from environment variable or GitHub Secret
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "yAIzaSyD593mVhnhzb4A36CQriDVF1QL7oeBW10Y")


def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    """
    Fetches papers from arXiv using multiple keywords.
    
    :param keywords: List of keywords to search for.
    :param max_results: Maximum number of results.
    :param operator: "AND" (all keywords must appear) or "OR" (any keyword can appear).
    :return: List of paper dictionaries.
    """
    query = f" {operator} ".join([f'("{kw}")' for kw in keywords])

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    papers = []
    for result in client.results(search):


        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,  # Original abstract from arXiv
            "pdf_url": result.pdf_url
        })

    return papers


def gemini_summarize(title, abstract):
    """
    Uses Gemini API to summarize a research paper with a structured response.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your-gemini-api-key":
        print("❌ ERROR: Gemini API Key is missing. Set GEMINI_API_KEY as an environment variable or GitHub Secret.")
        return "Summary unavailable (API key missing)."

    # Replace with actual Gemini API URL
    gemini_url = "https://api.gemini.example.com/generate-text"

    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json"
    }

    # Custom prompt to structure the summary
    prompt = f"""
    You are an AI assistant that summarizes research papers in a structured format.
    Given the title and abstract of a paper, provide a summary with the following sections:
    
    - **Novelty**: Describe what is new or unique about this research.
    - **Methodology**: Briefly explain the approach and methods used.
    - **Data**: Describe the datasets or sources of data used in the study.
    - **Conclusion**: Summarize the main findings and contributions of the paper.
    
    **Title**: {title}
    **Abstract**: {abstract}
    
    Please return the response in a structured format using bullet points for each section.
    """

    payload = {"text": prompt}

    response = requests.post(gemini_url, json=payload, headers=headers)

    if response.status_code != 200:
        print(
            f"❌ ERROR: Failed to summarize text. Status: {response.status_code}, Response: {response.text}")
        return "Summary unavailable (API error)."

    data = response.json()
    return data.get("summary", "No summary provided by Gemini.")

# Example Usage: Provide a List of Keywords
keywords = ["extreme event", "compound risk", "compound hazard", "floods", "droughts", "heatwaves", "wildfires", "climate extremes", "hydrological extremes",
            "natural disasters", "flood forecasting", "drought indicators", "water resource management", "precipitation extremes", "flood risk", "drought risk",
            "hazard mitigation", "disaster resilience", "hydroclimatic extremes", "climate variability", "climate change adaptation", "extreme weather events", "compound climate extremes", "multi-hazard risk assessment",
            "extreme weather events"]

# Fetch papers from arXiv
papers = fetch_arxiv_papers(keywords, max_results=10, operator="OR")

# Summarize each paper using Gemini API
for paper in papers:
    paper["gemini_summary"] = gemini_summarize(paper["summary"])

# Print Results with Gemini Summary
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
