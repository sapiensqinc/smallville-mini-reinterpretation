"""Simulation engine — drives the cognitive loop tick by tick.

Tick order (intentionally sequential, not parallel, so a later agent can
react to an earlier agent's move within the same tick):

  for each persona (in deterministic order):
      perception  = perceive(...)
      memories    = retrieve(..., query="what matters right now at <location>")
      decision    = decide_action(..., memories)
      event       = execute(decision)
      if decision was 'speak' and the target is still here:
          conversation = generate_conversation(...)
          append conversation turns to events
      if should_reflect(persona):
          reflect(persona)
          emit a 'reflect' event

  recorder.record_tick(...)
  time += seconds_per_tick
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..agent import Persona
from ..cognition import (
    decide_action,
    ensure_daily_plan,
    execute,
    generate_conversation,
    perceive,
    reflect,
    retrieve,
    should_reflect,
)
from ..llm import Embedder, GeminiClient
from ..world import World
from .recorder import Recorder

logger = logging.getLogger(__name__)


class Simulation:
    def __init__(
        self,
        *,
        world: World,
        personas: list[Persona],
        llm: GeminiClient,
        embedder: Embedder,
        recorder: Recorder,
        start_time: datetime,
        seconds_per_tick: int,
        retrieval_k: int,
        recency_decay: float,
        reflect_threshold: float,
    ):
        self.world = world
        self.personas = personas
        self.llm = llm
        self.embedder = embedder
        self.recorder = recorder
        self.current_time = start_time
        self.seconds_per_tick = seconds_per_tick
        self.retrieval_k = retrieval_k
        self.recency_decay = recency_decay
        self.reflect_threshold = reflect_threshold
        self.tick = 0

    def run(self, max_ticks: int) -> None:
        self.recorder.set_meta(
            start_time=self.current_time,
            seconds_per_tick=self.seconds_per_tick,
            personas=self.personas,
            world=self.world,
        )

        for tick in range(max_ticks):
            self.tick = tick
            logger.info("=== tick %d  %s ===", tick, self.current_time.isoformat())
            events = self._run_tick()
            self.recorder.record_tick(
                tick=tick,
                time=self.current_time,
                personas=self.personas,
                events=events,
            )
            self.current_time += timedelta(seconds=self.seconds_per_tick)

    def _run_tick(self) -> list[dict]:
        events: list[dict] = []

        for persona in self.personas:
            # make sure a daily plan exists before any decision
            ensure_daily_plan(persona, self.current_time, self.llm)

            perception = perceive(persona, self.world, self.personas)
            query = (
                f"What is salient for {persona.name} right now at "
                f"{perception.here.name}?"
            )
            memories = retrieve(
                persona,
                query,
                embedder=self.embedder,
                current_tick=self.tick,
                recency_decay=self.recency_decay,
                k=self.retrieval_k,
            )

            decision = decide_action(
                persona,
                perception,
                memories,
                self.world,
                self.current_time,
                self.llm,
                current_tick=self.tick,
            )
            event = execute(
                persona,
                decision,
                self.world,
                llm=self.llm,
                embedder=self.embedder,
                current_tick=self.tick,
            )
            events.append(event)

            # If this was a 'speak' decision, resolve the full conversation now.
            if decision.action == "speak" and decision.target_person:
                target = self._persona(decision.target_person)
                if target and target.scratch.current_location == persona.scratch.current_location:
                    convo_events = generate_conversation(
                        persona,
                        target,
                        location_name=perception.here.name,
                        opening_reason=decision.activity,
                        llm=self.llm,
                        embedder=self.embedder,
                        current_tick=self.tick,
                        recency_decay=self.recency_decay,
                        retrieval_k=self.retrieval_k,
                    )
                    events.extend(convo_events)

            # Reflection trigger — runs at most once per persona per tick
            if should_reflect(persona, self.reflect_threshold):
                insights = reflect(
                    persona,
                    llm=self.llm,
                    embedder=self.embedder,
                    current_tick=self.tick,
                    recency_decay=self.recency_decay,
                    retrieval_k=self.retrieval_k,
                )
                for ins in insights:
                    events.append(
                        {"type": "reflect", "actor": persona.id, "text": ins}
                    )

        return events

    def _persona(self, pid: str) -> Persona | None:
        for p in self.personas:
            if p.id == pid:
                return p
        return None
