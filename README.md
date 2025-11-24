# IntelligensiDeploy 

One-Button Cloud Deployments for Intelligensi.ai

IntelligensiDeploy is the unified deployment engine for the entire Intelligensi.ai ecosystem.
It enables one-button, fully automated deployments across GPU and non-GPU infrastructure — including image generation servers, AI inference nodes, Weaviate vectors, video generation workers, and future micro-services.

This repository defines a declarative, repeatable, codified deployment pipeline using:

Terraform → Provision GPU instances (Lambda Cloud)

Docker → Build & ship containerized services

Bash Harness → Orchestrate deploy flows

Environment Profiles → dev, staging, prod

Codex-compatible scripts → Every step machine-editable and automated

Our goal:
Click once → launch the entire AI stack.
Zero manual SSH. Zero drift. Zero guesswork.