RFID Dataset — Methodology
1. Objective

This document outlines the complete experimental methodology used to collect, structure, and validate the RFID dataset. The goal is to generate reproducible, well-documented data covering both baseline RFID behaviour and adversarial/anomalous conditions across scenarios S1 → S5.

2. Methodological Pipeline Overview

The experimental workflow consists of seven steps:

Experiment Design
Definition of tag sets, distance/orientation grids, repetitions, scenario parameters, and session plans stored under data/plans/.

Data Acquisition
Collection of raw RFID read events using dual ESP32-MFRC522 readers operated via
serial_logger_dual_enh.py.

Session Metadata Recording
Capture of session identifiers, context, and parameters in metadata files such as
meta_sessions_*.csv.

Data Merging & Structuring
Consolidation of raw JSONL logs into unified files (e.g.,
rfid_dataset_S1_all.jsonl) using merge_sessions_s1.py or the generic merger for multi-scenario aggregation.

Preprocessing & Canonicalization
Standardisation of fields, timestamp parsing, UID hashing, tag ID normalization, and filtering of malformed or corrupted events.

Analysis & Visualisation
Execution of analysis scripts (e.g., analyze_sessions_s*_basic.py) to produce summary tables, histograms, throughput graphs, collision plots, and scenario-specific metrics.

Documentation & Protocol Tracking
Maintenance of reproducibility materials, hardware wiring diagrams, firmware notes, and experimental protocol details in the docs/ directory.

3. Canonical Data Format

Each dataset entry corresponds to a single RFID read event represented as one JSON object per line (*.jsonl).
The canonical schema contains:

| Field             | Description                                                              |
| ----------------- | ------------------------------------------------------------------------ |
| `timestamp_iso`   | ISO-8601 UTC timestamp (e.g., `2025-11-04T08:12:55.469573Z`).            |
| `session_id`      | Unique session identifier (e.g., `S20251104_S1_TAG01_d1_o0_run1`).       |
| `scenario`        | Scenario code (S1 … S5).                                                 |
| `device_id`       | Reader identifier (`ESP32_A`, `ESP32_B`).                                |
| `port`            | Serial port assigned to device (e.g., `COM4`, `/dev/ttyUSB0`).           |
| `tag_local_id`    | Internal tag label (`TAG01` … `TAG12`).                                  |
| `uid_hash`        | Salted hash of the tag UID for privacy-preserving uniqueness.            |
| `uid_plain_local` | Raw UID hex string (stored locally only; removed before public release). |
| `distance_cm`     | Physical distance between tag and reader (cm).                           |
| `orientation_deg` | Tag angular orientation relative to reader (0°, 45°, 90°).               |
| `event`           | Event type (`read_success`, `read_fail`, `error`, etc.).                 |
| `raw_payload`     | Raw MFRC522-reported payload for diagnostic purposes.                    |

4. Quality Control Procedures

Quality assurance is performed at both the acquisition and preprocessing stages:

Timestamp consistency
Ensure monotonic increasing timestamps within each session.

Read count validation
Compare observed read frequencies to the expected counts based on the experimental plans.

UID consistency
Verify that uid_hash maps uniquely and consistently to tag_local_id across all sessions.

Schema validation
Detect missing or malformed fields (e.g., occasional absent RSSI fields) and log calibration needs.

Error pattern inspection
Identify communication failures, desynchronizations, or abnormal inter-read delays.

5. Reproducibility Artifacts

The repository includes all files necessary to replicate the data collection:

Experimental Plans

data/plans/s1_plan.csv — exact tag/distance/orientation presentation order for S1.

Similar structured plans for S2–S5.

Session Metadata

Files such as meta_sessions_S1.csv describing start time, end time, operator, reader ID, etc.

Hardware & Firmware Documentation

firmware/esp32_reader/notes_wiring.md — wiring diagrams and configuration notes.

Acquisition Automation Scripts

scripts/run_plan_s1.py — executes S1 plan automatically, labels sessions, and manages logs.

All components are version-controlled to ensure fully reproducible dataset construction.

6. Ethical & Privacy Considerations

No human, personal, or biometric data is collected.

Tag UIDs are cryptographically hashed before release.

Only synthetic attack behaviours (replay, cloning attempts, flooding) are performed, with no external security systems targeted.

The dataset is intended exclusively for research on RFID robustness, collision handling, and anomaly detection.