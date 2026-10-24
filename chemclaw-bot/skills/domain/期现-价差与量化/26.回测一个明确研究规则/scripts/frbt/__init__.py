# -*- coding: utf-8 -*-
"""frbt — futures rule backtest toolkit.

Modules
    spec       rule specification model, validation, fingerprinting
    data       loading and look-ahead-free availability alignment
    contracts  real-contract mapping, roll schedule, delivery no-trade window
    signal     indicator transforms and per-op rule evaluation
    engine     event-driven backtest loop (entry/exit/roll/costs/equity)
    metrics    performance statistics, drawdowns, annual/monthly tables
    analysis   declared sensitivity grid, out-of-sample split, block bootstrap
    report_html  self-contained interactive research platform
    report_xlsx  auditable workbook with live formulas
"""
__version__ = "1.0.0"
