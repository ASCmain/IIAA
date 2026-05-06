# IIAA — International Intelligent Accounting Assistant

IIAA is a local-first grounded AI prototype designed to support professional analysis of IAS/IFRS topics through verifiable documentary evidence.

The project was developed as part of a master's thesis project work in the context of financial management and accounting analysis. Its objective is not to replace professional judgment, but to support it with evidence-based retrieval, traceable outputs, and controlled response generation.

## Project purpose

The prototype explores whether a locally executed, grounded AI assistant can provide more defensible support than general-purpose generative AI systems when dealing with International Accounting Standards and related regulatory sources.

The system is designed for use cases such as:

- technical memo drafting support
- accounting policy analysis
- audit working-paper support
- guided review of IAS/IFRS-related questions
- controlled benchmarking against public generalist AI systems

## Key design principles

IIAA is built around a few core principles:

- local-first execution
- grounded retrieval over curated documentary sources
- evidence-based answering
- traceability and reproducibility
- abstention when evidence is weak or insufficient
- support for professional judgment rather than automated substitution

## Current repository scope

This repository contains:

- source code for the IIAA prototype
- technical specifications and development documentation
- metadata schemas and sample manifests
- glossary seed resources
- benchmark-related code and utilities
- selected public or reproducible documentary references

This repository does **not** include local runtime artifacts or sensitive configuration, including:

- `.env`
- local virtual environments such as `.venv/`
- local vector database storage such as `qdrant_data/`
- debug and backup material such as `debug_dump/`
- generated caches, logs, and temporary runtime outputs

Use `.env.example` as the reference template for local configuration.

## Architecture overview

The prototype follows a modular local pipeline:

1. source registration and corpus management
2. parsing and normalization of selected regulatory texts
3. deterministic chunk construction
4. vector indexing in Qdrant
5. query routing and retrieval orchestration
6. evidence evaluation and response generation
7. benchmark execution and result export

The system has been developed as a configuration-controlled prototype, with progressive milestones and tagged versions.

## Technical stack

Main components currently used in the project include:

- Python
- Ollama for local LLM and embedding execution
- Qdrant as vector database
- Streamlit for debugging and inspection UI
- structured telemetry for reproducibility and analysis

The project follows a local-first development workflow and was developed primarily on Apple Silicon macOS.

## Repository structure

- `apps/` — CLI and app entrypoints
- `src/` — core modules and libraries
- `docs/` — technical notes, policies, specs, benchmark documentation
- `data/` — glossary seeds, source registries, schemas, sample manifests
- `corpus/` — corpus catalog and source-related metadata scaffolding
- `telemetry/` — telemetry schemas and minimal repository scaffolding

## Setup notes

A typical local setup requires:

- Python 3.x
- a local virtual environment
- Ollama running locally
- Qdrant available locally
- a project-specific `.env` file derived from `.env.example`

Example high-level flow:

1. create and activate the virtual environment
2. install project dependencies
3. configure `.env`
4. start local services
5. run ingestion / indexing commands
6. run UI or benchmark commands

Because this repository evolved through multiple milestones, exact operational commands may vary by phase and by branch history. Refer to the scripts under `apps/` and the technical documentation in `docs/`.

## Important limitations

IIAA is a prototype and should not be treated as a production decision system.

In particular:

- answer quality depends on corpus scope and source quality
- absence of evidence should not be confused with evidence of absence
- benchmark outcomes are sensitive to prompt framing, corpus coverage, and retrieval choices
- the assistant is intended to support, not replace, accounting, audit, or legal-professional judgment

## Sources and redistribution note

Some source materials, regulatory texts, manifests, and derived artifacts may be included only in part, or represented through metadata, hashes, or reproducible acquisition instructions, depending on repository scope and redistribution constraints.

Users of this repository remain responsible for verifying the licensing and reuse conditions of third-party source materials.

## Versioning and governance

The repository uses Git-based configuration control with:

- small descriptive commits
- append-only changelog updates
- semantic milestone tags
- separation between versioned source code and excluded runtime artifacts

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for the full license text and `NOTICE` for attribution information.

## Attribution and citation

If you reuse this repository in academic, professional, or internal research contexts, preserve license and notice files and cite the IIAA project appropriately in accompanying documentation.

## Status

Prototype published for controlled technical and academic reference.
