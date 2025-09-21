"""Review analyzer agent for sentiment analysis and authenticity filtering."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime
from collections import Counter

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.core.config import settings
from src.core.models import Review, SearchResult

logger = logging.getLogger(__name__)


class ReviewAnalyzer:
    """Agent specialized in review analysis, sentiment detection, and authenticity filtering."""

    def __init__(self):
        """Initialize the review analyzer."""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not provided - review analysis will be limited")
            self.llm = None
        else:
            self.llm = ChatOpenAI(
                model=settings.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_tokens=settings.max_tokens,
                model_kwargs={
                    "reasoning_effort": settings.reasoning_effort,
                    "service_tier": settings.service_tier
                }
            )

    async def analyze_reviews(
        self,
        search_results: List[SearchResult],
        product_name: str,
        focus_areas: List[str] = None
    ) -> List[Review]:
        """
        Analyze reviews from search results with sentiment and authenticity assessment.

        Args:
            search_results: Search results containing review content
            product_name: Name of the product being reviewed
            focus_areas: Specific aspects to focus analysis on

        Returns:
            List of analyzed Review objects
        """
        try:
            logger.info(f"Analyzing reviews for product: {product_name}")

            # Extract review content from search results
            review_texts = self._extract_review_content(search_results)

            if not review_texts:
                logger.warning("No review content found in search results")
                return []

            # Analyze each review
            analyzed_reviews = []
            for review_text in review_texts[:10]:  # Limit to 10 reviews for MVP
                try:
                    review = await self._analyze_single_review(
                        review_text,
                        product_name,
                        focus_areas
                    )
                    if review:
                        analyzed_reviews.append(review)
                except Exception as e:
                    logger.error(f"Error analyzing single review: {e}")

            logger.info(f"Successfully analyzed {len(analyzed_reviews)} reviews")
            return analyzed_reviews

        except Exception as e:
            logger.error(f"Error in analyze_reviews: {e}")
            return []

    def _extract_review_content(self, search_results: List[SearchResult]) -> List[str]:
        """Extract review content from search results."""
        try:
            review_texts = []

            for result in search_results:
                content = result.content
                title = result.title

                # Check if content contains review indicators
                review_indicators = [
                    'review', 'rating', 'stars', 'customer', 'buyer', 'purchased',
                    'pros and cons', 'verdict', 'experience', 'quality', 'performance',
                    'recommend', 'satisfied', 'disappointed', 'excellent', 'terrible'
                ]

                content_lower = content.lower()
                if any(indicator in content_lower for indicator in review_indicators):
                    # Extract review-like sentences
                    sentences = self._extract_review_sentences(content)
                    review_texts.extend(sentences)

            # Remove duplicates and filter short content
            unique_reviews = list(set(review_texts))
            filtered_reviews = [
                review for review in unique_reviews
                if len(review.split()) >= 10  # At least 10 words
            ]

            return filtered_reviews[:20]  # Limit to 20 review texts

        except Exception as e:
            logger.error(f"Error extracting review content: {e}")
            return []

    def _extract_review_sentences(self, content: str) -> List[str]:
        """Extract review-like sentences from content."""
        try:
            sentences = re.split(r'[.!?]+', content)

            review_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:  # Skip very short sentences
                    continue

                # Check if sentence contains review language
                review_patterns = [
                    r'\b(love|hate|recommend|bought|purchased|using|tried)\b',
                    r'\b(excellent|terrible|amazing|awful|perfect|horrible)\b',
                    r'\b(quality|performance|battery|screen|sound|price)\b',
                    r'\b(pros|cons|advantage|disadvantage|problem|issue)\b',
                    r'\b(satisfied|disappointed|impressed|frustrated)\b'
                ]

                if any(re.search(pattern, sentence, re.IGNORECASE) for pattern in review_patterns):
                    review_sentences.append(sentence)

            return review_sentences[:5]  # Limit sentences per content block

        except Exception as e:
            logger.error(f"Error extracting review sentences: {e}")
            return []

    async def _analyze_single_review(
        self,
        review_text: str,
        product_name: str,
        focus_areas: List[str] = None
    ) -> Optional[Review]:
        """Analyze a single review for sentiment and authenticity."""
        try:
            if not self.llm:
                # Basic analysis without LLM
                return Review(
                    text=review_text[:500],
                    sentiment=self._basic_sentiment_analysis(review_text),
                    verified=False,
                    date=None,
                    helpful_count=0
                )

            # Advanced analysis with GPT-5
            sentiment = await self._analyze_sentiment(review_text, focus_areas)
            authenticity_score = await self._assess_authenticity(review_text)
            rating = self._extract_rating_from_text(review_text)

            return Review(
                text=review_text[:500],  # Truncate long reviews
                rating=rating,
                sentiment=sentiment,
                verified=authenticity_score > 0.7,  # Consider authentic if score > 0.7
                date=self._extract_date_from_text(review_text),
                helpful_count=self._extract_helpful_count(review_text)
            )

        except Exception as e:
            logger.error(f"Error analyzing single review: {e}")
            return None

    async def _analyze_sentiment(
        self,
        review_text: str,
        focus_areas: List[str] = None
    ) -> str:
        """Analyze sentiment of review text using GPT-5."""
        try:
            system_prompt = """You are a sentiment analysis expert. Analyze the sentiment of this product review.

            Classify sentiment as one of:
            - positive: Overall positive experience, recommends product
            - negative: Overall negative experience, does not recommend
            - mixed: Has both positive and negative aspects
            - neutral: Factual information without strong opinion

            Consider the overall tone and conclusion of the review."""

            focus_text = ""
            if focus_areas:
                focus_text = f"\nPay special attention to mentions of: {', '.join(focus_areas)}"

            content = f"""
            Review Text: {review_text}
            {focus_text}

            Provide sentiment classification (positive/negative/mixed/neutral) and brief reasoning.
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content)
            ]

            response = await self.llm.ainvoke(messages)
            response_text = response.content.lower()

            # Extract sentiment from response
            if 'positive' in response_text:
                return 'positive'
            elif 'negative' in response_text:
                return 'negative'
            elif 'mixed' in response_text:
                return 'mixed'
            else:
                return 'neutral'

        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return self._basic_sentiment_analysis(review_text)

    async def _assess_authenticity(self, review_text: str) -> float:
        """Assess authenticity of review (0.0 to 1.0 score)."""
        try:
            if not self.llm:
                return self._basic_authenticity_check(review_text)

            system_prompt = """You are a review authenticity expert. Assess if this review appears genuine.

            Consider these factors:
            - Specific details vs generic language
            - Natural writing style vs repetitive phrases
            - Balanced perspective vs extreme opinions
            - Contextual relevance to the product
            - Personal experience indicators

            Rate authenticity from 0.0 (definitely fake) to 1.0 (definitely genuine)."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Review to assess: {review_text}")
            ]

            response = await self.llm.ainvoke(messages)

            # Extract score from response
            score_match = re.search(r'(\d\.\d)', response.content)
            if score_match:
                return float(score_match.group(1))

            # Fallback scoring based on response keywords
            response_lower = response.content.lower()
            if 'genuine' in response_lower or 'authentic' in response_lower:
                return 0.8
            elif 'suspicious' in response_lower or 'fake' in response_lower:
                return 0.3
            else:
                return 0.6

        except Exception as e:
            logger.error(f"Error assessing authenticity: {e}")
            return 0.5  # Neutral score on error

    def _basic_sentiment_analysis(self, text: str) -> str:
        """Basic sentiment analysis using keyword matching."""
        try:
            text_lower = text.lower()

            positive_words = [
                'excellent', 'amazing', 'fantastic', 'perfect', 'love', 'recommend',
                'great', 'awesome', 'outstanding', 'satisfied', 'happy', 'impressed'
            ]

            negative_words = [
                'terrible', 'awful', 'horrible', 'hate', 'disappointed', 'frustrated',
                'poor', 'bad', 'worst', 'useless', 'broken', 'defective'
            ]

            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)

            if positive_count > negative_count:
                return 'positive'
            elif negative_count > positive_count:
                return 'negative'
            elif positive_count > 0 and negative_count > 0:
                return 'mixed'
            else:
                return 'neutral'

        except Exception as e:
            logger.error(f"Error in basic sentiment analysis: {e}")
            return 'neutral'

    def _basic_authenticity_check(self, text: str) -> float:
        """Basic authenticity check using heuristics."""
        try:
            score = 0.5  # Start with neutral

            # Positive indicators
            if len(text.split()) > 20:  # Detailed review
                score += 0.1
            if any(word in text.lower() for word in ['purchased', 'bought', 'using', 'tried']):
                score += 0.2
            if re.search(r'\b(month|week|day|year)\b', text.lower()):  # Time references
                score += 0.1

            # Negative indicators
            if text.count('!') > 3:  # Excessive exclamation
                score -= 0.2
            if len(set(text.split())) / len(text.split()) < 0.7:  # High repetition
                score -= 0.2

            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error in basic authenticity check: {e}")
            return 0.5

    def _extract_rating_from_text(self, text: str) -> Optional[float]:
        """Extract numerical rating from review text."""
        try:
            # Rating patterns
            patterns = [
                r'(\d)\s*out\s*of\s*5',
                r'(\d)/5',
                r'(\d)\s*star',
                r'rating:\s*(\d)',
                r'(\d\.\d)\s*star'
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rating = float(match.group(1))
                    if 0 <= rating <= 5:
                        return rating

            return None

        except Exception as e:
            logger.error(f"Error extracting rating: {e}")
            return None

    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extract date from review text."""
        try:
            # Simple date patterns
            date_patterns = [
                r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # MM/DD/YYYY
                r'\b(\w+ \d{1,2}, \d{4})\b',     # Month DD, YYYY
                r'\b(\d{4}-\d{2}-\d{2})\b'       # YYYY-MM-DD
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1)

            return None

        except Exception as e:
            logger.error(f"Error extracting date: {e}")
            return None

    def _extract_helpful_count(self, text: str) -> int:
        """Extract helpful count from review text."""
        try:
            # Helpful patterns
            patterns = [
                r'(\d+)\s*people\s*found\s*helpful',
                r'helpful\s*\((\d+)\)',
                r'(\d+)\s*helpful'
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return int(match.group(1))

            return 0

        except Exception as e:
            logger.error(f"Error extracting helpful count: {e}")
            return 0

    async def summarize_reviews(
        self,
        reviews: List[Review],
        focus_areas: List[str] = None
    ) -> Dict[str, Any]:
        """
        Summarize multiple reviews into key insights.

        Args:
            reviews: List of analyzed reviews
            focus_areas: Specific aspects to focus summary on

        Returns:
            Summary analysis with key insights
        """
        try:
            if not reviews:
                return {"error": "No reviews to summarize"}

            # Sentiment distribution
            sentiment_counts = Counter(review.sentiment for review in reviews)

            # Rating distribution
            ratings = [review.rating for review in reviews if review.rating is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            # Authenticity stats
            verified_count = sum(1 for review in reviews if review.verified)
            authenticity_rate = verified_count / len(reviews) if reviews else 0

            # Generate summary using LLM if available
            summary_text = await self._generate_review_summary(reviews, focus_areas)

            return {
                "total_reviews": len(reviews),
                "sentiment_distribution": dict(sentiment_counts),
                "average_rating": round(avg_rating, 1) if avg_rating else None,
                "authenticity_rate": round(authenticity_rate, 2),
                "verified_reviews": verified_count,
                "summary": summary_text,
                "focus_areas": focus_areas or [],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error summarizing reviews: {e}")
            return {"error": f"Summary generation failed: {str(e)}"}

    async def _generate_review_summary(
        self,
        reviews: List[Review],
        focus_areas: List[str] = None
    ) -> str:
        """Generate summary of reviews using GPT-5."""
        try:
            if not self.llm:
                return self._basic_review_summary(reviews)

            # Prepare review data for analysis
            review_data = self._prepare_reviews_for_summary(reviews)
            focus_text = ""
            if focus_areas:
                focus_text = f"\nFocus particularly on: {', '.join(focus_areas)}"

            system_prompt = f"""You are a review summary expert. Analyze these product reviews and provide:

            1. Key themes and common points
            2. Main strengths mentioned by customers
            3. Common complaints or issues
            4. Overall customer satisfaction level
            5. Notable patterns or insights

            Keep the summary concise but comprehensive.{focus_text}"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Reviews to summarize:\n{review_data}")
            ]

            response = await self.llm.ainvoke(messages)
            return response.content

        except Exception as e:
            logger.error(f"Error generating review summary: {e}")
            return self._basic_review_summary(reviews)

    def _basic_review_summary(self, reviews: List[Review]) -> str:
        """Generate basic summary without LLM."""
        try:
            sentiment_counts = Counter(review.sentiment for review in reviews)
            total = len(reviews)

            summary_parts = [f"Analysis of {total} reviews:"]

            # Sentiment breakdown
            for sentiment, count in sentiment_counts.most_common():
                percentage = (count / total) * 100
                summary_parts.append(f"- {sentiment.title()}: {count} reviews ({percentage:.1f}%)")

            # Overall assessment
            if sentiment_counts.get('positive', 0) > sentiment_counts.get('negative', 0):
                summary_parts.append("Overall sentiment appears positive.")
            elif sentiment_counts.get('negative', 0) > sentiment_counts.get('positive', 0):
                summary_parts.append("Overall sentiment appears negative.")
            else:
                summary_parts.append("Sentiment appears mixed or neutral.")

            return "\n".join(summary_parts)

        except Exception as e:
            logger.error(f"Error in basic review summary: {e}")
            return "Unable to generate review summary."

    def _prepare_reviews_for_summary(self, reviews: List[Review]) -> str:
        """Prepare review data for LLM summary."""
        try:
            formatted_reviews = []

            for i, review in enumerate(reviews[:10], 1):  # Limit to 10 for context
                review_info = [
                    f"Review {i}:",
                    f"Sentiment: {review.sentiment}",
                    f"Text: {review.text[:200]}..."
                ]

                if review.rating:
                    review_info.append(f"Rating: {review.rating}/5")

                formatted_reviews.append("\n".join(review_info))

            return "\n\n".join(formatted_reviews)

        except Exception as e:
            logger.error(f"Error preparing reviews for summary: {e}")
            return "Error formatting reviews for analysis."