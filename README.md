# IntelligensiDeploy

## Purpose
IntelligensiDeploy is a one-click deployment engine for AI infrastructure. It streamlines provisioning GPU servers, orchestrating containers, and bootstrapping services like Weaviate or image/video generation backends so teams can focus on models instead of plumbing.

## Features
- GPU deployment pipelines for high-performance inference nodes
- Docker orchestration templates for reproducible services
- Weaviate launcher for vector databases
- Image and video generation engine scaffolds
- Config-driven workflows designed for full automation

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/IntelligensiDeploy.git
   cd IntelligensiDeploy
   ```
2. (Recommended) Create and activate a virtual environment.
3. Install Python CLI dependencies:
   ```bash
   pip install -r requirements.txt  # placeholder for future dependencies
   ```

## CLI Usage
Run the Typer-based CLI for deployment actions:
```bash
python -m src.cli.main --help
python -m src.cli.main deploy image-server
python -m src.cli.main init
```

## Vision
IntelligensiDeploy aims to deliver fully automated AI infra deployments across clouds and on-prem with a single command. The roadmap includes turnkey GPU provisioning, Docker/VM rollouts, vector databases, media generation servers, and monitoring integrations for zero-drift operations.
