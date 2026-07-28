"""
=========================================================
NTIS Historical Market Memory Engine
Module  : hmme_engine.py
Version : 1.0.0
Release : HMME-06

Purpose:
    Central orchestrator for HMME learning pipeline.

Pipeline:
    Candidate Selector
        ->
    Outcome Filter
        ->
    Learning Statistics
        ->
    Memory Repository
        ->
    Memory Index
=========================================================
"""

from __future__ import annotations

import logging
import pandas as pd

from .candidate_selector import CandidateSelector
from .outcome_filter import OutcomeFilter
from .learning_statistics import LearningStatistics
from .memory_repository import MemoryRepository
from .memory_index import MemoryIndex


class HMMEEngine:

    def __init__(
        self,
        memory_file,
        logger=None,
    ):

        self.logger = logger or logging.getLogger(__name__)

        self.selector = CandidateSelector()
        self.outcome_filter = OutcomeFilter()
        self.statistics = LearningStatistics()

        self.repository = MemoryRepository(
            memory_file,
            logger=self.logger,
        )

        self.index = MemoryIndex(
            logger=self.logger,
        )


    def build_memory(
        self,
        candidate_data: pd.DataFrame,
    ):

        qualified = self.outcome_filter.filter(
            candidate_data
        )

        statistics = self.statistics.calculate(
            qualified
        )

        updated_memory = self.repository.update(
            statistics
        )

        self.index.build(
            updated_memory
        )

        return updated_memory
