# FRIDAY Proactive Intelligence

FRIDAY now has a bounded proactive runtime.

## Mental model

observe -> evaluate -> decide -> inform

FRIDAY does not need a chat message before every useful interaction.

### Event-driven path

1. Existing FRIDAY components publish FridayEvent events.
2. ProactiveEngine observes those events.
3. Observers convert important events into ProactiveSignal candidates.
4. AttentionManager scores importance, urgency, relevance, and confidence.
5. Low-value signals are silently ignored.
6. Important signals become proactive_message events.
7. Connected clients receive the message through the existing WebSocket.
8. Messages are also persisted in the private FRIDAY runtime database.

### Periodic cognition

CognitionLoop runs once per configured interval and asks the existing FRIDAY model one bounded question:

Is there one concrete, useful reason to interrupt Tirth right now?

If there is nothing useful, the model must return NOOP.

This is deliberately not an unrestricted autonomous reasoning loop.

## Endpoints

- GET /proactive/messages — recent persisted proactive messages.
- POST /proactive/check — run one cognition cycle immediately.
- POST /proactive/attention-test — verify WebSocket/UI notification delivery.

## Configuration

Environment variables use the FRIDAY_ prefix:

- FRIDAY_PROACTIVE_ENABLED=true
- FRIDAY_PROACTIVE_COGNITION_ENABLED=true
- FRIDAY_PROACTIVE_COGNITION_INTERVAL_SECONDS=3600
- FRIDAY_PROACTIVE_INITIAL_DELAY_SECONDS=60

The periodic loop is throttled to at least five minutes.

## OSIRIS

OSIRIS is already available through the research/tool layer. It remains read-only and can be connected to a future proactive watcher by topic. No always-on external polling is enabled by default, preventing unnecessary API usage and noise.

## JEV

JEV is not a runtime dependency. core/decision_engine.py provides FRIDAY's current small, deterministic policy layer so the architecture can evolve without coupling the core to JEV.
