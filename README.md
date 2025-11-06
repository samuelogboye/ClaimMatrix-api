# ClaimMatrix-api
An AI-powered medical claims audit engine for self-insured employers and health plans.

ClaimMatrix automatically audits medical claims post-payment, identifies hard-to-catch billing errors, and provides defensible audit results to support provider disputes, ERISA fiduciary compliance, and cost recovery.  
Built using **FastAPI, PostgreSQL, Docker, Pandas, and scikit-learn**.

---

## 🚀 Key Features
- **100% Claim Auditing** — No sampling. Every claim is analyzed.
- **Hybrid Audit Engine** — Rule-based checks + ML anomaly detection.
- **Billing Error Detection**
  - Duplicate submissions  
  - Upcoding & unbundling  
  - Price outliers vs historical norms  
  - Missing 501(r) financial assistance screening
- **Secure API** — Claims ingestion + audit results over REST.
- **PostgreSQL Storage** — Durable audit logs for compliance.
- **Dockerized Deployment** — Ready for local or cloud deployment.

---

## 🧩 System Architecture
TPA → FastAPI → PostgreSQL → Audit Engine (Rules + IsolationForest) → Flagged Claims API

## 🛠 Tech Stack
| Component | Technology |
|----------|------------|
| API Layer | FastAPI |
| Database | PostgreSQL |
| ML / Analytics | Pandas, scikit-learn |
| Containerization | Docker & Docker Compose |
| Auth  | JWT, Role-based access |

---

## 🔧 Installation

### ✅ Clone Repository
```bash
git clone https://github.com/samuelogboye/ClaimMatrix-api.git
cd ClaimMatrix-api
```

✅ Create Environment & Install Requirements
```bash
pip install -r requirements.txt
```

🐳 Run with Docker

```bash
docker compose up --build
```

This will start:

FastAPI service → localhost:8000

PostgreSQL database → localhost:5432


🚀 Running the API

Start the backend locally:

uvicorn app.main:app --reload


Open API docs (Swagger):

http://localhost:8000/docs

📥 Claims Ingestion API
POST /claims/upload

Upload CSV of claims:
Request
```bash
curl -X POST "http://localhost:8000/claims/upload" \
     -F "file=@data/sample_claims.csv"
```

Response
```json
{
  "status": "accepted",
  "records_ingested": 1052
}
```

🔎 Get Flagged / Suspicious Claims
GET /claims/flagged
```bash
curl "http://localhost:8000/claims/flagged"
```

Response
```json
[
  {
    "claim_id": "CL-04491",
    "issues": [
      "Charge amount is 3.2x higher than CPT median",
      "Potential upcoding"
    ],
    "suspicion_score": 0.91,
    "recommended_action": "Request medical records"
  }
]
```

### 🧠 How the Audit Engine Works
✅ Rule-Based Detection

- Duplicate claims

- Excessive charge amount vs expected CPT value

- Bundled services billed separately

- Missing financial assistance checks for uninsured/self-pay

✅ ML Anomaly Detection

- Isolation Forest model trained on historical distributions

- Computes a suspicion_score per claim

- Higher score → more likely fraudulent or erroneous

🗄 Database Schema (PostgreSQL)
## 🗄 Database Schema (PostgreSQL)

### **claims**
| Field           | Type      |
|-----------------|-----------|
| id              | UUID      |
| claim_id        | TEXT      |
| member_id       | TEXT      |
| provider_id     | TEXT      |
| date_of_service | DATE      |
| cpt_code        | TEXT      |
| charge_amount   | NUMERIC   |
| created_at      | TIMESTAMP |

### **audit_results**
| Field             | Type      |
|------------------|-----------|
| id               | UUID      |
| claim_id (FK)    | UUID      |
| issues_found     | JSONB     |
| suspicion_score  | NUMERIC   |
| recommended_action | TEXT    |
| audit_timestamp  | TIMESTAMP |


### ✅ Future Roadmap
Feature	Status
JWT authentication	Planned
Provider appeals portal	Planned
Real-time streaming ingestion (Kafka / Kinesis)	Planned
Dashboard for savings + provider patterns	Planned
Automatic medical record retrieval	Future

### 🧪 Testing
pytest -q

### ✅ License

### ✅ Acknowledgements

ClaimMatrix was inspired by real payment integrity workflows used by self-insured employers, health plans, and audit vendors to prevent financial leakage and reduce ERISA compliance exposure.