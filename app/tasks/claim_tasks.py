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
from app.utils.logging_config import get_logger
from app.utils.file_validation import cleanup_temp_file

logger = get_logger(__name__)


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
    logger.info(f"Starting claims CSV processing: {file_path}")

    try:
        # Read CSV file
        df = pd.read_csv(file_path)
        logger.info(
            f"CSV file loaded successfully",
            extra={"extra_fields": {"file_path": file_path, "row_count": len(df)}}
        )
    except Exception as e:
        logger.error(
            f"Failed to read CSV file: {str(e)}",
            exc_info=True,
            extra={"extra_fields": {"file_path": file_path}}
        )
        return {
            "status": "error",
            "message": f"Failed to read CSV file: {str(e)}",
            "records_ingested": 0,
            "records_audited": 0,
        }

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
        logger.error(
            f"CSV validation failed - missing columns: {missing_columns}",
            extra={"extra_fields": {"file_path": file_path, "missing_columns": missing_columns}}
        )
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

        logger.info(
            f"Claims CSV processing completed successfully",
            extra={"extra_fields": {
                "file_path": file_path,
                "records_ingested": records_ingested,
                "records_audited": records_audited,
                "error_count": len(errors)
            }}
        )

    except Exception as e:
        logger.error(
            f"Claims CSV processing failed: {str(e)}",
            exc_info=True,
            extra={"extra_fields": {
                "file_path": file_path,
                "records_ingested": records_ingested,
                "records_audited": records_audited
            }}
        )
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
        # Clean up temporary file after processing
        cleanup_temp_file(file_path)

    return {
        "status": "success",
        "records_ingested": records_ingested,
        "records_audited": records_audited,
        "errors": errors[:10] if errors else [],
    }


@celery_app.task(
    name="app.tasks.claim_tasks.process_claims_csv",
    bind=True,  # Bind task instance as first argument
    max_retries=3,  # Maximum number of retries
    default_retry_delay=300,  # 5 minutes between retries
    autoretry_for=(Exception,),  # Retry on any exception
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=3600,  # Maximum backoff of 1 hour
    retry_jitter=True,  # Add random jitter to prevent thundering herd
)
def process_claims_csv(self, file_path: str) -> Dict[str, Any]:
    """
    Celery task to process claims CSV file with automatic retries.

    Args:
        self: Task instance (bound)
        file_path: Path to the CSV file to process

    Returns:
        Dictionary with processing results
    """
    logger.info(
        f"Celery task started: process_claims_csv - {file_path}",
        extra={"extra_fields": {"task_id": self.request.id, "retries": self.request.retries}}
    )

    try:
        # Run the async function in an event loop
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(process_claims_csv_async(file_path))

        logger.info(
            f"Celery task completed: process_claims_csv",
            extra={"extra_fields": {
                "file_path": file_path,
                "status": result.get("status"),
                "task_id": self.request.id
            }}
        )

        return result

    except Exception as exc:
        logger.error(
            f"Celery task failed: process_claims_csv - {str(exc)}",
            exc_info=True,
            extra={"extra_fields": {
                "file_path": file_path,
                "task_id": self.request.id,
                "retries": self.request.retries
            }}
        )
        # Re-raise to trigger automatic retry
        raise


@celery_app.task(
    name="app.tasks.claim_tasks.run_ml_audit",
    bind=True,  # Bind task instance
    max_retries=2,  # Retry up to 2 times for ML tasks
    default_retry_delay=600,  # 10 minutes between retries
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=7200,  # Maximum 2 hours backoff
    retry_jitter=True,
)
def run_ml_audit(self) -> Dict[str, Any]:
    """
    Celery task to run ML-based anomaly detection on all claims with automatic retries.

    Args:
        self: Task instance (bound)

    Returns:
        Dictionary with audit results
    """
    logger.info(
        "Celery task started: run_ml_audit (ML anomaly detection)",
        extra={"extra_fields": {"task_id": self.request.id, "retries": self.request.retries}}
    )

    async def run_ml_audit_async():
        session = get_async_session()
        audit_service = AuditEngineService(session)

        try:
            logger.info("Starting ML anomaly detection on claims")

            # Run ML anomaly detection
            anomalous_claims = await audit_service.run_ml_anomaly_detection(
                skip=0, limit=10000
            )

            logger.info(
                f"ML anomaly detection completed",
                extra={"extra_fields": {"anomalies_found": len(anomalous_claims)}}
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

            logger.info(
                "ML audit task completed successfully",
                extra={"extra_fields": {
                    "anomalies_detected": len(anomalous_claims),
                    "records_audited": audited_count
                }}
            )

            return {
                "status": "success",
                "anomalies_detected": len(anomalous_claims),
                "records_audited": audited_count,
            }

        except Exception as e:
            logger.error(
                f"ML audit task failed: {str(e)}",
                exc_info=True
            )
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

    logger.info(
        f"Celery task completed: run_ml_audit",
        extra={"extra_fields": {"status": result.get("status")}}
    )

    return result
