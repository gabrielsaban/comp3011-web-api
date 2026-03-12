# Project Brief

## Module Context

This repository contains work for a university coursework assignment requiring the design, implementation, and presentation of a data-driven web API backed by a SQL database.

The objective is to demonstrate practical application of software engineering principles in the design of a real-world API system.

---

## Goal

Design and implement a data-driven REST API backed by a PostgreSQL database, exposing UK road traffic accident data enriched with meteorological observations, spatial clustering, and route risk scoring.

---

## Project

**UK Road Traffic Accidents API** — a data-driven REST API that combines STATS19 accident records with Met Office MIDAS weather observations, pre-computed DBSCAN spatial clusters, and a statistical route risk scoring model.

### Dataset

| Source | Description | Coverage | Volume |
|--------|-------------|----------|--------|
| STATS19 | DfT road safety accident, vehicle, and casualty records | 2019–2023 (5 years) | ~500,000 accidents |
| MIDAS | Met Office hourly surface weather observations | Matched by proximity and time | ~350 UK stations |

STATS19 is published under OGL v3 at https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-safety-data.
MIDAS is available via CEDA at https://catalogue.ceda.ac.uk/uuid/220a65615218d5c9cc9e4785a3234bd0 (free account required).

### Three Capability Pillars Beyond Core CRUD

1. **Weather Enrichment** — each accident record is matched to the nearest MIDAS weather station observation within ±1 hour, enabling analysis of accident severity against measured precipitation, visibility, temperature, and wind speed rather than the categorical codes in STATS19 alone. Expected coverage: ~85%.

2. **Spatial Clustering** — DBSCAN (epsilon=0.89km, min_samples=10, haversine metric, ball_tree algorithm) is run at import time over all accident coordinates to produce a `cluster` table. Clusters are labelled Low/Medium/High/Critical based on fatal rate percentage. Accident records carry a `cluster_id` foreign key.

3. **Route Risk Scoring** — `POST /analytics/route-risk` accepts a polyline (list of lat/lng waypoints) and decomposes it into 500m segments, scoring each against five factors (accident density, severity score, time-of-day risk, speed limit risk, cluster proximity) with a weighted formula to produce a normalised 0–1 risk score per segment and an aggregate route summary.

### Reference Documents

- `docs/api-spec.md` — full REST API specification (43 endpoints, request/response schemas, conventions)
- `docs/architecture.md` — system design: SQL DDL, import pipeline, DBSCAN parameters, route risk formula, technology stack, application structure, indexing strategy

---

## Project Status

Design phase complete. Implementation pending.

All endpoints are fully specified in `docs/api-spec.md`. The database schema, import pipeline, and scoring model are documented in `docs/architecture.md`. The next step is building the FastAPI application and import scripts.

---

## Coursework Objectives

The coursework evaluates the following capabilities:

- Application of software engineering principles to API design
- Design and implementation of a structured, data-driven backend system
- Justification of design choices including technology stack and architecture
- Demonstration of curiosity, creativity, and independent development
- Clear documentation and explanation of implementation decisions

The project should reflect good professional practices in API development.

---

## Target Quality Standard

The highest grading bands reward projects that demonstrate:

- Exceptional originality or interesting data use
- Novel integrations, insights, or analytical features
- Strong architectural decisions and clean code quality
- High-quality, well-polished documentation
- Evidence of genuine curiosity and exploration in the design process
- Effective and thoughtful use of Generative AI as a development tool

The goal is to produce a system that is technically sound, well justified, and clearly documented.

---

## Technical Requirements

At minimum the API must:

- Use a relational SQL database
- Implement CRUD operations for at least one data model
- Provide at least four HTTP endpoints
- Accept structured inputs and return structured responses (JSON)
- Use appropriate HTTP status codes and error handling
- Be runnable locally or via hosting

This project exceeds those minimums across all categories.

---

## API Documentation Requirements

The project must include clear API documentation.

Documentation may be generated or written using tools such as:

- Swagger / OpenAPI
- Postman collections
- Markdown documentation

The documentation must:

- Describe all available endpoints
- Specify request parameters and response formats
- Include example requests and responses
- Document authentication and error behaviour where applicable

The documentation must be referenced from the project `README.md`, and if generated as HTML should also be exported as a PDF.

---

## Repository Expectations

The repository should demonstrate good software development practice, including:

- Clear commit history showing development progress
- Readable project structure
- Well-organised source code
- Clear setup instructions in the README

The system should be understandable and defensible during the oral presentation.

---

## Generative AI Usage

Generative AI tools may be used as part of the development workflow.

Acceptable uses include:

- brainstorming project ideas and datasets
- designing database schemas
- generating boilerplate code
- debugging issues
- improving documentation

Use of AI must be declared in the final report, with reflection on how it contributed to the development process.

---

## Development Philosophy

The project should prioritise:

- clarity and maintainability
- sensible architectural choices
- realistic, defensible design decisions
- high-quality documentation

Overly complex systems or unnecessary abstractions should be avoided unless they clearly improve the design.
