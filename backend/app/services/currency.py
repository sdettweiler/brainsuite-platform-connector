import httpx
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.performance import CurrencyRate

logger = logging.getLogger(__name__)


class CurrencyConverterService:
    """Fetches and caches daily exchange rates. Primary: exchangerate-api.com, Fallback: frankfurter.app"""

    async def get_rate(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None,
    ) -> float:
        if from_currency == to_currency:
            return 1.0

        target_date = rate_date or date.today()

        # Check DB cache first
        cached = await self._get_cached_rate(db, from_currency, to_currency, target_date)
        if cached:
            return cached

        # Fetch from API
        rate = await self._fetch_rate(from_currency, to_currency, target_date)
        if rate:
            await self._cache_rate(db, from_currency, to_currency, target_date, rate)
            return rate

        # Last resort: 1.0 with warning
        logger.error(f"Could not fetch exchange rate {from_currency}->{to_currency} for {target_date}, using 1.0")
        return 1.0

    async def convert(
        self,
        db: AsyncSession,
        amount: Optional[Decimal],
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None,
    ) -> Optional[Decimal]:
        if amount is None:
            return None
        rate = await self.get_rate(db, from_currency, to_currency, rate_date)
        return Decimal(str(amount)) * Decimal(str(rate))

    async def _get_cached_rate(
        self, db: AsyncSession, from_currency: str, to_currency: str, rate_date: date
    ) -> Optional[float]:
        result = await db.execute(
            select(CurrencyRate).where(
                CurrencyRate.rate_date == rate_date,
                CurrencyRate.from_currency == from_currency.upper(),
                CurrencyRate.to_currency == to_currency.upper(),
            )
        )
        record = result.scalar_one_or_none()
        return record.rate if record else None

    async def _cache_rate(
        self,
        db: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        rate: float,
        source: str = "api",
    ) -> None:
        record = CurrencyRate(
            rate_date=rate_date,
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
            rate=rate,
            source=source,
        )
        db.add(record)
        try:
            await db.flush()
        except Exception:
            await db.rollback()

    async def _fetch_rate(
        self, from_currency: str, to_currency: str, rate_date: date
    ) -> Optional[float]:
        # Try primary API
        if settings.EXCHANGERATE_API_KEY:
            rate = await self._fetch_from_exchangerate_api(from_currency, to_currency, rate_date)
            if rate:
                return rate

        # Fallback to frankfurter.app
        return await self._fetch_from_frankfurter(from_currency, to_currency, rate_date)

    async def _fetch_from_exchangerate_api(
        self, from_currency: str, to_currency: str, rate_date: date
    ) -> Optional[float]:
        try:
            url = f"{settings.EXCHANGERATE_API_URL}/{settings.EXCHANGERATE_API_KEY}/latest/{from_currency.upper()}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                if data.get("result") == "success":
                    rates = data.get("conversion_rates", {})
                    return rates.get(to_currency.upper())
        except Exception as e:
            logger.warning(f"exchangerate-api.com failed: {e}")
        return None

    async def _fetch_from_frankfurter(
        self, from_currency: str, to_currency: str, rate_date: date
    ) -> Optional[float]:
        try:
            date_str = rate_date.strftime("%Y-%m-%d")
            url = f"{settings.FRANKFURTER_API_URL}/{date_str}"
            params = {"from": from_currency.upper(), "to": to_currency.upper()}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    # Try latest if historical date not available
                    resp = await client.get(f"{settings.FRANKFURTER_API_URL}/latest", params=params)
                resp.raise_for_status()
                data = resp.json()
                rates = data.get("rates", {})
                return rates.get(to_currency.upper())
        except Exception as e:
            logger.warning(f"frankfurter.app failed: {e}")
        return None


currency_converter = CurrencyConverterService()
