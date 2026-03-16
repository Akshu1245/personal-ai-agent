"""
============================================================
AKSHAY AI CORE — Truth Checker
============================================================
Fact verification and claim validation system.
============================================================
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.config import settings
from core.utils.logger import get_logger

logger = get_logger("brain.truth_checker")


class VerificationStatus(str, Enum):
    """Verification result status."""
    VERIFIED = "verified"
    LIKELY_TRUE = "likely_true"
    UNCERTAIN = "uncertain"
    LIKELY_FALSE = "likely_false"
    FALSE = "false"
    UNVERIFIABLE = "unverifiable"


@dataclass
class Source:
    """A source for fact verification."""
    name: str
    url: Optional[str] = None
    reliability: float = 0.5  # 0-1 scale
    content: Optional[str] = None
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VerificationResult:
    """Result of fact verification."""
    claim: str
    status: VerificationStatus
    confidence: float  # 0-1
    sources: List[Source] = field(default_factory=list)
    explanation: str = ""
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    verified_at: datetime = field(default_factory=datetime.utcnow)


class TruthChecker:
    """
    Fact verification system.
    
    Features:
    - Claim extraction
    - Multi-source verification
    - Confidence scoring
    - Evidence aggregation
    - Source reliability tracking
    """
    
    def __init__(self):
        self._source_reliability: Dict[str, float] = {}
        self._cache: Dict[str, VerificationResult] = {}
        self._cache_ttl = 3600  # 1 hour
    
    async def verify(
        self,
        text: str,
        deep_check: bool = False,
        max_sources: int = 5,
    ) -> List[VerificationResult]:
        """
        Verify claims in text.
        
        Args:
            text: Text containing claims to verify
            deep_check: Whether to do thorough verification
            max_sources: Maximum sources to check
            
        Returns:
            List of verification results
        """
        # Step 1: Extract claims
        claims = await self._extract_claims(text)
        
        if not claims:
            return []
        
        # Step 2: Verify each claim
        results = []
        for claim in claims:
            # Check cache
            cache_key = claim.lower().strip()
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if (datetime.utcnow() - cached.verified_at).total_seconds() < self._cache_ttl:
                    results.append(cached)
                    continue
            
            result = await self._verify_claim(claim, deep_check, max_sources)
            results.append(result)
            
            # Cache result
            self._cache[cache_key] = result
        
        return results
    
    async def _extract_claims(self, text: str) -> List[str]:
        """Extract verifiable claims from text."""
        claims = []
        
        # Simple sentence splitting
        import re
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Filter for factual claims
            # Skip questions, commands, opinions
            if sentence.endswith('?'):
                continue
            
            if any(sentence.lower().startswith(w) for w in ['please', 'can you', 'could you', 'would you']):
                continue
            
            # Check for factual indicators
            factual_indicators = [
                'is', 'are', 'was', 'were', 'has', 'have', 'had',
                'will', 'can', 'could', 'should',
                'always', 'never', 'every', 'all', 'none',
                'percent', '%', 'million', 'billion',
            ]
            
            if any(ind in sentence.lower() for ind in factual_indicators):
                claims.append(sentence)
        
        # Use LLM for better extraction if available
        if settings.AI_PROVIDER and claims:
            try:
                claims = await self._llm_extract_claims(text)
            except Exception as e:
                logger.warning("LLM claim extraction failed", error=str(e))
        
        return claims[:10]  # Limit claims
    
    async def _llm_extract_claims(self, text: str) -> List[str]:
        """Use LLM to extract verifiable claims."""
        from core.brain.llm_connector import llm, Message
        
        system_prompt = """Extract verifiable factual claims from the text.
Return only objective, checkable statements.
Exclude opinions, questions, and subjective statements.
Return as JSON array of strings."""
        
        response = await llm.complete(
            messages=[
                Message(role="system", content=system_prompt),
                Message(role="user", content=text),
            ],
            max_tokens=500,
            temperature=0.1,
        )
        
        import json
        try:
            return json.loads(response.content)
        except:
            return []
    
    async def _verify_claim(
        self,
        claim: str,
        deep_check: bool,
        max_sources: int,
    ) -> VerificationResult:
        """Verify a single claim."""
        sources = []
        supporting = []
        contradicting = []
        
        # Step 1: Search for evidence
        if deep_check:
            sources = await self._search_sources(claim, max_sources)
        
        # Step 2: Analyze evidence
        for source in sources:
            analysis = await self._analyze_evidence(claim, source)
            
            if analysis.get("supports"):
                supporting.append(f"{source.name}: {analysis.get('reason', '')}")
            elif analysis.get("contradicts"):
                contradicting.append(f"{source.name}: {analysis.get('reason', '')}")
        
        # Step 3: Calculate confidence
        status, confidence = self._calculate_verdict(supporting, contradicting, sources)
        
        # Step 4: Generate explanation
        explanation = await self._generate_explanation(
            claim, status, supporting, contradicting
        )
        
        return VerificationResult(
            claim=claim,
            status=status,
            confidence=confidence,
            sources=sources,
            explanation=explanation,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
        )
    
    async def _search_sources(
        self,
        claim: str,
        max_sources: int,
    ) -> List[Source]:
        """Search for verification sources."""
        sources = []
        
        # In production, this would:
        # 1. Search fact-checking APIs (Google Fact Check, Snopes API)
        # 2. Search Wikipedia
        # 3. Search news sources
        # 4. Search academic databases
        
        # Simulated source search
        try:
            # Try web search via plugin
            from plugins import plugin_manager
            
            result = await plugin_manager.execute_plugin(
                plugin_id="web_automation",
                command="scrape",
                params={
                    "url": f"https://www.google.com/search?q={claim}",
                    "selector": ".g",
                },
                user_id="truth_checker",
                timeout=30,
            )
            
            if result.get("status") == "success":
                for item in result.get("data", [])[:max_sources]:
                    sources.append(Source(
                        name="Web Search",
                        content=str(item),
                        reliability=0.5,
                    ))
                    
        except Exception as e:
            logger.warning("Source search failed", error=str(e))
        
        return sources
    
    async def _analyze_evidence(
        self,
        claim: str,
        source: Source,
    ) -> Dict[str, Any]:
        """Analyze if source supports or contradicts claim."""
        if not source.content:
            return {"inconclusive": True}
        
        # Use LLM for analysis
        if settings.AI_PROVIDER:
            try:
                from core.brain.llm_connector import llm, Message
                
                prompt = f"""Analyze if this evidence supports or contradicts the claim.

Claim: {claim}

Evidence: {source.content[:1000]}

Respond with JSON: {{"supports": true/false, "contradicts": true/false, "reason": "brief explanation"}}"""
                
                response = await llm.complete(
                    messages=[Message(role="user", content=prompt)],
                    max_tokens=200,
                    temperature=0.1,
                )
                
                import json
                return json.loads(response.content)
                
            except Exception as e:
                logger.warning("Evidence analysis failed", error=str(e))
        
        # Simple keyword matching fallback
        claim_words = set(claim.lower().split())
        content_lower = source.content.lower()
        
        matches = sum(1 for w in claim_words if w in content_lower)
        support_ratio = matches / len(claim_words) if claim_words else 0
        
        return {
            "supports": support_ratio > 0.5,
            "contradicts": False,
            "reason": f"{matches}/{len(claim_words)} keywords found",
        }
    
    def _calculate_verdict(
        self,
        supporting: List[str],
        contradicting: List[str],
        sources: List[Source],
    ) -> tuple[VerificationStatus, float]:
        """Calculate final verdict and confidence."""
        if not sources:
            return VerificationStatus.UNVERIFIABLE, 0.0
        
        total = len(supporting) + len(contradicting)
        if total == 0:
            return VerificationStatus.UNCERTAIN, 0.3
        
        support_ratio = len(supporting) / total
        
        if support_ratio >= 0.8:
            status = VerificationStatus.VERIFIED
            confidence = min(0.95, 0.7 + support_ratio * 0.25)
        elif support_ratio >= 0.6:
            status = VerificationStatus.LIKELY_TRUE
            confidence = 0.5 + support_ratio * 0.3
        elif support_ratio >= 0.4:
            status = VerificationStatus.UNCERTAIN
            confidence = 0.4
        elif support_ratio >= 0.2:
            status = VerificationStatus.LIKELY_FALSE
            confidence = 0.5 + (1 - support_ratio) * 0.3
        else:
            status = VerificationStatus.FALSE
            confidence = min(0.95, 0.7 + (1 - support_ratio) * 0.25)
        
        return status, confidence
    
    async def _generate_explanation(
        self,
        claim: str,
        status: VerificationStatus,
        supporting: List[str],
        contradicting: List[str],
    ) -> str:
        """Generate human-readable explanation."""
        status_text = {
            VerificationStatus.VERIFIED: "appears to be true",
            VerificationStatus.LIKELY_TRUE: "is likely true",
            VerificationStatus.UNCERTAIN: "could not be conclusively verified",
            VerificationStatus.LIKELY_FALSE: "is likely false",
            VerificationStatus.FALSE: "appears to be false",
            VerificationStatus.UNVERIFIABLE: "could not be verified with available sources",
        }
        
        explanation = f"The claim '{claim}' {status_text[status]}."
        
        if supporting:
            explanation += f" {len(supporting)} source(s) support this claim."
        
        if contradicting:
            explanation += f" {len(contradicting)} source(s) contradict this claim."
        
        return explanation
    
    async def check_response(
        self,
        response: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check an AI response for accuracy.
        
        Args:
            response: The AI response to check
            context: Original context/question
            
        Returns:
            Dict with verification results
        """
        results = await self.verify(response, deep_check=True)
        
        # Summary
        verified_count = sum(
            1 for r in results
            if r.status in [VerificationStatus.VERIFIED, VerificationStatus.LIKELY_TRUE]
        )
        
        problematic_count = sum(
            1 for r in results
            if r.status in [VerificationStatus.FALSE, VerificationStatus.LIKELY_FALSE]
        )
        
        overall_status = "accurate"
        if problematic_count > verified_count:
            overall_status = "potentially inaccurate"
        elif len(results) > 0 and verified_count == 0:
            overall_status = "unverified"
        
        return {
            "overall_status": overall_status,
            "total_claims": len(results),
            "verified": verified_count,
            "problematic": problematic_count,
            "results": [
                {
                    "claim": r.claim,
                    "status": r.status.value,
                    "confidence": r.confidence,
                    "explanation": r.explanation,
                }
                for r in results
            ],
        }
    
    def clear_cache(self) -> None:
        """Clear the verification cache."""
        self._cache.clear()


# Global truth checker instance
truth_checker = TruthChecker()
