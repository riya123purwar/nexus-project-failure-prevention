# AETHER EV synthetic demo data

`aether_ev.json` is a fictional, internally linked demo project. It contains 18 entities, 21 relationships, 12 activities, five synthetic source records and five ground-truth findings. Planted issues include a conflicting test date, unconfirmed thermal-lab availability, unsupported alternate-supplier assumptions, an absent approval gate and an unscheduled charging verification activity.

The excerpts and dates are invented for demonstration. The project starts 18 April 2026; schedule durations are calendar days with finish-to-start dependencies. The delay control is a hypothetical change to battery arrival. The `sources/` directory contains TXT and CSV samples for the current upload endpoint; they can reproduce extraction only after Vertex AI Gemini is configured.
