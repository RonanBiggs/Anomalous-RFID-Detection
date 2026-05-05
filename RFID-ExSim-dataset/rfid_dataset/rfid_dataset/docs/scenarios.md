Experiment Scenarios (S1–S5)

This document describes the experimental scenarios implemented in the RFID dataset, including their objectives, setup conditions, controlled parameters, and expected behavioral characteristics. Each scenario represents a distinct operational condition of the RFID system, ranging from baseline acquisition to controlled adversarial stress conditions.

S1 — Baseline Legitimate Reads

Objective:
To establish reference measurements of normal RFID tag–reader interactions under controlled and repeatable conditions.

Description:
A single reader interacts with individual passive tags across multiple distances and orientations. This scenario provides the ground truth distribution of timing, signal consistency, and read stability.

Controlled Parameters:

Distances: 1 cm, 3 cm, 4 cm

Orientations: 0°, 45°, 90°

Repetitions: 100–150 read attempts per (tag × distance × orientation) condition

Recorded Data Fields:
Timestamp, device identifier, tag identifier, UID hash, event type, raw payload.

Intended Use:
Serves as the baseline reference for comparison against scenarios involving collisions, duplicates, replays, or high-rate stress.

S2 — Simultaneous Read / Collision Scenario

Objective:
To characterize timing differences, collision patterns, and missed-read behavior when two readers attempt to read the same tag concurrently.

Description:
Two identical ESP32-MFRC522 readers are activated simultaneously while a tag is placed in the region of overlapping electromagnetic fields. Sessions emphasize synchronized triggering and stable positioning.

Controlled Parameters:

Readers: ESP32_A and ESP32_B active concurrently

Tag placement: Centralized position between antennas

Iterations: 150 acquisition cycles per tag

Key Measurements:

Inter-reader timestamp differences

Asymmetric or missed reads

Collision occurrence frequency

Order-of-detection patterns between devices

S3 — Tag Duplication / UID Equivalence

Objective:
To observe system behavior in the presence of tags sharing the same UID (true clones or operationally equivalent identifiers).

Description:
Depending on hardware availability, either a writable tag is programmed with a cloned UID, or a pair of distinct tags is assigned the same logical UID within metadata to simulate ambiguity.

Key Measurements:

Frequency of ambiguous identification

Overlapping reads attributed to the same UID

Stability of device assignment when identical identifiers coexist

S4 — Replay / Controlled Injection Scenario

Objective:
To emulate replay-like conditions, where a previously captured tag UID is reintroduced into the system through cloned hardware or controlled software injection.

Description:
Reader A captures legitimate tag events. In parallel or in subsequent sessions, Reader B introduces a tag reproducing the same UID, or selective replay events are injected through software for timing analysis.

Key Measurements:

Replay latency distributions

Injection success ratios

Timing irregularities compared to baseline reads

Consistency between legitimate and replayed sequences

S5 — High-Rate Read / Flooding (DoS-Like Stress)

Objective:
To quantify reader performance and stability under sustained high-frequency reading attempts, simulating load or denial-of-service stress.

Description:
The tag is continuously presented or moved rapidly in front of the reader. High-intensity acquisition loops generate large volumes of read attempts in short intervals.

Controlled Parameters:

Bursts: 1,000–5,000 read attempts

Mode: Continuous tag presence or fast manual oscillation

Optional: Servo-based automation for repeatability

Key Measurements:

Success vs failure ratio over time

Throughput evolution during bursts

Signal loss patterns or saturation thresholds