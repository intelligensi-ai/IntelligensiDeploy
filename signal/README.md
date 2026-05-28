# Intelligensi.ai Signal

**Speak your intent. Let the city answer.**

Intelligensi.ai Signal is an agentic AI dashboard for London that helps people decide which events, opportunities, gatherings, and experiences are genuinely worth attending.

## Problem

London has too many competing options on any given evening: AI meetups, business mixers, cultural events, nightlife, gaming sessions, public talks, sports screenings, and community gatherings. The real cost is not only the ticket price. It is travel time, missed alternatives, crowd quality, weather, attendee fit, and whether the event actually supports the user's goal.

## Solution

Signal lets users describe their intent in natural language, then ranks London events using specialist agents for intent, discovery, transport, weather, cost, crowd/sentiment, attendee relevance, and final recommendation scoring.

The current prototype uses a rich simulated London dataset and deterministic local logic. The code is structured so mock adapters can later be replaced with Eventbrite, Meetup-style sources, TfL, London Datastore, Open-Meteo, venue listings, routing APIs, and sentiment feeds.

## User Journey

1. Open the dashboard.
2. Type or speak an intent such as: "I want to meet AI investors and senior engineers tonight after work. I'm travelling from Aldgate and I want to keep the total cost under GBP30."
3. Signal parses the goal, location, budget, category, time window, attendee targets, and priority weighting.
4. The map updates with relevant London event pins and non-linear travel effort rings.
5. The recommendation dashboard ranks the best options with a clear Signal Score.
6. The user compares alternatives and sees agent reasoning before deciding.
7. The mock registration action simulates an application without sending personal data anywhere.

## Agent Architecture

- **Intent Agent** extracts category, goal, desired attendee type, date window, start location, budget, travel tolerance, and priority weights.
- **Event Discovery Agent** filters and ranks a structured London event corpus. Future adapter: Eventbrite, Meetup, City of London open data, London Datastore, venue listings, and web search.
- **Transport Agent** estimates London travel as a non-linear network problem using location hubs, route affinity, interchanges, river/orbital penalties, and simulated disruption signals. Future adapter: TfL Journey Planner, OpenStreetMap, Google Maps, or a local transport graph.
- **Weather Agent** estimates weather impact by city zone. Future adapter: Open-Meteo, Met Office, or venue-local forecasts.
- **Cost Agent** combines ticket price, travel cost, food/drink estimate, and budget fit.
- **Crowd and Sentiment Agent** estimates crowd density, social energy, sentiment, and overcrowding risk.
- **Attendee Relevance Agent** scores whether the likely audience matches the user's intent.
- **Recommendation Agent** combines every signal into the final decision-support score and "worth it?" judgement.

## Scoring Model

Signal Score is a weighted estimate:

- Intent relevance: 25%
- Attendee relevance: 20%
- Travel effort: 15%
- Cost fit: 10%
- Timing suitability: 10%
- Sentiment: 10%
- Weather/city conditions: 5%
- Crowd suitability: 5%

The UI labels the output as simulated decision-support rather than live truth.

## Data Sources

The prototype includes at least 20 simulated London events across AI, business, culture, nightlife, sports, gaming, community, and education. Each event includes location, borough, times, price, tags, expected attendance, capacity, attendee profile, networking value, sentiment, source placeholder, and weather sensitivity.

Future sources:

- City of London open data
- London Datastore
- TfL API
- Eventbrite API
- Meetup-style event sources
- Open-Meteo weather API
- Google Maps or OpenStreetMap routing
- Social sentiment and venue/event listing APIs

## NVIDIA Hack for Impact Relevance

Signal demonstrates how local-first agentic AI can support real urban decisions using open models, open city data, and practical orchestration.

- **Economic systems impact:** better allocation of time, money, travel, networking, and opportunity.
- **Public services impact:** easier discovery of civic, cultural, educational, and community resources.
- **Urban operations impact:** event recommendations adapt to transport, weather, crowding, and city conditions.
- **Local-first AI:** deterministic agents can run locally today and later call open models for intent parsing, summarisation, ranking explanations, and adaptive planning.
- **NVIDIA hardware fit:** suitable for edge deployment on NVIDIA DGX Spark or ZGX Nano AI Station style local AI hardware, with future on-device open models, embedding search, routing graphs, and real-time city-signal fusion.

## Local Setup

```bash
npm install
npm run dev
```

Then open the Vite local URL, usually:

```text
http://localhost:5173
```

## Demo Script for Judges

Use this exact prompt:

```text
I want to meet AI investors and senior engineers tonight after work. I'm travelling from Aldgate and I want to keep the total cost under GBP30.
```

Signal should:

1. Parse the intent as AI/startup networking with investor and senior engineer attendee targets.
2. Filter the London event dataset to relevant after-work events.
3. Display ranked pins on the stylised London map.
4. Show travel effort rings from Aldgate.
5. Rank top events such as London AI Founders Mixer, Founder Dating / Co-founder Matching Night, Startup Pitch Night, and Women in AI Networking Evening.
6. Recommend the best event with a clear Signal Score and "worth it?" judgement.
7. Explain trade-offs around travel, cost, crowd density, attendee relevance, and confidence.
8. Compare alternatives in the comparison table.
9. Show the Signal trace, including Intent, Event Discovery, Transport, Cost, Weather, Attendee Relevance, and Recommendation agents.

## Future Roadmap

- Replace mock event corpus with live Eventbrite, Meetup-style, venue, and open-data adapters.
- Replace heuristic transport with TfL Journey Planner plus a local transport graph.
- Add local embedding search for event matching and attendee relevance.
- Add open-model intent parsing and explanation generation.
- Add calendar export and saved recommendations.
- Add richer profile memory with privacy-first local storage.
- Add real application/registration integrations with explicit consent.
- Add multi-person planning for groups with different locations and budgets.
- Add city operations views for event platforms, universities, councils, and tourism teams.
