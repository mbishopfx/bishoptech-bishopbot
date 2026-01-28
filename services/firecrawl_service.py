from firecrawl import FirecrawlApp
from config import CONFIG
import time

# Use the FirecrawlApp class
app = FirecrawlApp(api_key=CONFIG["FIRECRAWL_API_KEY"])

def scrape_url(url):
    """Scrapes a single URL and returns markdown."""
    try:
        # v2 scrape method
        result = app.scrape(url, params={'formats': ['markdown']})
        return result.get('markdown', "No content found.")
    except Exception as e:
        return f"Scrape Error: {str(e)}"

def map_url(url):
    """Maps the website structure."""
    try:
        # v2 map method
        result = app.map(url)
        # Returns links directly or in a dict depending on version
        if isinstance(result, list):
            return result
        return result.get('links', [])
    except Exception as e:
        return f"Map Error: {str(e)}"

def crawl_url(url, limit=5):
    """Crawls a URL synchronously (v2) or async with polling."""
    try:
        # In newer SDK versions, .crawl() can be synchronous if it waits by default
        # or we might need to use start_crawl
        print(f"🕸️ Starting crawl for {url} (limit: {limit})...")
        
        # Try the most direct v2 way
        # Some versions use crawl(url, limit=10), others use params
        try:
            crawl_result = app.crawl(url, limit=limit, formats=['markdown'])
        except TypeError:
            # Fallback if keyword arguments are different
            crawl_result = app.crawl(url, params={'limit': limit, 'formats': ['markdown']})

        if isinstance(crawl_result, dict) and 'data' in crawl_result:
            pages = crawl_result.get('data', [])
            combined_md = ""
            for i, page in enumerate(pages):
                combined_md += f"\n\n--- PAGE {i+1}: {page.get('url')} ---\n\n"
                combined_md += page.get('markdown', '')
            return combined_md
            
        # If it returns a job ID (async fallback)
        job_id = crawl_result.get('id') if isinstance(crawl_result, dict) else None
        if not job_id:
             return "Crawl failed to return data or job ID."

        print(f"🕒 Crawl job started: {job_id}. Polling for results...")
        
        max_retries = 30 # 60 seconds max
        for _ in range(max_retries):
            status = app.get_crawl_status(job_id)
            if status.get('status') == 'completed':
                pages = status.get('data', [])
                combined_md = ""
                for i, page in enumerate(pages):
                    combined_md += f"\n\n--- PAGE {i+1}: {page.get('url')} ---\n\n"
                    combined_md += page.get('markdown', '')
                return combined_md
            elif status.get('status') == 'failed':
                return f"Crawl job {job_id} failed."
            
            time.sleep(2)
            
        return "Crawl timed out."
    except Exception as e:
        return f"Crawl Error: {str(e)}"
