"""Product researcher agent for spec and price extraction."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.core.config import settings
from src.core.models import Product, ProductCategory, SearchResult
from src.tools.tavily_shopping import TavilyShoppingTool

logger = logging.getLogger(__name__)


class ProductResearcher:
    """Agent specialized in product discovery, spec extraction, and price analysis."""

    def __init__(self):
        """Initialize the product researcher."""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not provided - enhanced analysis will be limited")
            self.llm = None
        else:
            llm_kwargs = dict(
                model=settings.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_tokens=settings.max_tokens,
            )
            if settings.openai_base_url:
                llm_kwargs["base_url"] = settings.openai_base_url
            self.llm = ChatOpenAI(**llm_kwargs)

        self.tavily_tool = TavilyShoppingTool()

    async def research_products(
        self,
        query: str,
        max_products: int = 10,
        category: Optional[ProductCategory] = None
    ) -> List[Product]:
        """
        Research products for a given query with enhanced spec extraction.

        Args:
            query: Search query for products
            max_products: Maximum number of products to return
            category: Product category filter

        Returns:
            List of Product objects with extracted specifications
        """
        try:
            logger.info(f"Researching products for query: {query}")

            # Get initial search results
            search_results = await self.tavily_tool.get_shopping_results(query)
            raw_products = search_results.get("products", [])
            raw_results = search_results.get("raw_results", [])

            if not raw_products:
                logger.warning("No products found in search results")
                return []

            # Enhance products with better spec extraction
            enhanced_products = []
            for i, product in enumerate(raw_products[:max_products]):
                try:
                    enhanced_product = await self._enhance_product(
                        product,
                        raw_results[i] if i < len(raw_results) else None,
                        query
                    )
                    if enhanced_product:
                        enhanced_products.append(enhanced_product)
                except Exception as e:
                    logger.error(f"Error enhancing product {product.name}: {e}")
                    enhanced_products.append(product)  # Use original if enhancement fails

            logger.info(f"Successfully researched {len(enhanced_products)} products")
            return enhanced_products

        except Exception as e:
            logger.error(f"Error in research_products: {e}")
            return []

    async def _enhance_product(
        self,
        product: Product,
        search_result: Optional[SearchResult],
        original_query: str
    ) -> Optional[Product]:
        """
        Enhance a product with better specification extraction using GPT-5.

        Args:
            product: Base product object
            search_result: Original search result for context
            original_query: User's original query for relevance

        Returns:
            Enhanced Product object
        """
        try:
            if not self.llm or not search_result:
                return product

            # Extract more specifications using LLM
            specs = await self._extract_specifications(search_result, original_query)

            # Enhance price extraction
            price = await self._extract_price_advanced(search_result)

            # Categorize product
            category = await self._categorize_product(product.name, search_result.content)

            # Create enhanced product
            enhanced_product = Product(
                name=product.name,
                price=price or product.price,
                currency=product.currency,
                url=product.url,
                image_url=product.image_url,
                description=self._clean_description(search_result.content),
                specifications=specs,
                category=category,
                brand=product.brand or await self._extract_brand_advanced(search_result),
                model=product.model,
                availability=True,  # Assume available if found in search
                rating=await self._extract_rating(search_result),
                review_count=await self._extract_review_count(search_result)
            )

            return enhanced_product

        except Exception as e:
            logger.error(f"Error enhancing product: {e}")
            return product

    async def _extract_specifications(
        self,
        search_result: SearchResult,
        query: str
    ) -> Dict[str, Any]:
        """Extract detailed specifications using GPT-5."""
        try:
            if not self.llm:
                return {}

            system_prompt = """You are a product specification expert. Extract key technical specifications from the product information.

            Focus on specifications most relevant to the user's query. Return a JSON object with specification names as keys and values as strings.

            Common specs to look for:
            - For laptops: processor, RAM, storage, screen size, graphics, battery life, weight
            - For phones: processor, RAM, storage, camera, battery, screen size, 5G
            - For headphones: driver size, frequency response, battery life, noise canceling
            - For electronics: power, dimensions, connectivity, warranty

            Only include specifications that are clearly stated. Use "Unknown" for missing critical specs."""

            content = f"""
            User Query: {query}
            Product Title: {search_result.title}
            Product Information: {search_result.content[:1000]}

            Extract specifications in JSON format.
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content)
            ]

            response = await self.llm.ainvoke(messages)

            # Parse JSON response (simplified for MVP)
            specs_text = response.content
            specs = self._parse_specs_from_text(specs_text)

            return specs

        except Exception as e:
            logger.error(f"Error extracting specifications: {e}")
            return {}

    async def _extract_price_advanced(self, search_result: SearchResult) -> Optional[float]:
        """Enhanced price extraction using multiple strategies."""
        try:
            content = search_result.content
            title = search_result.title

            # Multiple price patterns
            price_patterns = [
                r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,299.99
                r'USD\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # USD 1299.99
                r'Price:\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Price: $1299.99
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*dollars?',  # 1299 dollars
                r'Sale:\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Sale: $1299.99
                r'Now:\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Now: $1299.99
            ]

            # Try to extract from title first (usually more accurate)
            for pattern in price_patterns:
                match = re.search(pattern, title, re.IGNORECASE)
                if match:
                    try:
                        price_str = match.group(1).replace(',', '')
                        price = float(price_str)
                        if 10 <= price <= 50000:  # Reasonable price range
                            return price
                    except ValueError:
                        continue

            # Then try content
            for pattern in price_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    for match in matches:
                        try:
                            price_str = match.replace(',', '') if isinstance(match, str) else match
                            price = float(price_str)
                            if 10 <= price <= 50000:  # Reasonable price range
                                return price
                        except ValueError:
                            continue

            return None

        except Exception as e:
            logger.error(f"Error in advanced price extraction: {e}")
            return None

    async def _categorize_product(self, name: str, content: str) -> Optional[ProductCategory]:
        """Categorize product based on name and content."""
        try:
            combined_text = f"{name} {content}".lower()

            # Category keywords
            category_keywords = {
                ProductCategory.COMPUTERS: [
                    'laptop', 'computer', 'pc', 'desktop', 'macbook', 'chromebook',
                    'processor', 'cpu', 'ram', 'ssd', 'graphics card', 'motherboard'
                ],
                ProductCategory.ELECTRONICS: [
                    'phone', 'smartphone', 'tablet', 'ipad', 'headphones', 'earbuds',
                    'speaker', 'camera', 'tv', 'monitor', 'smart watch', 'fitness tracker'
                ],
                ProductCategory.HOME: [
                    'furniture', 'chair', 'desk', 'table', 'bed', 'sofa',
                    'kitchen', 'appliance', 'vacuum', 'air purifier'
                ]
            }

            # Score each category
            category_scores = {}
            for category, keywords in category_keywords.items():
                score = sum(1 for keyword in keywords if keyword in combined_text)
                if score > 0:
                    category_scores[category] = score

            # Return category with highest score
            if category_scores:
                return max(category_scores.keys(), key=lambda k: category_scores[k])

            return ProductCategory.OTHER

        except Exception as e:
            logger.error(f"Error categorizing product: {e}")
            return ProductCategory.OTHER

    async def _extract_brand_advanced(self, search_result: SearchResult) -> Optional[str]:
        """Enhanced brand extraction."""
        try:
            text = f"{search_result.title} {search_result.content}".lower()

            # Extended brand list
            brands = [
                # Tech brands
                'apple', 'samsung', 'google', 'microsoft', 'sony', 'lg', 'htc', 'oneplus',
                # Computer brands
                'dell', 'hp', 'lenovo', 'asus', 'acer', 'msi', 'razer', 'alienware',
                'macbook', 'thinkpad', 'surface', 'inspiron', 'pavilion', 'elitebook',
                # Gaming brands
                'nvidia', 'amd', 'intel', 'corsair', 'logitech', 'steelseries',
                # Audio brands
                'bose', 'sennheiser', 'audio-technica', 'beyerdynamic', 'shure',
                'beats', 'airpods', 'jabra', 'plantronics'
            ]

            for brand in brands:
                if brand in text:
                    return brand.replace('-', ' ').title()

            return None

        except Exception as e:
            logger.error(f"Error extracting brand: {e}")
            return None

    async def _extract_rating(self, search_result: SearchResult) -> Optional[float]:
        """Extract product rating from search result."""
        try:
            content = search_result.content

            # Rating patterns
            rating_patterns = [
                r'(\d\.\d)\s*(?:out of|/)?\s*5\s*star',  # 4.5 out of 5 stars
                r'(\d\.\d)\s*/\s*5',  # 4.5/5
                r'rating:\s*(\d\.\d)',  # Rating: 4.5
                r'(\d\.\d)\s*star',  # 4.5 stars
            ]

            for pattern in rating_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        rating = float(match.group(1))
                        if 0 <= rating <= 5:
                            return rating
                    except ValueError:
                        continue

            return None

        except Exception as e:
            logger.error(f"Error extracting rating: {e}")
            return None

    async def _extract_review_count(self, search_result: SearchResult) -> int:
        """Extract review count from search result."""
        try:
            content = search_result.content

            # Review count patterns
            review_patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*reviews?',  # 1,234 reviews
                r'(\d{1,3}(?:,\d{3})*)\s*customer\s*reviews?',  # customer reviews
                r'(\d{1,3}(?:,\d{3})*)\s*ratings?',  # ratings
            ]

            for pattern in review_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        count_str = match.group(1).replace(',', '')
                        count = int(count_str)
                        if count >= 0:
                            return count
                    except ValueError:
                        continue

            return 0

        except Exception as e:
            logger.error(f"Error extracting review count: {e}")
            return 0

    def _parse_specs_from_text(self, specs_text: str) -> Dict[str, Any]:
        """Parse specifications from LLM response text."""
        try:
            # Try to extract JSON-like content
            import json

            # Look for JSON patterns in the response
            json_start = specs_text.find('{')
            json_end = specs_text.rfind('}')

            if json_start != -1 and json_end != -1:
                json_str = specs_text[json_start:json_end + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # Fallback: parse key-value pairs from text
            specs = {}
            lines = specs_text.split('\n')

            for line in lines:
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().strip('"\'')
                        value = parts[1].strip().strip(',').strip('"\'')
                        if key and value and value.lower() != 'unknown':
                            specs[key] = value

            return specs

        except Exception as e:
            logger.error(f"Error parsing specs from text: {e}")
            return {}

    def _clean_description(self, content: str) -> str:
        """Clean and truncate product description."""
        try:
            # Remove extra whitespace and truncate
            cleaned = ' '.join(content.split())
            return cleaned[:500] + '...' if len(cleaned) > 500 else cleaned

        except Exception as e:
            logger.error(f"Error cleaning description: {e}")
            return content[:500] + '...' if len(content) > 500 else content

    async def compare_products(
        self,
        products: List[Product],
        comparison_criteria: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple products based on specified criteria.

        Args:
            products: List of products to compare
            comparison_criteria: List of criteria to focus comparison on

        Returns:
            Comparison analysis
        """
        try:
            if not products or not self.llm:
                return {"error": "No products to compare or LLM not available"}

            if comparison_criteria is None:
                comparison_criteria = ["price", "specifications", "ratings", "value"]

            system_prompt = """You are a product comparison expert. Compare these products objectively:
            1. Create a side-by-side comparison
            2. Highlight key differences
            3. Identify best value options
            4. Note any standout features or concerns

            Focus on the specified comparison criteria."""

            products_data = self._format_products_for_comparison(products)
            criteria_text = ", ".join(comparison_criteria)

            content = f"""
            Comparison Criteria: {criteria_text}

            Products to Compare:
            {products_data}

            Provide a structured comparison analysis.
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content)
            ]

            response = await self.llm.ainvoke(messages)

            return {
                "comparison": response.content,
                "products_compared": len(products),
                "criteria": comparison_criteria,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in compare_products: {e}")
            return {"error": f"Comparison failed: {str(e)}"}

    def _format_products_for_comparison(self, products: List[Product]) -> str:
        """Format products for comparison analysis."""
        formatted = []

        for i, product in enumerate(products, 1):
            specs_text = "\n".join([f"   - {k}: {v}" for k, v in product.specifications.items()])

            formatted.append(f"""
Product {i}: {product.name}
- Price: ${product.price or 'N/A'}
- Brand: {product.brand or 'Unknown'}
- Category: {product.category or 'Unknown'}
- Rating: {product.rating or 'N/A'} ({product.review_count} reviews)
- Specifications:
{specs_text}
- Description: {product.description[:200] if product.description else 'N/A'}...
            """)

        return "\n" + "="*50 + "\n".join(formatted)