"""Tavily Google Shopping tool for product research."""

import asyncio
from typing import List, Dict, Any, Optional
from tavily import TavilyClient
from src.core.config import settings
from src.core.models import SearchResult, Product, Review
import logging

logger = logging.getLogger(__name__)


class TavilyShoppingTool:
    """Tool for searching Google Shopping via Tavily API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Tavily Shopping tool."""
        self.api_key = api_key or settings.tavily_api_key
        if not self.api_key:
            logger.warning("Tavily API key not provided - tool will not function")
            self.client = None
        else:
            self.client = TavilyClient(api_key=self.api_key)
    
    async def search_products(
        self, 
        query: str, 
        max_results: int = 10,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search for products using Tavily API.
        
        Args:
            query: Product search query
            max_results: Maximum number of results to return
            include_domains: List of domains to include in search
            exclude_domains: List of domains to exclude from search
        
        Returns:
            List of search results
        """
        if not self.client:
            logger.error("Tavily client not initialized - missing API key")
            return []
        
        try:
            # Use Google Shopping focused search
            search_params = {
                "query": f"{query} shopping price specs",
                "search_depth": "advanced",
                "max_results": max_results,
                "include_raw_content": True,
                "include_images": True
            }
            
            if include_domains:
                search_params["include_domains"] = include_domains
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
            
            response = await asyncio.to_thread(self.client.search, **search_params)
            
            results = []
            for item in response.get("results", []):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score"),
                    published_date=item.get("published_date")
                )
                results.append(result)
            
            logger.info(f"Found {len(results)} search results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching with Tavily: {e}")
            return []
    
    def extract_product_from_result(self, result: SearchResult) -> Optional[Product]:
        """
        Extract product information from a search result.
        
        Args:
            result: Search result to extract from
        
        Returns:
            Product object or None if extraction fails
        """
        try:
            # Basic extraction logic - could be enhanced with NLP
            content_lower = result.content.lower()
            
            # Try to extract price
            price = self._extract_price(result.content)
            
            # Try to extract brand/model from title
            brand, model = self._extract_brand_model(result.title)
            
            product = Product(
                name=result.title,
                price=price,
                url=result.url,
                description=result.content[:500],  # Truncate description
                brand=brand,
                model=model
            )
            
            return product
            
        except Exception as e:
            logger.error(f"Error extracting product from result: {e}")
            return None
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text."""
        import re
        
        # Look for price patterns like $99.99, $1,299, etc.
        price_patterns = [
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'\b(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*USD\b',
            r'Price:\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'Sale\s+price\s+\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'Now:\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    price = float(price_str)
                    # Return only reasonable prices (avoid extraction errors)
                    if 1.0 <= price <= 50000:
                        return price
                except ValueError:
                    continue
        
        return None
    
    def _extract_brand_model(self, title: str) -> tuple[Optional[str], Optional[str]]:
        """Extract brand and model from product title."""
        # Common tech brands
        brands = [
            'apple', 'samsung', 'sony', 'lg', 'dell', 'hp', 'lenovo', 
            'asus', 'acer', 'msi', 'razer', 'logitech', 'microsoft',
            'google', 'amazon', 'nvidia', 'amd', 'intel'
        ]
        
        title_lower = title.lower()
        brand = None
        
        for b in brands:
            if b in title_lower:
                brand = b.capitalize()
                break
        
        # Model extraction is more complex and domain-specific
        # For now, just return the full title as model if no brand found
        model = title if not brand else None
        
        return brand, model

    async def get_shopping_results(self, query: str) -> Dict[str, Any]:
        """
        Get comprehensive shopping results for a query.
        
        Args:
            query: Product search query
            
        Returns:
            Dictionary with products and raw results
        """
        try:
            # Search for products
            results = await self.search_products(query)
            
            # Extract products from results
            products = []
            for result in results:
                product = self.extract_product_from_result(result)
                if product:
                    products.append(product)
            
            return {
                "products": products,
                "raw_results": results,
                "query": query,
                "total_found": len(products)
            }
            
        except Exception as e:
            logger.error(f"Error in get_shopping_results: {e}")
            return {
                "products": [],
                "raw_results": [],
                "query": query,
                "total_found": 0,
                "error": str(e)
            }