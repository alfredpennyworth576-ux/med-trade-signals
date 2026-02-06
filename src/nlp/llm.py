"""
LLM Integration for Advanced NLP Analysis
Uses OpenAI GPT models for enhanced entity extraction and sentiment analysis
"""
import re
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sys
sys.path.insert(0, str(__file__).replace('nlp/llm.py', ''))
from utils.config import config
from utils.logger import logger

# Try to import openai, fallback if not available
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class LLMAnalyzer:
    """Advanced NLP analysis using OpenAI GPT models"""
    
    # Prompt templates for medical/financial analysis
    ANALYSIS_PROMPT = """You are a medical trading signal analyst. Analyze the following text and extract structured information.

TEXT:
{text}

Respond with a JSON object containing:
{{
    "sentiment": "positive" | "negative" | "neutral",
    "sentiment_confidence": 0.0-1.0,
    "entities": [
        {{
            "name": "entity name",
            "type": "drug | company | condition | trial | biomarker | fda_decision",
            "ticker": "ticker symbol if applicable",
            "confidence": 0.0-1.0
        }}
    ],
    "clinical_analysis": {{
        "trial_phase": "Phase X" | null,
        "trial_status": "recruiting | completed | ongoing | terminated | null",
        "endpoint_met": true | false | null,
        "efficacy_summary": "brief summary of efficacy results",
        "safety_concerns": "any safety signals mentioned",
        "indication": "disease/condition being treated"
    }},
    "trading_signal": {{
        "signal_type": "FDA_APPROVAL | FDA_REJECTION | TRIAL_SUCCESS | TRIAL_FAILURE | BREAKTHROUGH_DESIGNATION | null",
        "confidence": 0.0-1.0,
        "target_upside": "estimated % upside if applicable",
        "target_downside": "estimated % downside if applicable"
    }},
    "key_insights": ["list of key takeaways"],
    "source_quality": "high | medium | low"
}}

Focus on factual extraction. Be conservative with confidence scores."""

    SUMMARY_PROMPT = """Summarize this medical/news text in 2-3 sentences, highlighting trading-relevant information:

{text}

Output:"""

    def __init__(self, model: str = "gpt-3.5-turbo", cache_hours: int = 24):
        """
        Initialize LLM analyzer
        
        Args:
            model: OpenAI model to use (gpt-4o, gpt-4, gpt-3.5-turbo)
            cache_hours: How long to cache results
        """
        self.model = model
        self.cache_hours = cache_hours
        self.cache = {}
        self.cache_dir = config.PROCESSED_DIR
        self._load_cache()
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        return f"llm_analysis_{text_hash}"
    
    def _load_cache(self):
        """Load cached results"""
        import os
        cache_file = f"{self.cache_dir}/llm_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Filter out expired entries
                    cutoff = datetime.utcnow() - timedelta(hours=self.cache_hours)
                    self.cache = {
                        k: v for k, v in data.items()
                        if datetime.fromisoformat(v['timestamp']) > cutoff
                    }
            except Exception as e:
                logger.warning(f"Failed to load LLM cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk"""
        import os
        cache_file = f"{self.cache_dir}/llm_cache.json"
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save LLM cache: {e}")
    
    def _call_openai(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Call OpenAI API"""
        if not config.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            return None
        
        try:
            client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical trading signal analyst. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI rate limit: {e}")
            return None
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI: {e}")
            return None
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict]:
        """Extract JSON from API response"""
        try:
            # Try direct parsing first
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in response
        try:
            # Look for JSON between code blocks or braces
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass
        
        return None
    
    def analyze_text(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Analyze text using LLM
        
        Args:
            text: Text to analyze
            use_cache: Whether to use cached results
            
        Returns:
            Dict containing analysis results
        """
        # Check cache
        cache_key = self._get_cache_key(text)
        if use_cache and cache_key in self.cache:
            logger.debug(f"Using cached analysis for {cache_key}")
            return self.cache[cache_key]
        
        # Call OpenAI
        prompt = self.ANALYSIS_PROMPT.format(text=text[:8000])  # Truncate if too long
        response = self._call_openai(prompt)
        
        if response:
            result = self._extract_json_from_response(response)
            if result:
                result['analysis_source'] = 'llm'
                result['model'] = self.model
                result['timestamp'] = datetime.utcnow().isoformat()
                self.cache[cache_key] = result
                self._save_cache()
                return result
        
        # Fallback to None if OpenAI fails
        return {
            "error": "LLM analysis failed",
            "analysis_source": "fallback",
            "sentiment": "neutral",
            "confidence": 0.5
        }
    
    def summarize(self, text: str) -> str:
        """Generate a summary of the text"""
        prompt = self.SUMMARY_PROMPT.format(text=text[:4000])
        response = self._call_openai(prompt, max_tokens=300)
        
        if response:
            return response.strip()
        
        # Fallback: return first 200 characters
        return text[:200] + "..." if len(text) > 200 else text
    
    def batch_analyze(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze multiple texts"""
        results = []
        for text in texts:
            result = self.analyze_text(text)
            results.append(result)
        return results


class FallbackAnalyzer:
    """Fallback regex-based analysis when LLM is unavailable"""
    
    def __init__(self):
        self.extractor = None
        self.sentiment_analyzer = None
        # Import here to avoid circular imports
        from .utils import EnhancedEntityExtractor, EnhancedSentimentAnalyzer
        self.extractor = EnhancedEntityExtractor()
        self.sentiment_analyzer = EnhancedSentimentAnalyzer()
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """Analyze using regex patterns"""
        entities = self.extractor.extract_entities(text)
        sentiment = self.sentiment_analyzer.get_clinical_sentiment(text)
        
        # Convert entities to dict format
        entity_list = [
            {
                "name": e.text,
                "type": e.entity_type,
                "ticker": e.ticker,
                "confidence": e.confidence
            }
            for e in entities
        ]
        
        # Determine trading signal
        signal_type = None
        if sentiment.get("signals"):
            signal_type = sentiment["signals"][0] if sentiment["signals"] else None
        
        return {
            "sentiment": sentiment["sentiment"],
            "sentiment_confidence": sentiment["confidence"],
            "entities": entity_list,
            "clinical_analysis": {
                "trial_phase": None,
                "trial_status": None,
                "endpoint_met": None,
                "efficacy_summary": None,
                "safety_concerns": None,
                "indication": None
            },
            "trading_signal": {
                "signal_type": signal_type,
                "confidence": sentiment["confidence"],
                "target_upside": None,
                "target_downside": None
            },
            "key_insights": [],
            "source_quality": "medium",
            "analysis_source": "regex_fallback"
        }


def analyze_text_with_llm(text: str, prefer_llm: bool = True) -> Dict[str, Any]:
    """
    Analyze text with LLM, falling back to regex if unavailable
    
    Args:
        text: Text to analyze
        prefer_llm: If True, try LLM first; if False, use regex only
        
    Returns:
        Dict containing analysis results
    """
    # If LLM not preferred or unavailable, use fallback
    if not prefer_llm or not config.OPENAI_API_KEY:
        fallback = FallbackAnalyzer()
        return fallback.analyze(text)
    
    # Try LLM first
    llm = LLMAnalyzer()
    result = llm.analyze_text(text)
    
    # Check if LLM failed
    if result.get("analysis_source") == "fallback":
        fallback = FallbackAnalyzer()
        fallback_result = fallback.analyze(text)
        # Merge results
        fallback_result["llm_error"] = result.get("error")
        return fallback_result
    
    return result


# Convenience function
def quick_analyze(text: str) -> Dict[str, Any]:
    """
    Quick analysis using best available method
    
    Returns simplified result with key fields
    """
    result = analyze_text_with_llm(text)
    
    return {
        "sentiment": result.get("sentiment", "neutral"),
        "confidence": result.get("sentiment_confidence", 0.5),
        "entities": [e.get("name") for e in result.get("entities", [])],
        "tickers": list(set(e.get("ticker") for e in result.get("entities", []) if e.get("ticker"))),
        "signal": result.get("trading_signal", {}).get("signal_type"),
        "signal_confidence": result.get("trading_signal", {}).get("confidence", 0),
        "source": result.get("analysis_source", "unknown")
    }


if __name__ == "__main__":
    # Test the analyzer
    sample_text = """
    Pfizer announced positive Phase 3 results for their breast cancer drug.
    The trial met its primary endpoint with a 40% improvement in progression-free survival.
    HR=0.62, p<0.001. FDA breakthrough therapy designation granted.
    """
    
    print("=== Quick Analysis ===")
    print(quick_analyze(sample_text))
