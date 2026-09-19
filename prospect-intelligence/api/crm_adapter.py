"""
CRM Export Adapter.
Defines the CRMAdapter interface and provides a MockHubSpotAdapter
that writes JSON + CSV to /data/exports/.

A future LiveHubSpotAdapter can implement the same interface without
changing anything else in the system.

IMPORTANT: This MVP NEVER writes to a live/production CRM.
"""
from __future__ import annotations

import csv
import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from api.models import CRMExportRecord, ResearchBrief
from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class CRMAdapter(ABC):
    """Single interface — swap implementations without touching the pipeline."""

    @abstractmethod
    async def export(self, brief: ResearchBrief) -> CRMExportRecord:
        """Map a completed ResearchBrief to a CRMExportRecord and persist it."""
        ...


# ---------------------------------------------------------------------------
# Mock HubSpot adapter (sandbox / local files only)
# ---------------------------------------------------------------------------

class MockHubSpotAdapter(CRMAdapter):
    """
    Writes JSON + CSV to /data/exports/{job_id}_crm.{json,csv}.
    Also checks for duplicates against a sample CRM dataset.
    """

    def __init__(self) -> None:
        self._exports_dir = Path(settings.exports_path)
        self._exports_dir.mkdir(parents=True, exist_ok=True)
        self._crm_sample: list[dict] = self._load_crm_sample()

    def _load_crm_sample(self) -> list[dict]:
        path = Path(settings.crm_sample_path)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not load CRM sample: %s", exc)
        return []

    async def export(self, brief: ResearchBrief) -> CRMExportRecord:
        # ── Map to HubSpot-style fields ─────────────────────────────────
        snapshot = brief.snapshot
        contact_dict = brief.contact
        score = brief.lead_score

        company_name = snapshot.get("company_name", "")
        website = snapshot.get("website", "")

        company_fields = {
            "name": company_name,
            "website": website,
            "industry": snapshot.get("sector", ""),
            "city": snapshot.get("location", ""),
            "country": snapshot.get("geography", ""),
            "numberofemployees": snapshot.get("size", ""),
            "description": snapshot.get("overview", ""),
        }

        contact_fields = {
            "firstname": contact_dict.get("first_name", ""),
            "lastname": contact_dict.get("last_name", ""),
            "jobtitle": contact_dict.get("title", ""),
            "email": contact_dict.get("email", ""),
            "linkedin": contact_dict.get("linkedin", ""),
        }

        deal_fields = {
            "dealname": f"Coextend — {company_name}",
            "dealstage": "prospecting",
            "pipeline": "default",
            "lead_score": score.total,
            "lead_band": score.band,
            "priority": score.band,
            "notes": brief.next_action.action,
        }

        # ── Duplicate detection ──────────────────────────────────────────
        possible_dup = self._check_duplicate(company_name, website)

        record = CRMExportRecord(
            job_id=brief.job_id,
            company_fields=company_fields,
            contact_fields=contact_fields,
            deal_fields=deal_fields,
            lead_score_total=score.total,
            lead_score_band=score.band,
            possible_duplicate=possible_dup,
            exported_at=datetime.now(UTC),
        )

        # ── Write to sandbox files ────────────────────────────────────────
        await self._write_json(record)
        await self._write_csv(record)

        if possible_dup:
            logger.warning(
                "Possible CRM duplicate detected for '%s' (%s)", company_name, website
            )
        else:
            logger.info("CRM export written for job %s", brief.job_id)

        return record

    def _check_duplicate(self, company_name: str, website: str) -> bool:
        """
        Name/domain match against the sample CRM dataset.
        Returns True if a likely match is found.
        """
        if not company_name and not website:
            return False

        from urllib.parse import urlparse
        domain = urlparse(website).netloc.lstrip("www.") if website else ""
        name_lower = company_name.lower().strip()

        for record in self._crm_sample:
            existing_name = str(record.get("company_name", "")).lower().strip()
            existing_website = str(record.get("website", ""))
            existing_domain = urlparse(existing_website).netloc.lstrip("www.")

            name_match = name_lower and existing_name and name_lower == existing_name
            domain_match = domain and existing_domain and domain == existing_domain

            if name_match or domain_match:
                return True
        return False

    async def _write_json(self, record: CRMExportRecord) -> None:
        path = self._exports_dir / f"{record.job_id}_crm.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    async def _write_csv(self, record: CRMExportRecord) -> None:
        path = self._exports_dir / f"{record.job_id}_crm.csv"
        flat = {
            "job_id": record.job_id,
            "lead_score_total": record.lead_score_total,
            "lead_score_band": record.lead_score_band,
            "possible_duplicate": record.possible_duplicate,
            "exported_at": str(record.exported_at),
        }
        flat.update({f"company_{k}": v for k, v in record.company_fields.items()})
        flat.update({f"contact_{k}": v for k, v in record.contact_fields.items()})
        flat.update({f"deal_{k}": v for k, v in record.deal_fields.items()})

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=flat.keys())
            writer.writeheader()
            writer.writerow(flat)
