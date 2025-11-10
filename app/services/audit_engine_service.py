"""Audit Engine service for detecting fraudulent/erroneous claims."""
from typing import List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from sklearn.ensemble import IsolationForest

from app.models.claim import Claim
from app.repositories.claim_repository import ClaimRepository
from app.repositories.audit_result_repository import AuditResultRepository


class AuditEngineService:
    """Service for auditing claims using rule-based and ML detection."""

    # CPT code median prices (simplified - in production, use a comprehensive database)
    CPT_MEDIAN_PRICES = {
        "99213": Decimal("100.00"),  # Office visit, established patient
        "99214": Decimal("150.00"),  # Office visit, established patient, complex
        "99215": Decimal("200.00"),  # Office visit, established patient, high complexity
        "99203": Decimal("130.00"),  # Office visit, new patient
        "99204": Decimal("180.00"),  # Office visit, new patient, complex
        "99205": Decimal("250.00"),  # Office visit, new patient, high complexity
        "80053": Decimal("50.00"),   # Comprehensive metabolic panel
        "85025": Decimal("30.00"),   # Complete blood count
        "36415": Decimal("10.00"),   # Routine venipuncture
        "93000": Decimal("75.00"),   # Electrocardiogram
    }

    # Bundled CPT codes that shouldn't be billed together
    BUNDLED_CODES = {
        ("99213", "99214"),  # Can't bill two office visits same day
        ("99203", "99204"),  # Can't bill two new patient visits same day
        ("80053", "85025"),  # Often bundled in lab panels
    }

    def __init__(self, db: AsyncSession):
        """Initialize audit engine with database session."""
        self.db = db
        self.claim_repo = ClaimRepository(db)
        self.audit_repo = AuditResultRepository(db)

    async def audit_claim(self, claim: Claim) -> Tuple[List[str], Decimal]:
        """
        Audit a single claim using rule-based detection.

        Args:
            claim: Claim object to audit

        Returns:
            Tuple of (list of issues found, suspicion score)
        """
        issues = []

        # Rule 1: Check for duplicate claims
        duplicate_issue = await self._check_duplicate_claim(claim)
        if duplicate_issue:
            issues.append(duplicate_issue)

        # Rule 2: Check for excessive charge amounts
        price_issue = self._check_excessive_charge(claim)
        if price_issue:
            issues.append(price_issue)

        # Rule 3: Check for bundled services
        bundled_issue = await self._check_bundled_services(claim)
        if bundled_issue:
            issues.append(bundled_issue)

        # Calculate suspicion score based on number and severity of issues
        suspicion_score = self._calculate_suspicion_score(issues, claim)

        return issues, suspicion_score

    async def _check_duplicate_claim(self, claim: Claim) -> str:
        """
        Check if claim is a duplicate.

        Args:
            claim: Claim to check

        Returns:
            Issue description if duplicate found, empty string otherwise
        """
        result = await self.db.execute(
            select(func.count(Claim.id))
            .where(
                Claim.member_id == claim.member_id,
                Claim.provider_id == claim.provider_id,
                Claim.date_of_service == claim.date_of_service,
                Claim.cpt_code == claim.cpt_code,
                Claim.id != claim.id,  # Exclude current claim
            )
        )
        duplicate_count = result.scalar()

        if duplicate_count > 0:
            return f"Duplicate claim detected ({duplicate_count} similar claims found)"
        return ""

    def _check_excessive_charge(self, claim: Claim) -> str:
        """
        Check if charge amount is excessive compared to CPT median.

        Args:
            claim: Claim to check

        Returns:
            Issue description if excessive, empty string otherwise
        """
        if claim.cpt_code in self.CPT_MEDIAN_PRICES:
            median_price = self.CPT_MEDIAN_PRICES[claim.cpt_code]
            ratio = float(claim.charge_amount / median_price)

            if ratio > 2.5:
                return f"Charge amount is {ratio:.1f}x higher than CPT median (${median_price})"
            elif ratio < 0.5:
                return f"Charge amount is unusually low ({ratio:.1f}x of CPT median)"

        return ""

    async def _check_bundled_services(self, claim: Claim) -> str:
        """
        Check if claim has bundled services billed separately.

        Args:
            claim: Claim to check

        Returns:
            Issue description if bundled services found, empty string otherwise
        """
        # Check for other claims on same date for same member/provider
        result = await self.db.execute(
            select(Claim.cpt_code)
            .where(
                Claim.member_id == claim.member_id,
                Claim.provider_id == claim.provider_id,
                Claim.date_of_service == claim.date_of_service,
                Claim.id != claim.id,
            )
        )
        same_day_codes = [row[0] for row in result.all()]

        # Check if any bundled codes are present
        for code in same_day_codes:
            if (claim.cpt_code, code) in self.BUNDLED_CODES or (
                code,
                claim.cpt_code,
            ) in self.BUNDLED_CODES:
                return f"Bundled service detected: CPT {claim.cpt_code} and {code} billed separately"

        return ""

    def _calculate_suspicion_score(self, issues: List[str], claim: Claim) -> Decimal:
        """
        Calculate suspicion score based on issues found.

        Args:
            issues: List of issues found
            claim: Claim being audited

        Returns:
            Suspicion score between 0 and 1
        """
        if not issues:
            return Decimal("0.0")

        base_score = Decimal("0.3") * len(issues)  # Each issue adds 0.3

        # Increase score for high-value claims with issues
        if claim.charge_amount > Decimal("500.00"):
            base_score += Decimal("0.1")

        # Cap at 1.0
        return min(base_score, Decimal("1.0"))

    async def run_ml_anomaly_detection(
        self, skip: int = 0, limit: int = 1000
    ) -> List[Claim]:
        """
        Run ML-based anomaly detection on claims using Isolation Forest.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to process

        Returns:
            List of claims flagged as anomalies
        """
        # Fetch claims for analysis
        claims = await self.claim_repo.get_all(skip=skip, limit=limit)

        if len(claims) < 10:
            # Not enough data for ML
            return []

        # Prepare features for ML model
        features = []
        for claim in claims:
            features.append(
                [
                    float(claim.charge_amount),
                    hash(claim.cpt_code) % 1000,  # Simple encoding
                    hash(claim.provider_id) % 1000,
                    (datetime.now().date() - claim.date_of_service).days,
                ]
            )

        X = np.array(features)

        # Train Isolation Forest model
        model = IsolationForest(
            contamination=0.1,  # Expect 10% anomalies
            random_state=42,
            n_estimators=100,
        )
        predictions = model.fit_predict(X)

        # Get anomalous claims (prediction = -1)
        anomalous_claims = [
            claims[i] for i, pred in enumerate(predictions) if pred == -1
        ]

        return anomalous_claims

    def _get_recommended_action(
        self, issues: List[str], suspicion_score: Decimal
    ) -> str:
        """
        Determine recommended action based on issues and suspicion score.

        Args:
            issues: List of issues found
            suspicion_score: Suspicion score

        Returns:
            Recommended action string
        """
        if suspicion_score >= Decimal("0.8"):
            return "Request medical records and initiate provider audit"
        elif suspicion_score >= Decimal("0.6"):
            return "Request additional documentation from provider"
        elif suspicion_score >= Decimal("0.4"):
            return "Flag for manual review"
        else:
            return "Monitor for patterns"

    async def create_audit_result(
        self, claim: Claim, issues: List[str], suspicion_score: Decimal
    ) -> None:
        """
        Create an audit result entry for a claim.

        Args:
            claim: Claim that was audited
            issues: List of issues found
            suspicion_score: Calculated suspicion score
        """
        issues_dict = {"issues": issues, "issue_count": len(issues)}
        recommended_action = self._get_recommended_action(issues, suspicion_score)

        await self.audit_repo.create(
            claim_id=claim.id,
            issues_found=issues_dict,
            suspicion_score=suspicion_score,
            recommended_action=recommended_action,
        )

        await self.db.commit()
