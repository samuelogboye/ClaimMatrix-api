"""Celery tasks for claim processing."""
import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.celery_app import celery_app
from app.config import settings
from app.services.claim_service import ClaimService
from app.services.audit_engine_service import AuditEngineService
from app.schemas.claim import ClaimCreate


def get_async_session() -> AsyncSession:
    """Create async database session for Celery tasks."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()


async def process_claims_csv_async(file_path: str) -> Dict[str, Any]:
    """
    Async function to process claims CSV and audit them.

    Args:
        file_path: Path to the CSV file

    Returns:
        Dictionary with processing results
    """
    # Read CSV file
    df = pd.read_csv(file_path)

    # Validate required columns
    required_columns = [
        "claim_id",
        "member_id",
        "provider_id",
        "date_of_service",
        "cpt_code",
        "charge_amount",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return {
            "status": "error",
            "message": f"Missing required columns: {', '.join(missing_columns)}",
            "records_ingested": 0,
            "records_audited": 0,
        }

    session = get_async_session()
    claim_service = ClaimService(session)
    audit_service = AuditEngineService(session)

    records_ingested = 0
    records_audited = 0
    errors = []

    try:
        for index, row in df.iterrows():
            try:
                # Parse date of service
                date_of_service = pd.to_datetime(row["date_of_service"]).date()

                # Create claim
                claim_data = ClaimCreate(
                    claim_id=str(row["claim_id"]),
                    member_id=str(row["member_id"]),
                    provider_id=str(row["provider_id"]),
                    date_of_service=date_of_service,
                    cpt_code=str(row["cpt_code"]),
                    charge_amount=Decimal(str(row["charge_amount"])),
                )

                # Check if claim already exists
                existing_claim = await claim_service.get_claim_by_claim_id(
                    claim_data.claim_id
                )

                if existing_claim:
                    # Skip duplicate claims
                    continue

                # Create claim
                claim_response = await claim_service.create_claim(claim_data)
                records_ingested += 1

                # Get the claim object for auditing
                claim = await claim_service.repository.get_by_id(claim_response.id)

                if claim:
                    # Audit the claim
                    issues, suspicion_score = await audit_service.audit_claim(claim)

                    # Create audit result
                    await audit_service.create_audit_result(
                        claim, issues, suspicion_score
                    )
                    records_audited += 1

            except Exception as e:
                errors.append(f"Row {index}: {str(e)}")
                continue

        await session.commit()

    except Exception as e:
        await session.rollback()
        return {
            "status": "error",
            "message": f"Processing failed: {str(e)}",
            "records_ingested": records_ingested,
            "records_audited": records_audited,
            "errors": errors[:10],  # Limit errors to first 10
        }
    finally:
        await session.close()

    return {
        "status": "success",
        "records_ingested": records_ingested,
        "records_audited": records_audited,
        "errors": errors[:10] if errors else [],
    }


@celery_app.task(name="app.tasks.claim_tasks.process_claims_csv")
def process_claims_csv(file_path: str) -> Dict[str, Any]:
    """
    Celery task to process claims CSV file.

    Args:
        file_path: Path to the CSV file to process

    Returns:
        Dictionary with processing results
    """
    # Run the async function in an event loop
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(process_claims_csv_async(file_path))
    return result


@celery_app.task(name="app.tasks.claim_tasks.run_ml_audit")
def run_ml_audit() -> Dict[str, Any]:
    """
    Celery task to run ML-based anomaly detection on all claims.

    Returns:
        Dictionary with audit results
    """

    async def run_ml_audit_async():
        session = get_async_session()
        audit_service = AuditEngineService(session)

        try:
            # Run ML anomaly detection
            anomalous_claims = await audit_service.run_ml_anomaly_detection(
                skip=0, limit=10000
            )

            audited_count = 0
            for claim in anomalous_claims:
                # Create audit result for anomalous claims
                issues = ["Flagged by ML anomaly detection (Isolation Forest)"]
                suspicion_score = Decimal("0.75")  # High suspicion for ML-flagged claims

                await audit_service.create_audit_result(
                    claim, issues, suspicion_score
                )
                audited_count += 1

            await session.commit()

            return {
                "status": "success",
                "anomalies_detected": len(anomalous_claims),
                "records_audited": audited_count,
            }

        except Exception as e:
            await session.rollback()
            return {
                "status": "error",
                "message": f"ML audit failed: {str(e)}",
                "anomalies_detected": 0,
            }
        finally:
            await session.close()

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(run_ml_audit_async())
    return result
