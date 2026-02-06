"""
Signal Validator
Validates trading signals for accuracy and flags suspicious ones.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re
import hashlib
import sys
sys.path.insert(0, str(__file__).replace('signals/validator.py', ''))


class ValidationFlag(Enum):
    """Types of validation flags"""
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    TICKER_INVALID = "ticker_invalid"
    SOURCE_UNRELIABLE = "source_unreliable"
    OLD_INFORMATION = "old_information"
    CONTRADICTING_SIGNALS = "contradicting_signals"
    SPAM_PATTERN = "spam_pattern"
    HYPE_CYCLE = "hype_cycle"
    UNUSUAL_VOLUME = "unusual_volume"
    WASH_TRADING = "wash_trading"


@dataclass
class ValidationResult:
    """Result of signal validation"""
    is_valid: bool
    flags: List[ValidationFlag]
    warnings: List[str]
    score: int  # 0-100 validity score
    details: Dict
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "flags": [f.value for f in self.flags],
            "warnings": self.warnings,
            "score": self.score,
            "details": self.details
        }


@dataclass
class HistoricalPattern:
    """Historical pattern for comparison"""
    signal_type: str
    avg_move: float
    success_rate: float
    avg_duration_days: float
    sample_size: int


class SignalValidator:
    """
    Validate trading signals.
    
    Features:
    - Check ticker validity (verify it exists)
    - Cross-reference with historical patterns
    - Flag suspicious signals
    - Detect spam and pump-and-dump patterns
    """
    
    # Valid ticker patterns by exchange
    TICKER_PATTERNS = {
        "NYSE": r"^[A-Z]{1,5}$",
        "NASDAQ": r"^[A-Z]{1,5}$",
        "AMEX": r"^[A-Z]{1,5}$",
        "DEFAULT": r"^[A-Z]{1,5}$"
    }
    
    # Known pharmaceutical/biotech tickers (partial list)
    KNOWN_BIOTECH_TICKERS = {
        "MRNA", "BNTX", "NVAX", "INO", "ARVN", "REGN", "VRTX", "GILD",
        "AMGN", "GENE", "EXAS", "INCY", "BIIB", "ALXN", "IOVA", "CRSP",
        "EDIT", "NTLA", "BEAM", "PACK", "FATE", "BLUE", "AGEN", "ARVA",
        "AXSM", "BCRX", "BMRN", "BPMC", "CARA", "CLOX", "DNLI", "DTX",
        "EIDX", "ENTA", "EPZM", "EQRX", "ESPR", "EVH", "FREQ", "GERN",
        "GLYC", "HALO", "HIMS", "HOOK", "HZNP", "IDRA", "IMMU", "IMRN",
        "INSM", "IOBT", "ITCI", "KURA", "KYMR", "LEGN", "LGND", "LUMO",
        "MARK", "MDGL", "MEIP", "MIST", "MNKD", "MRTX", "MYOV", "NEOG",
        "NMRK", "NTRT", "OBSV", "OLMA", "OPCH", "OPK", "OPNT", "ORIC",
        "ORTX", "PBLA", "PCYC", "PHRM", "PLX", "PNT", "PRAX", "PRTK",
        "PTCT", "PYPD", "QURE", "RDUS", "RENE", "RMTI", "RNA", "RXDX",
        "RYTM", "SAGE", "SNDX", "SNY", "SRNE", "STOK", "SURF", "SVRA",
        "SYRS", "TCMD", "TCON", "TGTX", "TK", "TNDM", "TRVI", "TSRO",
        "TTNP", "TURX", "TYRA", "UBX", "VACC", "VIR", "VIVO", "VKTX",
        "XBIT", "XENT", "XERS", "YMAB", "ZYNE"
    }
    
    # Spam/pump-and-dump patterns
    SPAM_PATTERNS = [
        r"guaranteed.*return",
        r"100.*percent.*gain",
        r"this.*stock.*will.*moon",
        r"don't.*miss.*out",
        r"pump.*and.*dump",
        r"buy.*the.*dip.*now",
        r"hot.*stock.*tip",
        r"exclusive.*insider",
        r"CEO.*of.*company.*here",
        r"turn.*\$.*into.*\$",
        r"get.*rich.*quick"
    ]
    
    # Historical patterns for common signal types
    HISTORICAL_PATTERNS = {
        "FDA_APPROVAL": HistoricalPattern(
            signal_type="FDA_APPROVAL",
            avg_move=15.0,
            success_rate=0.75,
            avg_duration_days=5,
            sample_size=150
        ),
        "FDA_REJECTION": HistoricalPattern(
            signal_type="FDA_REJECTION",
            avg_move=-25.0,
            success_rate=0.85,
            avg_duration_days=3,
            sample_size=80
        ),
        "TRIAL_SUCCESS": HistoricalPattern(
            signal_type="TRIAL_SUCCESS",
            avg_move=12.0,
            success_rate=0.70,
            avg_duration_days=10,
            sample_size=200
        ),
        "TRIAL_FAILURE": HistoricalPattern(
            signal_type="TRIAL_FAILURE",
            avg_move=-20.0,
            success_rate=0.80,
            avg_duration_days=5,
            sample_size=120
        ),
        "PRICE_TARGET_CHANGE": HistoricalPattern(
            signal_type="PRICE_TARGET_CHANGE",
            avg_move=5.0,
            success_rate=0.60,
            avg_duration_days=2,
            sample_size=500
        )
    }
    
    # Suspicious confidence patterns
    SUSPICIOUS_CONFIDENCE_THRESHOLDS = {
        "reddit": 80,  # Reddit signals above 80 are suspicious
        "twitter": 85,
        "default": 95
    }
    
    def __init__(self, known_tickers: Optional[set] = None):
        """
        Initialize validator.
        
        Args:
            known_tickers: Set of known valid tickers (optional)
        """
        self.known_tickers = known_tickers or self.KNOWN_BIOTECH_TICKERS
        self._compiled_spam_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SPAM_PATTERNS
        ]
    
    def validate_ticker(self, ticker: str, company_name: str = "") -> Tuple[bool, str]:
        """
        Validate ticker format and existence.
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not ticker:
            return False, "Empty ticker"
        
        # Check format
        is_valid_format = bool(re.match(self.TICKER_PATTERNS["DEFAULT"], ticker))
        
        if not is_valid_format:
            return False, f"Invalid ticker format: {ticker}"
        
        # Check against known tickers
        if ticker.upper() in self.known_tickers:
            return True, f"Valid biotech ticker: {ticker}"
        
        # Check if ticker is too generic (might be invalid)
        common_words = {"THE", "AND", "FOR", "CEO", "FDA", "INC", "CORP", "CO"}
        if ticker.upper() in common_words:
            return False, f"Common word used as ticker: {ticker}"
        
        # Unknown ticker - warning but not invalid
        return True, f"Unknown ticker: {ticker} (company enrichment recommended)"
    
    def check_spam_patterns(self, headline: str, summary: str) -> Tuple[bool, List[str]]:
        """
        Check for spam/pump-and-dump patterns.
        
        Returns:
            Tuple of (is_spam, matched_patterns)
        """
        text = f"{headline} {summary}".lower()
        matched = []
        
        for pattern in self._compiled_spam_patterns:
            if pattern.search(text):
                matched.append(pattern.pattern)
        
        return len(matched) > 0, matched
    
    def check_hype_cycle(self, signal: Dict, recent_signals: List[Dict]) -> Tuple[bool, str]:
        """
        Check if signal is part of a hype cycle.
        
        Returns:
            Tuple of (is_hype, message)
        """
        if not recent_signals:
            return False, ""
        
        ticker = signal.get("ticker", "").upper()
        signal_type = signal.get("signal_type", "")
        
        # Count recent signals for same ticker
        recent_count = sum(
            1 for s in recent_signals
            if s.get("ticker", "").upper() == ticker
            and s.get("signal_type") == signal_type
        )
        
        # Check if too many signals in short time (hype indicator)
        if recent_count > 3:
            return True, f"Hype cycle detected: {recent_count}+ signals for {ticker} recently"
        
        # Check for alternating sentiment
        sentiments = [s.get("sentiment") for s in recent_signals 
                     if s.get("ticker", "").upper() == ticker]
        
        if len(sentiments) >= 4:
            # Check for rapid sentiment changes
            changes = sum(1 for i in range(1, len(sentiments))
                         if sentiments[i] != sentiments[i-1])
            if changes >= 3:
                return True, f"Rapid sentiment changes detected for {ticker}"
        
        return False, ""
    
    def cross_reference_historical(self, signal: Dict) -> Tuple[bool, Dict]:
        """
        Cross-reference signal with historical patterns.
        
        Returns:
            Tuple of (matches_pattern, details)
        """
        signal_type = signal.get("signal_type", "")
        
        if signal_type not in self.HISTORICAL_PATTERNS:
            return True, {"message": "No historical data for this signal type"}
        
        pattern = self.HISTORICAL_PATTERNS[signal_type]
        
        # Check if confidence is realistic
        confidence = signal.get("confidence", 50)
        expected_confidence = int(pattern.success_rate * 100)
        
        # Confidence too high for the signal type
        if confidence > expected_confidence + 20:
            return False, {
                "warning": "Confidence may be inflated",
                "expected_confidence": expected_confidence,
                "actual_confidence": confidence,
                "historical_success_rate": pattern.success_rate
            }
        
        # Check if target moves align with historical
        target_upside = signal.get("target_upside", 0)
        expected_move = pattern.avg_move
        
        if abs(target_upside) > abs(expected_move) * 1.5:
            return False, {
                "warning": "Target move may be unrealistic",
                "expected_move": expected_move,
                "actual_target": target_upside
            }
        
        return True, {
            "message": "Signal aligns with historical patterns",
            "historical_success_rate": pattern.success_rate,
            "avg_move": pattern.avg_move,
            "sample_size": pattern.sample_size
        }
    
    def validate_sources(self, sources: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate signal sources.
        
        Returns:
            Tuple of (all_valid, warnings)
        """
        reliable_sources = {"fda.gov", "sec.gov", "reuters.com", "bloomberg.com",
                          "wsj.com", "pubmed.ncbi.nlm.nih.gov", "nejm.org"}
        
        warnings = []
        all_valid = True
        
        for source in sources:
            source_lower = source.lower()
            is_reliable = any(r in source_lower for r in reliable_sources)
            
            if not is_reliable:
                warnings.append(f"Unreliable source: {source}")
                # Not invalidating, just warning
                if "reddit" in source_lower or "twitter" in source_lower:
                    warnings.append(f"Social media source requires additional verification")
        
        return all_valid, warnings
    
    def check_recency(self, collected_at: str, max_age_hours: int = 72) -> Tuple[bool, str]:
        """
        Check if signal is recent enough.
        
        Returns:
            Tuple of (is_recent, message)
        """
        try:
            if not collected_at:
                return False, "No timestamp provided"
            
            collected_date = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            age_hours = (datetime.now() - collected_date).total_seconds() / 3600
            
            if age_hours < 0:
                return False, "Future timestamp (suspicious)"
            
            if age_hours > max_age_hours:
                return False, f"Signal is {age_hours:.0f} hours old (> {max_age_hours})"
            
            if age_hours > 24:
                return True, f"Signal is {age_hours:.1f} hours old"
            
            return True, "Signal is fresh"
        
        except ValueError:
            return False, "Invalid timestamp format"
    
    def validate_signal(self, signal: Dict, 
                       recent_signals: Optional[List[Dict]] = None) -> ValidationResult:
        """
        Perform comprehensive signal validation.
        
        Args:
            signal: Signal dictionary to validate
            recent_signals: Optional list of recent signals for comparison
        
        Returns:
            ValidationResult with validation status and details
        """
        flags = []
        warnings = []
        details = {}
        
        # 1. Validate ticker
        ticker_valid, ticker_msg = self.validate_ticker(
            signal.get("ticker", ""),
            signal.get("company_name", "")
        )
        if not ticker_valid:
            flags.append(ValidationFlag.TICKER_INVALID)
            warnings.append(ticker_msg)
        details["ticker"] = ticker_msg
        
        # 2. Check spam patterns
        is_spam, spam_matches = self.check_spam_patterns(
            signal.get("headline", ""),
            signal.get("summary", "")
        )
        if is_spam:
            flags.append(ValidationFlag.SPAM_PATTERN)
            warnings.append(f"Spam patterns detected: {spam_matches}")
        details["spam_check"] = {
            "is_spam": is_spam,
            "matched_patterns": spam_matches
        }
        
        # 3. Check sources
        sources = signal.get("sources", [])
        sources_valid, source_warnings = self.validate_sources(sources)
        if source_warnings:
            warnings.extend(source_warnings)
            flags.append(ValidationFlag.SOURCE_UNRELIABLE)
        details["sources"] = {"warnings": source_warnings}
        
        # 4. Check recency
        is_recent, recency_msg = self.check_recency(signal.get("collected_at", ""))
        if not is_recent:
            flags.append(ValidationFlag.OLD_INFORMATION)
            warnings.append(recency_msg)
        details["recency"] = recency_msg
        
        # 5. Cross-reference historical patterns
        matches_historical, historical_details = self.cross_reference_historical(signal)
        if not matches_historical:
            flags.append(ValidationFlag.SUSPICIOUS_PATTERN)
            warnings.append(historical_details.get("warning", "Pattern mismatch"))
        details["historical"] = historical_details
        
        # 6. Check hype cycle
        if recent_signals:
            is_hype, hype_msg = self.check_hype_cycle(signal, recent_signals)
            if is_hype:
                flags.append(ValidationFlag.HYPE_CYCLE)
                warnings.append(hype_msg)
            details["hype_check"] = hype_msg
        
        # 7. Check suspicious confidence
        primary_source = sources[0].lower() if sources else ""
        confidence = signal.get("confidence", 50)
        
        max_confidence = self_CONFIDENCE_THRESHOLDS[".SUSPICIOUSdefault"]
        for source_type, threshold in self.SUSPICIOUS_CONFIDENCE_THRESHOLDS.items():
            if source_type in primary_source:
                max_confidence = threshold
                break
        
        if confidence > max_confidence:
            warnings.append(f"Confidence {confidence}% may be inflated for this source type")
            details["confidence_warning"] = f"Max expected: {max_confidence}%"
        
        # Calculate validity score
        base_score = 100
        penalty_weights = {
            ValidationFlag.TICKER_INVALID: 30,
            ValidationFlag.SPAM_PATTERN: 50,
            ValidationFlag.SOURCE_UNRELIABLE: 15,
            ValidationFlag.OLD_INFORMATION: 20,
            ValidationFlag.HYPE_CYCLE: 25,
            ValidationFlag.SUSPICIOUS_PATTERN: 15
        }
        
        for flag in flags:
            base_score -= penalty_weights.get(flag, 10)
        
        # Apply warnings penalty
        base_score -= len(warnings) * 3
        
        validity_score = max(0, min(100, base_score))
        is_valid = validity_score >= 60 and ValidationFlag.TICKER_INVALID not in flags
        
        return ValidationResult(
            is_valid=is_valid,
            flags=flags,
            warnings=warnings,
            score=validity_score,
            details=details
        )
    
    def batch_validate(self, signals: List[Dict]) -> List[ValidationResult]:
        """
        Validate a batch of signals.
        
        Returns:
            List of ValidationResults
        """
        # Group by ticker for cross-reference
        recent_by_ticker = {}
        for signal in signals:
            ticker = signal.get("ticker", "").upper()
            if ticker not in recent_by_ticker:
                recent_by_ticker[ticker] = []
            recent_by_ticker[ticker].append(signal)
        
        results = []
        for signal in signals:
            ticker = signal.get("ticker", "").upper()
            # Get recent signals for this ticker (excluding current)
            recent = [s for s in recent_by_ticker.get(ticker, []) 
                     if s != signal]
            results.append(self.validate_signal(signal, recent))
        
        return results
    
    def get_validation_summary(self, results: List[ValidationResult]) -> Dict:
        """Get summary of batch validation"""
        if not results:
            return {"total": 0, "valid": 0, "invalid": 0}
        
        valid_count = sum(1 for r in results if r.is_valid)
        
        flag_counts = {}
        for result in results:
            for flag in result.flags:
                flag_counts[flag.value] = flag_counts.get(flag.value, 0) + 1
        
        return {
            "total": len(results),
            "valid": valid_count,
            "invalid": len(results) - valid_count,
            "validity_rate": round(valid_count / len(results) * 100, 1),
            "flag_counts": flag_counts,
            "avg_score": sum(r.score for r in results) / len(results)
        }


# Convenience function
def validate_signal(signal: Dict, recent_signals: List[Dict] = None) -> ValidationResult:
    """Quick function to validate a signal"""
    validator = SignalValidator()
    return validator.validate_signal(signal, recent_signals)


if __name__ == "__main__":
    # Demo
    validator = SignalValidator()
    
    # Test signal
    test_signal = {
        "signal_type": "FDA_APPROVAL",
        "ticker": "MRNA",
        "company_name": "Moderna Inc",
        "headline": "FDA approves Moderna's COVID-19 vaccine",
        "summary": "The FDA has granted full approval for Moderna's vaccine.",
        "confidence": 85,
        "sources": ["fda.gov", "reuters.com"],
        "collected_at": "2026-02-06T08:00:00"
    }
    
    result = validator.validate_signal(test_signal)
    
    print(f"Valid: {result.is_valid}")
    print(f"Score: {result.score}/100")
    print(f"Flags: {[f.value for f in result.flags]}")
    print(f"Warnings: {result.warnings}")
    print(f"Details: {result.details}")
    
    # Test spam signal
    spam_signal = {
        "signal_type": "PRICE_TARGET_CHANGE",
        "ticker": "XYZ",
        "company_name": "XYZ Corp",
        "headline": "GUARANTEED 100% RETURN - THIS STOCK WILL MOON!",
        "summary": "Don't miss out on this exclusive tip!",
        "confidence": 95,
        "sources": ["reddit.com"],
        "collected_at": "2026-02-06T08:00:00"
    }
    
    print("\n" + "="*50 + "\n")
    spam_result = validator.validate_signal(spam_signal)
    
    print(f"Valid: {spam_result.is_valid}")
    print(f"Score: {spam_result.score}/100")
    print(f"Flags: {[f.value for f in spam_result.flags]}")
    print(f"Warnings: {spam_result.warnings}")
