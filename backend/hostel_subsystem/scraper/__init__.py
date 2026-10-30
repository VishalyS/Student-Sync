"""
Scraper module for Student Sync - Hostel subsystem.
"""
from scraper.auth import AuthenticatedSession, HostelAuthenticator
from scraper.client import HostelHttpClient
from scraper.endpoints import EndpointDefinition, HostelEndpoints
from scraper.extractor import HostelExtractor
from scraper.raw import (
    RawExtractionBundle,
    RawResponseRecord,
    calculate_payload_hash,
)

__all__ = [
    "HostelHttpClient",
    "HostelAuthenticator",
    "AuthenticatedSession",
    "HostelEndpoints",
    "EndpointDefinition",
    "HostelExtractor",
    "RawResponseRecord",
    "RawExtractionBundle",
    "calculate_payload_hash",
]
