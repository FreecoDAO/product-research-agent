"""Pydantic data models for the Product Research Agent."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class PriceRange(str, Enum):
    """Price range categories."""
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    PREMIUM = "premium"


class ProductCategory(str, Enum):
    """Product categories."""
    ELECTRONICS = "electronics"
    COMPUTERS = "computers"
    HOME = "home"
    CLOTHING = "clothing"
    OTHER = "other"


class Product(BaseModel):
    """Product model with specifications and pricing."""
    name: str
    price: Optional[float] = None
    currency: str = "USD"
    url: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)
    category: Optional[ProductCategory] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    availability: bool = True
    rating: Optional[float] = None
    review_count: int = 0


class Review(BaseModel):
    """Customer review model."""
    text: str
    rating: Optional[float] = None
    date: Optional[str] = None
    verified: bool = False
    helpful_count: int = 0
    sentiment: Optional[str] = None  # positive, negative, neutral


class SearchResult(BaseModel):
    """Search result from Tavily API."""
    title: str
    url: str
    content: str
    score: Optional[float] = None
    published_date: Optional[str] = None


class ResearchQuery(BaseModel):
    """Research query input."""
    query: str
    category: Optional[ProductCategory] = None
    price_range: Optional[PriceRange] = None
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    features: List[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    """Complete research result."""
    query: ResearchQuery
    products: List[Product] = Field(default_factory=list)
    reviews: List[Review] = Field(default_factory=list)
    summary: Optional[str] = None
    recommendation: Optional[str] = None
    alternatives: List[Product] = Field(default_factory=list)
    timestamp: Optional[str] = None
    total_research_time: Optional[float] = None