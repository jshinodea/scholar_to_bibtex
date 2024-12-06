from flask import Flask, request, jsonify, send_file
import os
from serpapi import GoogleSearch
from dotenv import load_dotenv
import re
from urllib.parse import urlparse, parse_qs
import hashlib

app = Flask(__name__)

def extract_author_id(url):
    """Extract the author ID from a Google Scholar URL."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get('user', [None])[0]

def get_publications(author_id, api_key):
    """Fetch all publications for a given author ID using SerpAPI with pagination."""
    all_articles = []
    start = 0
    batch_size = 100

    while True:
        params = {
            "api_key": api_key,
            "engine": "google_scholar_author",
            "author_id": author_id,
            "start": start,
            "num": batch_size,
            "sort": "pubdate"
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        articles = results.get('articles', [])
        
        if not articles:
            break
            
        all_articles.extend(articles)
        start += batch_size
        print(f"Fetched {len(all_articles)} publications...")
        
    return all_articles

def create_bibtex_entry(article):
    """Convert a single article to BibTeX format."""
    first_author = article['authors'].split(',')[0].strip()
    last_name = first_author.split()[-1].lower()
    year = article.get('year', 'XXXX')
    
    title_hash = hashlib.md5(article['title'].encode()).hexdigest()[:4]
    citation_key = f"{last_name}{year}_{title_hash}"
    
    title = article['title'].replace('{', '\\{').replace('}', '\\}')
    authors = article['authors'].replace(' and ', ' AND ')
    
    entry = [
        f"@article{{{citation_key},",
        f"  title = {{{title}}},",
        f"  author = {{{authors}}},",
        f"  year = {{{year}}},",
    ]
    
    if 'publication' in article:
        entry.append(f"  journal = {{{article['publication']}}},")
    
    if 'cited_by' in article:
        entry.append(f"  note = {{Cited by {article['cited_by']['value']}}},")
    
    if 'link' in article:
        entry.append(f"  url = {{{article['link']}}},")
    
    entry.append("}")
    return '\n'.join(entry)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/convert', methods=['POST'])
def convert_to_bibtex():
    load_dotenv()
    api_key = os.getenv('SERPAPI_KEY')
    
    if not api_key:
        return jsonify({"error": "SERPAPI_KEY not found in environment variables"}), 500
    
    data = request.get_json()
    if not data or 'scholar_url' not in data:
        return jsonify({"error": "Missing scholar_url in request body"}), 400
    
    url = data['scholar_url']
    author_id = extract_author_id(url)
    
    if not author_id:
        return jsonify({"error": "Could not extract author ID from URL"}), 400
    
    try:
        publications = get_publications(author_id, api_key)
        
        if not publications:
            return jsonify({"error": "No publications found"}), 404
        
        bibtex_entries = [create_bibtex_entry(article) for article in publications]
        
        output_file = f"scholar_{author_id}_publications.bib"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(bibtex_entries))
        
        return send_file(
            output_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name=output_file
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 