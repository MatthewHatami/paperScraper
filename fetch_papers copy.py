import arxiv


def fetch_arxiv_papers(keywords, max_results=5, operator="AND"):
    """
    Fetches papers from arXiv using multiple keywords.
    
    :param keywords: List of keywords to search for.
    :param max_results: Maximum number of results.
    :param operator: "AND" (all keywords must appear) or "OR" (any keyword can appear).
    :return: List of paper dictionaries.
    """
    # Create query string based on multiple keywords
    query = f" {operator} ".join([f'("{kw}")' for kw in keywords])

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    papers = []
    for result in search.results():
        papers.append({
            "title": result.title,
            "authors": ", ".join([a.name for a in result.authors]),
            "published_date": result.published.strftime("%Y-%m-%d"),
            "summary": result.summary,
            "pdf_url": result.pdf_url
        })

    return papers


# Example Usage: Provide a List of Keywords
keywords = ["extreme event", "compound risk", "compound hazard", "floods", "droughts", "heatwaves", "wildfires", "climate extremes", "hydrological extremes",
            "natural disasters", "flood forecasting", "drought indicators", "water resource management", "precipitation extremes", "flood risk", "drought risk",
            "hazard mitigation", "disaster resilience", "hydroclimatic extremes", "climate variability", "climate change adaptation", "extreme weather events", "compound climate extremes", "multi-hazard risk assessment",
            "extreme weather events"]

papers = fetch_arxiv_papers(keywords, max_results=10, operator="OR")

# Print Results
for p in papers:
    print(f"📌 Title: {p['title']}")
    print(f"👨‍💻 Authors: {p['authors']}")
    print(f"📅 Published: {p['published_date']}")
    print(f"📄 PDF Link: {p['pdf_url']}")
    print("-" * 50)
