import re
import structlog
import spacy
from typing import Dict, Optional

logger = structlog.get_logger()

class NLPExtractor:
    _model = None

    @classmethod
    def load_models(cls):
        """Called during Celery worker initialization to warm up NLP models."""
        if cls._model is None:
            try:
                logger.info("Loading spaCy NLP models into memory...")
                # Load the small English model for entity recognition
                cls._model = spacy.load("en_core_web_sm")
                logger.info("NLP models warmed up and ready.")
            except OSError:
                logger.warning("spaCy model not found, falling back to regex-only mode")
                cls._model = "REGEX_ONLY"
            except Exception as e:
                logger.error("Failed to load NLP models", error=str(e))
                cls._model = "REGEX_ONLY"

    @staticmethod
    def extract_financial_entities(sms_body: str) -> Dict[str, Optional[float]]:
        """
        Extract financial entities from SMS text using NLP and regex fallback.

        Args:
            sms_body: The SMS message text to analyze

        Returns:
            Dict with 'amount' (float or None) and 'confidence_score' (0.0-1.0)
        """
        if not sms_body or not isinstance(sms_body, str):
            return {"amount": None, "confidence_score": 0.0}

        # Clean and normalize the text
        sms_body = sms_body.strip()

        # Method 1: Use spaCy for entity recognition (if model loaded)
        if NLPExtractor._model and NLPExtractor._model != "REGEX_ONLY":
            try:
                doc = NLPExtractor._model(sms_body)

                # Look for money entities
                for ent in doc.ents:
                    if ent.label_ == "MONEY":
                        # Extract numeric value from money entity
                        amount_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', ent.text)
                        if amount_match:
                            amount = float(amount_match.group(1).replace(',', ''))
                            logger.info(
                                "NLP extracted amount from MONEY entity",
                                amount=amount,
                                entity_text=ent.text
                            )
                            return {"amount": amount, "confidence_score": 0.9}

                # Look for CARDINAL numbers that might be amounts (fallback)
                for ent in doc.ents:
                    if ent.label_ == "CARDINAL":
                        amount_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', ent.text)
                        if amount_match:
                            amount = float(amount_match.group(1).replace(',', ''))
                            # Only accept if it's a reasonable transaction amount
                            if 1 <= amount <= 10000000:  # Between 1 Naira and 10M Naira
                                logger.info(
                                    "NLP extracted amount from CARDINAL entity",
                                    amount=amount,
                                    entity_text=ent.text
                                )
                                return {"amount": amount, "confidence_score": 0.7}

            except Exception as e:
                logger.warning("NLP processing failed, falling back to regex", error=str(e))

        # Method 2: Regex fallback with improved patterns
        amount_patterns = [
            # Standard currency patterns
            r'(?:NGN|N|Rs|GHC|₦)\s?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            # Amount words
            r'(?:amount|sum|total|balance|credited|debited|transferred)[\s:]+(?:NGN|N|₦)?\s?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            # Transaction patterns
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s?(?:NGN|N|₦|naira|kobo)',
            # Standalone numbers (last resort)
            r'\b(\d+(?:,\d{3})*(?:\.\d{2})?)\b'
        ]

        for pattern in amount_patterns:
            matches = re.findall(pattern, sms_body, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    # Validate reasonable transaction amounts
                    if 1 <= amount <= 10000000:  # Between 1 Naira and 10M Naira
                        confidence = 0.85 if 'NGN' in sms_body.upper() or '₦' in sms_body else 0.6
                        logger.info(
                            "Regex extracted amount",
                            amount=amount,
                            pattern=pattern,
                            confidence=confidence
                        )
                        return {"amount": amount, "confidence_score": confidence}
                except ValueError:
                    continue

        logger.info("No amount found in SMS", sms_preview=sms_body[:100])
        return {"amount": None, "confidence_score": 0.0}