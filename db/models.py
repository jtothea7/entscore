"""
Data models as dataclasses
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Project:
    id: Optional[int] = None
    domain: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Competitor:
    id: Optional[int] = None
    analysis_id: Optional[int] = None
    url: str = ""
    position: int = 0
    word_count: int = 0
    heading_count: int = 0
    entity_count: int = 0
    scrape_success: bool = False
    scrape_method: str = ""


@dataclass
class Entity:
    id: Optional[int] = None
    analysis_id: Optional[int] = None
    entity_text: str = ""
    entity_type: Optional[str] = None
    client_count: int = 0
    client_salience: float = 0.0
    competitor_frequency: int = 0
    competitor_avg_salience: float = 0.0
    gap_status: str = ""  # 'strong', 'weak', 'missing'


@dataclass
class Analysis:
    id: Optional[int] = None
    project_id: Optional[int] = None
    url: str = ""
    keyword: str = ""
    health_score: Optional[float] = None
    entity_coverage_score: Optional[float] = None
    heading_score: Optional[float] = None
    word_count_score: Optional[float] = None
    readability_score: Optional[float] = None
    link_score: Optional[float] = None
    client_word_count: int = 0
    competitor_avg_word_count: float = 0.0
    recommended_word_count_min: int = 0
    recommended_word_count_max: int = 0
    created_at: Optional[datetime] = None
    analysis_duration_seconds: float = 0.0
    competitors_analyzed: int = 0
    competitors_failed: int = 0
    # Non-persisted fields for in-memory use
    competitors: List[Competitor] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)


@dataclass
class GSCData:
    id: Optional[int] = None
    url: str = ""
    keyword: str = ""
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    opportunity_score: float = 0.0
    uploaded_at: Optional[datetime] = None


@dataclass
class APIUsage:
    id: Optional[int] = None
    analysis_id: Optional[int] = None
    endpoint: str = ""
    cost: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class AnalysisResult:
    """Full analysis result used for rendering - assembled from DB queries"""
    analysis: Analysis = field(default_factory=Analysis)
    competitors: List[Competitor] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    # Client page data
    client_headings: List[Dict] = field(default_factory=list)
    client_internal_links: int = 0
    client_external_links: int = 0
    client_images_count: int = 0
    client_images_with_alt: int = 0
    client_schema_types: List[str] = field(default_factory=list)
    client_style: Dict = field(default_factory=dict)
    # Competitor aggregates
    competitor_avg_h2_count: float = 0.0
    competitor_avg_internal_links: float = 0.0
    competitor_schema_frequency: Dict = field(default_factory=dict)
    competitor_style: Dict = field(default_factory=dict)
    # Brief
    brief_text: str = ""
    # API cost
    total_cost: float = 0.0
    # Previous analysis for comparison
    previous_analysis: Optional[Analysis] = None
