import httpx
import asyncio
from typing import Optional, Dict, Any
import structlog
from src.core.config import settings
from src.core.exceptions import VeriphyException

logger = structlog.get_logger()

class SquadAPIClient:
    _instance = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SquadAPIClient, cls).__new__(cls)
        return cls._instance

    def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.SQUAD_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY.get_secret_value()}",
                    "Content-Type": "application/json"
                },
                timeout=httpx.Timeout(10.0, connect=2.0),
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
            )
        return self._client

    async def verify_transaction(self, amount: int, virtual_account: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Verify if a transaction with the given amount exists for the virtual account.

        Args:
            amount: The transaction amount to match
            virtual_account: The virtual account number
            retries: Number of retry attempts for network failures

        Returns:
            Transaction details if found and matched, None otherwise

        Raises:
            VeriphyException: If API communication fails after all retries
        """
        client = self.get_client()
        url = "/transaction/merchant"

        for attempt in range(retries):
            try:
                logger.info(
                    "Querying Squad API for transactions",
                    virtual_account=virtual_account,
                    amount=amount,
                    attempt=attempt + 1
                )

                response = await client.get(url, params={"virtual_account": virtual_account})
                response.raise_for_status()
                data = response.json()

                # Validate response structure
                if not isinstance(data, dict) or "data" not in data:
                    logger.error("Invalid Squad API response structure", response_data=data)
                    raise VeriphyException("Invalid response from Squad API", status_code=502)

                transactions = data.get("data", [])
                if not isinstance(transactions, list):
                    logger.error("Squad API transactions data is not a list", transactions=transactions)
                    raise VeriphyException("Invalid transaction data format", status_code=502)

                # Look for matching transaction
                for txn in transactions:
                    if not isinstance(txn, dict):
                        continue

                    txn_amount = txn.get("amount")
                    txn_status = txn.get("status", "").lower()
                    txn_reference = txn.get("transaction_reference")

                    # Convert amount to float for comparison
                    try:
                        txn_amount_float = float(txn_amount) if txn_amount is not None else 0.0
                    except (ValueError, TypeError):
                        logger.warning("Invalid transaction amount format", amount=txn_amount)
                        continue

                    # Check for exact amount match and successful status
                    if abs(txn_amount_float - amount) < 0.01 and txn_status == "success":
                        logger.info(
                            "Transaction match found",
                            transaction_ref=txn_reference,
                            amount=txn_amount_float,
                            status=txn_status
                        )
                        return {
                            "transaction_reference": txn_reference,
                            "amount": txn_amount_float,
                            "status": txn_status,
                            "timestamp": txn.get("created_at"),
                            "virtual_account": virtual_account
                        }

                logger.info(
                    "No matching transaction found",
                    virtual_account=virtual_account,
                    amount=amount,
                    transactions_checked=len(transactions)
                )
                return None

            except httpx.HTTPStatusError as e:
                # 4xx errors are not retryable (client errors)
                if 400 <= e.response.status_code < 500:
                    logger.error(
                        "Squad API Client Error",
                        status=e.response.status_code,
                        response_body=e.response.text[:500]  # Log first 500 chars
                    )
                    # Don't retry client errors
                    return None
                else:
                    # 5xx errors are retryable
                    logger.warning(
                        "Squad API Server Error, retrying...",
                        status=e.response.status_code,
                        attempt=attempt + 1
                    )

            except httpx.RequestError as e:
                logger.warning(
                    "Squad API Network Error, retrying...",
                    error=str(e),
                    attempt=attempt + 1
                )

            # Exponential backoff before retry (only for network/server errors)
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)

        logger.error("Squad API communication failed after all retries")
        raise VeriphyException("Squad API communication failed after retries", status_code=502)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()