from __future__ import annotations


def build_bls_overlay(cpi_payload: dict) -> dict:
    return {"bls_overlay_available": bool(cpi_payload), "warnings": [] if cpi_payload else ["BLS overlay missing."]}
