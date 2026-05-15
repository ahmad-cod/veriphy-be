from src.domain.ai.nlp import NLPExtractor


def test_extracts_amount_and_transaction_ref_from_sms():
    sms = (
        "Your payment of NGN 5,000.00 was successful. "
        "Transaction ref: SQCHIZ3634573076082. Thank you."
    )

    result = NLPExtractor.extract_financial_entities(sms)

    assert result["amount"] == 5000.0
    assert result["transaction_ref"] == "SQCHIZ3634573076082"
    assert result["confidence_score"] > 0.0
