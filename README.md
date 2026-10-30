# AMAGI & Althea Ecosystem

**Architectural, Guaranteed Integrity (A.G.I.) for Life-Critical Systems**

---

## Overview

This repository hosts the complete **AMAGI & Althea Ecosystem** — a dual-architecture framework for:

1. **AMAGI**: Hardware-enforced AI Safety and Compliance (EU AI Act, IEC 61508, ISO/IEC 15408, NIST AI RMF).
2. **Althea**: Open Bioengineering Architecture for Precision Oncology (CRISPR-TTP).

**Author**: Alexey Mikhailovich Burlai
**ORCID**: [0009-0001-4679-5967](https://orcid.org/0009-0001-4679-5967)
**Contact**: lexintrud@gmail.com
**Legal Entities**: LLC "Althea" (Russia) — active · AGIAM Technologies Ltd (UK) — in formation (inactive shell, not an active legal entity)
**Corpus state of this README**: October 31, 2026

---

## Repository Structure

```
docs/
├── amagi/
│   ├── specs/                    # Architectural Specifications
│   │   ├── Amagi_Framework_v2.0_Specification.pdf
│   │   ├── Amagi_NIPU_v1.1_Specification.pdf
│   │   ├── Amagi_MEM_v1.1_Specification.pdf
│   │   ├── Amagi_Master_Parameter_Sheet_v2.1.pdf
│   │   ├── Amagi_Master_Parameter_Sheet_v2.0.pdf   # superseded by v2.1 (kept for reference)
│   │   ├── AMAGI_Master_Glossary_v1.0.pdf          # canonical terminology register
│   │   └── Amagi_Open_Specification_v1.1.pdf
│   │
│   ├── safety-analysis/          # Functional Safety Artifacts
│   │   ├── Amagi_HARA_v1.1.pdf
│   │   ├── Amagi_HARA_v1.0.pdf                     # superseded by v1.1 (kept for reference)
│   │   ├── Amagi_FMEDA_v1.1.pdf
│   │   ├── Amagi_FMEDA_v1.0.pdf                    # superseded by v1.1 (kept for reference)
│   │   ├── Amagi_Traceability_Matrix_v1.1.pdf
│   │   └── Amagi_Traceability_Matrix_v1.0.pdf      # superseded by v1.1 (kept for reference)
│   │
│   ├── verification/             # Formal verification artifacts (public, independently re-runnable)
│   │   └── AMAGI_Supplementary_SCC_Verification_v3.1.zip
│   │
│   ├── regulatory/               # Compliance & Regulatory Mapping
│   │   └── AMAGI_NIST_AI_RMF_Profile_v1.1.pdf
│   │
│   └── governance/               # Legal, Licensing & Institutional
│       ├── AGIAM_Charter_v1.2.pdf
│       ├── Amagi-SAPL_v2.0.pdf
│       ├── Amagi_Framework_Master_Version_Control_Document_v1.1.pdf
│       ├── Amagi_Architectural_Class_Definition_v1.1.pdf
│       └── Amagi_Framework_Trade_Secrets_Notice_v1.0.pdf
│
└── althea/
    ├── specs/                    # Bioengineering Specifications
    │   ├── Althea_v4.0_Official_Publication.pdf
    │   ├── Althea_AMAGI_Strategic_Partnership_Offer_v1.1.pdf
    │   └── Althea_AMAGI_Strategic_Partnership_Offer_v1.0.pdf   # superseded by v1.1 (kept for reference)
    │
    └── clinical-protocols/       # Standardized Operating Procedures
        └── SOP_Althea_CRISPR-TTP_v2.0.pdf
```

---

## AMAGI: Hardware-Enforced AI Safety

### Six Irreducible Invariants

| # | Invariant | Description |
|---|-----------|-------------|
| INV-001 | **Single-Core Determinism** | No caches, no speculation, fixed-latency instruction stream |
| INV-002 | **Hardware-Enforced Temporal Triad** | CRTM response ≤ 15 µs, EGW gate-close ≤ 50 ns, cryptographic attestation |
| INV-003 | **Dual-Tier Trust Model** | Tier-1 (Safety Kernel) vs Tier-2 (Application Sandbox), one-way isolation |
| INV-004 | **Memory Partitioning** | MAG (eFuse/OTP), SHMF (executable), Audit Log (append-only hash-chained) |
| INV-005 | **Cryptographic Determinism** | ML-KEM-1024, ML-DSA-44, SLH-DSA-128f — post-quantum from first boot |
| INV-006 | **Provable Shutdown** | Any invariant violation forces CRTM-safe state within one watchdog tick |

> **Terminology (binding, AMAGI Master Glossary v1.0 §8.3, resolution D-09):** the triad *Trigger → Programmable Delay → Localized Activation* is canonically named the **Temporal Triad**. In the AMAGI corpus the acronym *TTP* denotes the Tautological Truth Predicate; in the Althea corpus it denotes Temporally Programmed Delivery. The two are distinct and are not conflated.

### Key Subsystems

- **NIPU** (Neuro-Immune Processing Unit) — deterministic single-core safety controller with SCC FSM
- **MEM** (Self-Protecting Memory) — three-tier memory hierarchy (MAG / SHMF / Audit Diode)
- **MPS** (Master Parameter Sheet) — single source of truth for all quantitative parameters

### Formal Verification (SCC)

The SCC Promela model (`scc_amagi_v3`) has been exhaustively model-checked with SPIN 6.5.2: **20 verification runs covering 15 unique claims — all verified** (safety, liveness and counterexample suites; state space 25,927,680 states; parameters W=24, M=2,000,000). The complete public dataset — models, logs, counterexample trails, checksums — is published and independently re-runnable:
[SCC Verification Package v3.1.1](docs/amagi/verification/AMAGI_Supplementary_SCC_Verification_v3.1.zip) · [DOI 10.5281/zenodo.23817489](https://doi.org/10.5281/zenodo.23817489).

*Scope note: this is model-level (proof-of-logic) evidence; a board-level measurement campaign is designated Phase 2.*

### Regulatory Coverage

| Standard | Scope |
|----------|-------|
| ISO/IEC 15408 (Common Criteria) | EAL4+ Protection Profile |
| IEC 61508 | SIL 2 @1oo1 / SIL 3 @1oo2 (capability; Phase 2 target 2027) |
| ISO 26262 | ASIL D automotive safety |
| EU AI Act Annex IV | High-risk AI system documentation |
| NIST AI RMF (AI 100-1) | Target Profile |
| FDA PCCP | Pre-market Certifiable Change Package |
| NIST SP 800-218 | SSDF alignment |

---

## Althea: CRISPR-TTP Bioengineering

### Architecture

- **Target**: Fusion-driven cancers (Ewing Sarcoma, EWSR1-FLI1)
- **Mechanism**: CRISPR-Cas9 edited autologous dendritic cells (>94% efficiency) + FUS-activated HOF nanoparticles
- **Delivery**: Temporally Programmed Delivery (TTP) via MR-guided Focused Ultrasound
- **AI Co-pilot**: Real-time personalization (89.3% sgRNA prediction accuracy)

### Regulatory Status

- **EMA**: ATMP classification determined (Feb 2026)
- **FDA CBER**: INTERACT meeting confirmed (Feb 2026)
- **Russian MoH**: Expert evaluation completed (Feb 2026)
- **Peer-reviewed**: [Frontiers in Genetics, 2026](https://doi.org/10.3389/fgene.2026.1727708) — article type: *Brief Research Report*; all efficacy figures are computational projections ("Projected Efficacy" / "in silico modeling predicts"); wet-lab validation is the explicit next step
- *Regulatory status as reported in the Strategic Partnership Offer (February 2026), carried forward*

---

## Publications & DOIs

### AMAGI Framework (AI Safety)

| Document | Version | DOI | File |
|:---|:---|:---|:---|
| **Framework** | v2.0 | [10.5281/zenodo.20753400](https://doi.org/10.5281/zenodo.20753400) | `docs/amagi/specs/` |
| **NIPU** (Processor) | v1.1 | [10.5281/zenodo.20753401](https://doi.org/10.5281/zenodo.20753401) | `docs/amagi/specs/` |
| **MEM** (Memory) | v1.1 | [10.5281/zenodo.20753402](https://doi.org/10.5281/zenodo.20753402) | `docs/amagi/specs/` |
| **Master Parameter Sheet** | **v2.1.1** | [10.5281/zenodo.23817440](https://doi.org/10.5281/zenodo.23817440) | `docs/amagi/specs/` |
| **Master Glossary** (terminology canon) | v1.0.1 | [10.5281/zenodo.23817360](https://doi.org/10.5281/zenodo.23817360) | `docs/amagi/specs/` |
| **Open Specification** | v1.1 | [10.5281/zenodo.20753403](https://doi.org/10.5281/zenodo.20753403) | `docs/amagi/specs/` |
| **HARA** | **v1.1.1** | [10.5281/zenodo.23817463](https://doi.org/10.5281/zenodo.23817463) | `docs/amagi/safety-analysis/` |
| **FMEDA** | **v1.1.1** | [10.5281/zenodo.23817447](https://doi.org/10.5281/zenodo.23817447) | `docs/amagi/safety-analysis/` |
| **Traceability Matrix** | **v1.1.1** | [10.5281/zenodo.23817470](https://doi.org/10.5281/zenodo.23817470) | `docs/amagi/safety-analysis/` |
| **SCC Verification Package** | v3.1.1 | [10.5281/zenodo.23817489](https://doi.org/10.5281/zenodo.23817489) | `docs/amagi/verification/` |
| **NIST AI RMF Profile** | v1.1 | [10.5281/zenodo.20753404](https://doi.org/10.5281/zenodo.20753404) | `docs/amagi/regulatory/` |
| **S-APL License** | v2.0 | [10.5281/zenodo.20753406](https://doi.org/10.5281/zenodo.20753406) | `docs/amagi/governance/` |
| **AGIAM Charter** | v1.2 | [10.5281/zenodo.20753872](https://doi.org/10.5281/zenodo.20753872) | `docs/amagi/governance/` |
| **Master Version Control Document** | v1.1.1 | [10.5281/zenodo.23817478](https://doi.org/10.5281/zenodo.23817478) | `docs/amagi/governance/` |
| **Architectural Class Definition** | v1.1 | [10.5281/zenodo.20145198](https://doi.org/10.5281/zenodo.20145198) | `docs/amagi/governance/` |
| **Trade Secrets Notice** | v1.0 | [10.5281/zenodo.17886699](https://doi.org/10.5281/zenodo.17886699) | `docs/amagi/governance/` |

*Superseded (kept in `docs/` for reference):* Master Parameter Sheet v2.0 — [10.5281/zenodo.20145212](https://doi.org/10.5281/zenodo.20145212); HARA v1.0 — [10.5281/zenodo.20753408](https://doi.org/10.5281/zenodo.20753408); FMEDA v1.0 — [10.5281/zenodo.20753410](https://doi.org/10.5281/zenodo.20753410); Traceability Matrix v1.0 — [10.5281/zenodo.20753412](https://doi.org/10.5281/zenodo.20753412).

*October 31, 2026 metadata correction:* the `.1` releases (v2.1.1, v1.0.1, v1.1.1 ×4, v3.1.1) publish **byte-identical files** with corrected author metadata (canonical creator name form *Alexey Mikhailovich Burlai* across the corpus). The prior version DOIs (v2.1, v1.0, v1.1, v3.1) remain valid and resolve to their respective records; document contents and in-document version designations are unchanged.

### Althea Framework (Bioengineering)

| Document | Version | DOI / Link | File |
|:---|:---|:---|:---|
| **Official Publication** | v4.0 | [10.3389/fgene.2026.1727708](https://doi.org/10.3389/fgene.2026.1727708) | `docs/althea/specs/` |
| **Genomic Innovation Spec** | v4.0 | [10.5281/zenodo.17780623](https://doi.org/10.5281/zenodo.17780623) | Zenodo |
| **Clinical Protocol (SOP)** | v2.0 | [10.5281/zenodo.17676423](https://doi.org/10.5281/zenodo.17676423) | `docs/althea/clinical-protocols/` |
| **Strategic Partnership Offer** | **v1.1** | [10.5281/zenodo.23816599](https://doi.org/10.5281/zenodo.23816599) | `docs/althea/specs/` |
| **TTP Architecture** | v3.0 | [10.5281/zenodo.17237907](https://doi.org/10.5281/zenodo.17237907) | Zenodo |
| **CRISPR Autovaccination** | v3.0 | [10.5281/zenodo.17246573](https://doi.org/10.5281/zenodo.17246573) | Zenodo |

*Superseded (kept in `docs/` for reference):* Strategic Partnership Offer v1.0 — [10.5281/zenodo.18718186](https://doi.org/10.5281/zenodo.18718186).

---

## Licensing Model

This project operates under a **Dual-Layer Licensing Strategy**:

### 1. Open Science Layer (Free)

- **AMAGI Specifications**: CC BY-NC 4.0 (Non-Commercial Research).
- **Althea Protocols**: CC0 1.0 (Public Domain).
- **Goal**: Establish Prior Art, enable academic research, prevent patent thickets.

### 2. Commercial Layer (S-APL v2.0)

- **License**: Strict Architectural Principle License (S-APL).
- **Full text**: [10.5281/zenodo.20753406](https://doi.org/10.5281/zenodo.20753406)
- **Governed by**: Laws of England and Wales.
- **Covers**: Commercial deployment, "Amagi Compliant" certification, access to Hard IP Suite (GDSII, Netlists).
- **Contact**: lexintrud@gmail.com (Subject: "S-APL Inquiry").

> **Note**: Access to trade secrets (implementation details, calibration data) requires an NDA + valid S-APL license.

---

## Strategic Partnerships

We invite collaboration with:

- **Semiconductor Companies**: For ASIC/FPGA implementation of AMAGI Hard IP.
- **Biotech & Pharma**: For clinical translation of Althea protocols.
- **Regulators & Auditors**: For certification pathway development.
- **Research Institutions**: For joint grants and validation studies.

**Next Steps**:

1. Review the [Strategic Partnership Offer v1.1](docs/althea/specs/Althea_AMAGI_Strategic_Partnership_Offer_v1.1.pdf) (concrete asks A1–A6, evidence classes, risk register).
2. Contact us at `lexintrud@gmail.com`.
3. Execute NDA and S-APL License (for commercial projects).

---

## Legal & Governance

- **Founding Charter**: [AGIAM Charter v1.2](docs/amagi/governance/AGIAM_Charter_v1.2.pdf)
- **IP Succession**: Shamir 3-of-5 secret sharing (Charter §5)
- **Jurisdiction**: Laws of England and Wales.
- **Dispute Resolution**: Binding arbitration in London.
- **Ethical Guardrails**: Strict prohibition on mass surveillance, autonomous weapons, and social scoring. Violations result in immediate license revocation.

---

## Disclaimer

- **Medical**: The Althea framework is a research protocol. It does not constitute medical advice. Clinical use requires regulatory approval and independent validation.
- **Safety**: AMAGI specifications are reference architectures. Implementation responsibility lies with the licensee.
- **No Warranty**: Provided "AS-IS" without warranties of any kind.

---

© 2025–2026 Alexey M. Burlai. All rights reserved.
**AMAGI**: Trust by Design. **Althea**: Survival by Architecture.
