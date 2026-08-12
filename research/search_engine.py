"""
Multi-Source Search Engine
Tavily → SerpAPI → Wikipedia → DuckDuckGo → arXiv
Each as fallback. No single point of failure.
"""

import json
import httpx
from typing import List, Dict, Optional
from core.config import Config

class ResearchSearchEngine:
    """
    Multi-source search with automatic fallback.
    Priority: Tavily > SerpAPI > Wikipedia > DuckDuckGo > arXiv
    """
    
    def __init__(self):
        self.tavily_key = Config.TAVILY_API_KEY
        self.serpapi_key = Config.SERPAPI_API_KEY
    
    async def search(self, query: str, max_results: int = 10, 
                     source: str = "auto") -> Dict:
        """
        Search across multiple sources with fallback.
        source: "auto", "tavily", "serpapi", "wikipedia", "duckduckgo", "arxiv"
        """
        results = []
        sources_used = []
        errors = []
        
        # Try Tavily first (best for AI research)
        if source in ("auto", "tavily") and self.tavily_key:
            try:
                tavily_results = await self._search_tavily(query, max_results)
                if tavily_results:
                    results.extend(tavily_results)
                    sources_used.append("tavily")
            except Exception as e:
                errors.append({"source": "tavily", "error": str(e)})
        
        # Fallback to SerpAPI
        if source in ("auto", "serpapi") and (not results or source != "auto"):
            if self.serpapi_key:
                try:
                    serp_results = await self._search_serpapi(query, max_results)
                    if serp_results:
                        results.extend(serp_results)
                        sources_used.append("serpapi")
                except Exception as e:
                    errors.append({"source": "serpapi", "error": str(e)})
        
        # Fallback to Wikipedia
        if source in ("auto", "wikipedia") and (not results or source != "auto"):
            try:
                wiki_results = await self._search_wikipedia(query, max_results)
                if wiki_results:
                    results.extend(wiki_results)
                    sources_used.append("wikipedia")
            except Exception as e:
                errors.append({"source": "wikipedia", "error": str(e)})
        
        # Fallback to DuckDuckGo
        if source in ("auto", "duckduckgo") and (not results or source != "auto"):
            try:
                ddg_results = await self._search_duckduckgo(query, max_results)
                if ddg_results:
                    results.extend(ddg_results)
                    sources_used.append("duckduckgo")
            except Exception as e:
                errors.append({"source": "duckduckgo", "error": str(e)})
        
        # Fallback to arXiv for academic
        if source in ("auto", "arxiv") and len(results) < 3:
            try:
                arxiv_results = await self._search_arxiv(query, max_results)
                if arxiv_results:
                    results.extend(arxiv_results)
                    sources_used.append("arxiv")
            except Exception as e:
                errors.append({"source": "arxiv", "error": str(e)})
        
        # Deduplicate
        results = self._deduplicate(results, max_results)
        
        return {
            "query": query,
            "total_results": len(results),
            "sources_used": sources_used,
            "errors": errors if errors else None,
            "results": results
        }
    
    async def _search_tavily(self, query: str, max_results: int) -> List[Dict]:
        """Search using Tavily API (optimized for AI research)"""
        url = "https://api.tavily.com/search"
        
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            data = response.json()
            
            results = []
            
            # Add AI-generated answer if available
            if data.get("answer"):
                results.append({
                    "title": "AI Summary",
                    "content": data["answer"],
                    "url": "tavily_ai",
                    "source": "tavily",
                    "type": "ai_summary"
                })
            
            # Add search results
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "source": "tavily",
                    "type": "web_result",
                    "score": r.get("score", 0)
                })
            
            return results
    
    async def _search_serpapi(self, query: str, max_results: int) -> List[Dict]:
        """Search using SerpAPI (Google results)"""
        url = "https://serpapi.com/search"
        
        params = {
            "api_key": self.serpapi_key,
            "q": query,
            "num": max_results,
            "engine": "google"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            results = []
            
            # Organic results
            for r in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("snippet", ""),
                    "url": r.get("link", ""),
                    "source": "serpapi",
                    "type": "web_result"
                })
            
            # Knowledge graph
            if data.get("knowledge_graph"):
                kg = data["knowledge_graph"]
                results.insert(0, {
                    "title": kg.get("title", query),
                    "content": kg.get("description", ""),
                    "url": kg.get("website", ""),
                    "source": "serpapi",
                    "type": "knowledge_graph"
                })
            
            return results
    
    async def _search_wikipedia(self, query: str, max_results: int) -> List[Dict]:
        """Search Wikipedia"""
        import wikipedia
        
        try:
            # Search for pages
            search_results = wikipedia.search(query, results=max_results)
            
            results = []
            for title in search_results[:max_results]:
                try:
                    page = wikipedia.page(title, auto_suggest=False)
                    results.append({
                        "title": page.title,
                        "content": page.summary[:1000],
                        "url": page.url,
                        "source": "wikipedia",
                        "type": "encyclopedia",
                        "images": page.images[:3] if hasattr(page, 'images') else []
                    })
                except:
                    continue
            
            return results
        except Exception as e:
            raise e
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """Search using DuckDuckGo"""
        from duckduckgo_search import DDGS
        
        results = []
        
        with DDGS() as ddgs:
            # Text search
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("body", ""),
                    "url": r.get("href", ""),
                    "source": "duckduckgo",
                    "type": "web_result"
                })
        
        return results
    
    async def _search_arxiv(self, query: str, max_results: int) -> List[Dict]:
        """Search arXiv for academic papers"""
        import arxiv
        
        results = []
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        for paper in search.results():
            results.append({
                "title": paper.title,
                "content": paper.summary[:1000],
                "url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "source": "arxiv",
                "type": "academic_paper",
                "authors": [a.name for a in paper.authors],
                "published": paper.published.isoformat() if paper.published else None
            })
        
        return results
    
    def _deduplicate(self, results: List[Dict], max_results: int) -> List[Dict]:
        """Remove duplicate results based on URL"""
        seen_urls = set()
        unique = []
        
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(r)
            elif not url:
                unique.append(r)
        
        return unique[:max_results]
    
    async def deep_research(self, query: str, depth: int = 3) -> Dict:
        """
        Deep research: initial search + follow-up searches based on findings.
        """
        all_results = []
        
        # Initial search
        initial = await self.search(query, max_results=10)
        all_results.extend(initial["results"])
        
        # Extract key topics for deeper search
        if depth > 1:
            topics = self._extract_topics(initial["results"])
            
            for topic in topics[:depth]:
                deeper = await self.search(topic, max_results=5)
                all_results.extend(deeper["results"])
        
        # Deduplicate final results
        final_results = self._deduplicate(all_results, 20)
        
        return {
            "query": query,
            "depth": depth,
            "total_findings": len(final_results),
            "results": final_results
        }
    
    def _extract_topics(self, results: List[Dict]) -> List[str]:
        """Extract key topics from results for deeper research"""
        # Get unique words from titles
        words = []
        for r in results[:5]:
            title = r.get("title", "")
            words.extend([w for w in title.split() if len(w) > 4])
        
        # Return most common words as topics
        from collections import Counter
        return [word for word, _ in Counter(words).most_common(5)]
