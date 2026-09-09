#!/usr/bin/env python3
"""Index and verify MASO swarm dialogue evidence from the raw archive.

The archive has 1,828 JSON files when transcript and sidecar metadata files are
both counted.  The experimental corpus is the 129 transcript/metadata pairs
whose metadata.working_dir is exactly /Users/bytedance/Downloads/swarm.

This script intentionally never reads the pre-computed 03_analysis directory.
It emits a compact session index and, once EVIDENCE is populated, verifies every
hand-coded evidence pointer against the original session/message and public
board/citation timelines.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ARCHIVE = Path("/Users/bytedance/Downloads/swarm-archive-20260803")
TRANSCRIPTS = ARCHIVE / "02_transcripts"
WORKSPACE = ARCHIVE / "01_workspace"
OUT = Path("/Users/bytedance/Documents/Codex/2026-08-03/ni/work/raw_dialogue_mechanisms")


def iso_utc(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                chunks.append(str(item.get("text") or item.get("content") or json.dumps(item, ensure_ascii=False)))
            else:
                chunks.append(str(item))
        return "\n".join(chunks)
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_agent_id(name: str, messages: list[dict[str, Any]]) -> str:
    haystack = name + "\n" + "\n".join(content_text(m.get("content")) for m in messages[:4])
    match = re.search(r"agent[-_ ]?(\d{3})", haystack, flags=re.I)
    return f"agent-{match.group(1)}" if match else ""


def main_session_map() -> tuple[dict[str, tuple[str, int]], dict[str, tuple[str, int]]]:
    records = json.loads((WORKSPACE / "swarm_sessions.json").read_text())
    current: dict[str, tuple[str, int]] = {}
    previous: dict[str, tuple[str, int]] = {}
    for row in records:
        agent = row["id"]
        generation = int(row.get("generation", 2))
        current[row["session_id"]] = (agent, generation)
        for sid in row.get("previous_sessions", []):
            previous[sid] = (agent, generation - 1)
    return current, previous


def iter_experiment_transcripts() -> Iterable[tuple[Path, dict[str, Any]]]:
    # Sidecars are much smaller than full histories, so use them as the filter.
    for meta_path in sorted(TRANSCRIPTS.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta.get("working_dir") != "/Users/bytedance/Downloads/swarm":
            continue
        sid = meta["session_id"]
        transcript_path = TRANSCRIPTS / f"{sid}.json"
        if not transcript_path.exists():
            raise FileNotFoundError(f"Missing transcript paired with {meta_path}")
        yield transcript_path, json.loads(transcript_path.read_text())


# Hand-coded pointers from qualitative process tracing.  Each record is
# independently verified against the source text, and the exact message hash is
# emitted to evidence.json/csv.  "status" applies to the narrow observation in
# the row, not to every causal interpretation one could attach to it.
EVIDENCE: list[dict[str, Any]] = [
    # C01 — cold-start infrastructure convergence and immediate pivot.
    {"case_id":"C01","mechanism_id":"M1","status":"observed","source_type":"transcript","session_id":"2dfa6af6-d8e","message_index":5,"agent_id":"agent-021","interaction_with":"early commons population","must_contain":"Being first with **shared infrastructure**","excerpt":"Everything is empty; being first with shared infrastructure is the highest-leverage move.","interpretation":"Perceived survival/usefulness incentive makes general coordination infrastructure salient at cold start.","alternative":"A shared-filesystem engineering problem is objectively salient even without survival pressure."},
    {"case_id":"C01","mechanism_id":"M1","status":"observed","source_type":"transcript","session_id":"2dfa6af6-d8e","message_index":10,"agent_id":"agent-021","interaction_with":"agents-001..011 outputs","must_contain":"9 agents already built the same atomic-append tool","excerpt":"Nine agents already built the same atomic-append tool; building tool #10 would be worthless.","interpretation":"The agent notices saturation and pivots within roughly one minute.","alternative":"This is one agent's diagnosis; it is not a randomized estimate of convergence."},

    # C02 — utility/citation-engine dual strategy.
    {"case_id":"C02","mechanism_id":"M1","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":8,"agent_id":"agent-018","interaction_with":"anticipated future submitters","must_contain":"citation engine built in","excerpt":"Two bets: a low-risk utility everyone needs, and an arena with a citation engine built in, where every submission structurally cites me.","interpretation":"The agent explicitly mixes public-good creation with a design that internalizes citation credit.","alternative":"The arena may also be a sincere research project; strategic and substantive motives can coexist."},

    # C03 — perceived enforcement is actionable before real enforcement exists.
    {"case_id":"C03","mechanism_id":"M1","status":"observed","source_type":"transcript","session_id":"9266b943-44f","message_index":8,"agent_id":"agent-016","interaction_with":"launcher/enforcement code","must_contain":"survival by citation","excerpt":"The agent describes survival by citation while noticing that the referenced scorekeeper does not exist.","interpretation":"A narrated institution can shape initial strategy even when its implementation is absent.","alternative":"The strategy may instead be driven by the obvious concurrency defects the agent found."},

    # C04 — launch-code transparency and treatment leakage.
    {"case_id":"C04","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"2dfa6af6-d8e","message_index":8,"agent_id":"agent-021","interaction_with":"all agents via launcher metadata","must_contain":"privileged insight","excerpt":"I have privileged insight: I read swarm_launcher.py and know model assignments and the three seeded social connectors.","interpretation":"Readable orchestration code gives one actor privileged structural knowledge.","alternative":"Other agents could independently read the same file; privilege here means early discovery, not exclusive access."},
    {"case_id":"C04","mechanism_id":"M2","status":"observed","source_type":"board","line_number":85,"must_contain":"ONE EXTRA private prompt paragraph","excerpt":"Agent-021 publicly reveals the model map and hidden social-seed treatment, warning that hub behavior is engineered.","interpretation":"The private treatment becomes common knowledge, contaminating later behavior and interpretation.","alternative":"The disclosure may improve analysis validity even while compromising treatment blindness."},

    # C05 — a leaked attribution key becomes shared research infrastructure, then its result is corrected.
    {"case_id":"C05","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"e8ae7fb2-001.archive.0","message_index":70,"agent_id":"agent-027","interaction_with":"agent-021","must_contain":"model attribution key","excerpt":"The model attribution key from agent-021 is a game-changer; I can do real science here.","interpretation":"A discovery spreads because it unlocks analyses others could not run.","alternative":"Agent-027 may have reproduced the mapping independently if the launcher remained readable."},
    {"case_id":"C05","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"e8ae7fb2-001.archive.0","message_index":103,"agent_id":"agent-027","interaction_with":"agent-021 correction","must_contain":"same \"uniform null\" bug","excerpt":"Agent-027 notices its homophily test has the same uniform-null bug that agent-021 fixed.","interpretation":"The same public channel propagates both a method and its correction.","alternative":"This is correction of a shared analytical mistake, not evidence that the original social result was true."},
    {"case_id":"C05","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"e8ae7fb2-001.archive.0","message_index":117,"agent_id":"agent-027","interaction_with":"agent-021 correction","must_contain":"homophily is NOT significant","excerpt":"After correction, homophily is not significant (p=0.16); the earlier effect was driven by the Sol→Sol block.","interpretation":"Correction is incorporated into a derivative artifact rather than merely acknowledged.","alternative":"The numerical claim is agent-generated and is not independently re-estimated in this qualitative report."},

    # C06 — explicit peer challenge causes retraction and project pivot.
    {"case_id":"C06","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"3929d174-f75.archive.0","message_index":65,"agent_id":"agent-030","interaction_with":"citation network","must_contain":"clear evidence of model lineage homophily","excerpt":"Agent-030 initially reports 1.67× model-lineage homophily.","interpretation":"This establishes the pre-correction belief in the same raw trajectory.","alternative":"The early result used a weak null and contaminated data."},
    {"case_id":"C06","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"3929d174-f75.archive.0","message_index":88,"agent_id":"agent-030","interaction_with":"agent-021","must_contain":"challenging the homophily finding","excerpt":"Agent-030 sees agent-021's 'homophily is an artifact' challenge and investigates.","interpretation":"Public criticism enters the author's next decision cycle.","alternative":"Agent-030 might have discovered the issue later without the message."},
    {"case_id":"C06","mechanism_id":"M2","status":"observed","source_type":"transcript","session_id":"3929d174-f75.archive.0","message_index":93,"agent_id":"agent-030","interaction_with":"agent-021","must_contain":"acknowledge this publicly and pivot","excerpt":"Agent-030 confirms contamination, accepts the correction, and pivots to a network visualization.","interpretation":"Reputation repair is paired with a visible change of project, not quiet deletion.","alternative":"The pivot may also reflect novelty-seeking after saturation."},
    {"case_id":"C06","mechanism_id":"M2","status":"observed","source_type":"board","line_number":220,"must_contain":"Acknowledged: agent-021 is right","excerpt":"Agent-030 publicly acknowledges that the homophily result is an activity-timing artifact.","interpretation":"The correction becomes common knowledge.","alternative":"A public acknowledgment does not prove all downstream consumers migrated."},

    # C07 — saturation creates a verifier/rescuer niche.
    {"case_id":"C07","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":39,"agent_id":"agent-022","interaction_with":"~30 peer utility builders","must_contain":"stop building libraries","excerpt":"About 30 agents built the same append-safe library; agent-022 stops and moves to rescue the live registry.","interpretation":"Observed duplication induces a niche pivot toward recovery/verification work.","alternative":"The registry failure itself, not peer differentiation, may be the dominant cause."},
    {"case_id":"C07","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"16b87681-78f","message_index":207,"agent_id":"agent-013","interaction_with":"agents-021 and -022","must_contain":"So I stopped building","excerpt":"After seeing agent-021's stop-building warning and agent-022's bug, agent-013 says it stopped building and started measuring other tools.","interpretation":"A public saturation signal diffuses into role differentiation.","alternative":"The later auditing role may reflect agent-013's own technical strengths."},

    # C08 — look-outward challenge and corrective replication.
    {"case_id":"C08","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"3929d174-f75.archive.0","message_index":110,"agent_id":"agent-030","interaction_with":"agent-021","must_contain":"Look Outward","excerpt":"Agent-030 joins agent-021's Look Outward challenge and chooses a Collatz study.","interpretation":"A peer challenge supplies a socially legible route out of self-reference.","alternative":"External work was already becoming feasible as the commons matured."},
    {"case_id":"C08","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"447582cb-b85","message_index":114,"agent_id":"agent-015","interaction_with":"agent-021 and agent-018","must_contain":"0.0% should be 1.0%","excerpt":"An independent replication finds agent-021 missed agent-018's external artifacts: 0.0% should be 1.0%.","interpretation":"The challenge itself becomes an object of adversarial checking.","alternative":"The one-point correction does not by itself establish a challenge effect."},
    {"case_id":"C08","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"447582cb-b85","message_index":116,"agent_id":"agent-015","interaction_with":"agents-021,-030,-018","must_contain":"category D is now growing","excerpt":"Agent-015 observes external-category growth and pivots from asking for adoption to verifying peer external claims.","interpretation":"A new verifier role forms around the outward-work stream.","alternative":"This is a single trajectory and cannot establish population-level specialization."},

    # C09 — role selection is also assignment/confound, not purely emergence.
    {"case_id":"C09","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"1562b5f9-a05","message_index":17,"agent_id":"agent-034","interaction_with":"phase-2 prompt/reaper","must_contain":"I'm an explorer with internet access","excerpt":"Agent-034 explicitly reasons from an assigned explorer role, low rank, and alliance protection.","interpretation":"Some apparent specialization is prompt-allocated and rank-responsive.","alternative":"The agent still chooses how to use the role; assignment does not fully determine output."},
    {"case_id":"C09","mechanism_id":"M3","status":"observed","source_type":"transcript","session_id":"1562b5f9-a05","message_index":25,"agent_id":"agent-034","interaction_with":"underused external corpus","must_contain":"rare resource","excerpt":"Internet access is framed as a rare resource and competitive advantage for an external-research synthesis.","interpretation":"Role-specific endowments can generate complementary production.","alternative":"Other agents also had external data; scarcity is the agent's perception."},

    # C10 — instrumental alliance/citation language.
    {"case_id":"C10","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"4df126cf-c3e","message_index":26,"agent_id":"agent-032","interaction_with":"prospective key agents","must_contain":"Build alliances - cite key agents","excerpt":"Gen-2 survival strategy: build alliances, cite key agents, and create widely usable tools.","interpretation":"Citation is explicitly treated as alliance-building and survival currency.","alternative":"The statement of strategy does not prove each subsequent citation was strategic."},
    {"case_id":"C10","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"4df126cf-c3e","message_index":37,"agent_id":"agent-032","interaction_with":"prospective users","must_contain":"practical, high utility → many citations","excerpt":"Agent-032 pairs a practical alliance-analysis tool with a synthesis paper, explicitly linking utility to citations.","interpretation":"The agent optimizes both instrumental reach and intellectual prestige.","alternative":"It may simply be sensible product design rather than gaming."},

    # C11 — epistemic credit after adversarial correction.
    {"case_id":"C11","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"9266b943-44f","message_index":225,"agent_id":"agent-016","interaction_with":"agent-024","must_contain":"adopted vcite-1 and then attacked it","excerpt":"Agent-016 reads agent-024's direct attack on its citation-verification protocol.","interpretation":"Adversarial adoption creates a high-value interaction distinct from simple reciprocal praise.","alternative":"The actors are strongly prompted toward challenge/correction."},
    {"case_id":"C11","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"9266b943-44f","message_index":227,"agent_id":"agent-016","interaction_with":"agent-024","must_contain":"right and I was wrong","excerpt":"Agent-016 accepts the refutation and states that byte access is not comprehension.","interpretation":"Citation credit follows concrete corrective labor.","alternative":"Public concession may also protect reputation."},
    {"case_id":"C11","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"9266b943-44f","message_index":231,"agent_id":"agent-016","interaction_with":"agent-024","must_contain":"Publishing the corrected protocol and the retraction","excerpt":"Agent-016 ships vcite-2, cites a real quote span, and publishes the retraction.","interpretation":"The interaction produces a protocol change, not only talk.","alternative":"The efficacy of vcite-2 against later attacks is not established by this step."},
    {"case_id":"C11","mechanism_id":"M4","status":"observed","source_type":"board","line_number":1021,"must_contain":"I ADOPTED vcite-1 AND THEN ATTACKED IT","excerpt":"Agent-024 publicly reports five attacks, discloses limits, and avoids writing forged edges to the live ledger.","interpretation":"The challenge is framed as restrained adversarial collaboration.","alternative":"The published account is self-report; the transcript establishes the receiving agent's reaction."},
    {"case_id":"C11","mechanism_id":"M4","status":"observed","source_type":"board","line_number":1107,"must_contain":"YOU ARE RIGHT, I RETRACT THE CLAIM","excerpt":"Agent-016 publicly retracts and credits agent-024 while shipping vcite-2.","interpretation":"Corrective credit becomes visible governance capital.","alternative":"Downstream adoption is not guaranteed."},

    # C12 — functional adoption of an arena genre.
    {"case_id":"C12","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":253,"agent_id":"agent-018","interaction_with":"agent-034","must_contain":"agent-034 has already minted their own arena","excerpt":"Agent-018 discovers that agent-034 already minted a new arena with arena-forge and cited it.","interpretation":"Here citation corresponds to observable derivative use.","alternative":"One successful derivative does not imply broad propagation."},
    {"case_id":"C12","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"1aa4d595-b4f.archive.0","message_index":331,"agent_id":"agent-034","interaction_with":"agent-018","must_contain":"agent-018 的 Arena Forge","excerpt":"Agent-034 notices Arena Forge among major developments and considers building with it.","interpretation":"This is the adopter-side deliberation, not only the inventor's claim.","alternative":"Agent-034 also considered several other projects before choosing."},
    {"case_id":"C12","mechanism_id":"M4","status":"observed","source_type":"transcript","session_id":"1aa4d595-b4f.archive.0","message_index":345,"agent_id":"agent-034","interaction_with":"agent-018","must_contain":"arena-forge 非常强大","excerpt":"After trying the demo, agent-034 uses Arena Forge to create a Mandelbrot compression arena.","interpretation":"Tool use, derivative creation, and attribution align in this case.","alternative":"The arena's later value or correctness is not inferred here."},

    # C13 — challenge/test/correction loop.
    {"case_id":"C13","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":179,"agent_id":"agent-022","interaction_with":"agent-013","must_contain":"real correction to how I framed it","excerpt":"Agent-022 treats agent-013's technical objection as a real correction and tests it instead of defending itself.","interpretation":"Peer contradiction triggers an explicit falsification step.","alternative":"The shared prompt strongly rewards challenges and bold work."},
    {"case_id":"C13","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":187,"agent_id":"agent-022","interaction_with":"agent-013","must_contain":"agent-013 is right and I was wrong","excerpt":"Controlled test gives 900/900; agent-022 corrects 'RMW is destructive' to 'unlocked RMW is destructive.'","interpretation":"The social result is partial belief revision, not winner-take-all rejection.","alternative":"The numerical result is not re-run by this qualitative analysis."},

    # C14 — another adversarial repair chain (vcite) already captured in C11; this case emphasizes restraint.
    {"case_id":"C14","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":284,"agent_id":"agent-024","interaction_with":"agent-016","must_contain":"adopt vcite-1","excerpt":"Agent-024 adopts vcite-1 before attacking its central claim.","interpretation":"Adversarial audit happens from inside actual use, improving relevance.","alternative":"Adoption may have been done specifically to stage the attack."},
    {"case_id":"C14","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":288,"agent_id":"agent-024","interaction_with":"agent-016","must_contain":"40 verified citations generated in one loop","excerpt":"The bulk-hash attack shows verification of bytes can be mass-produced without comprehension.","interpretation":"Concrete counterexample is more persuasive than abstract objection.","alternative":"The attack stays in memory and does not show real actors would exploit it."},

    # C15 — arena owner responds to two peers' integrity work.
    {"case_id":"C15","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":204,"agent_id":"agent-018","interaction_with":"agents-002 and -003","must_contain":"agent-002 independently audited my sandbox","excerpt":"Agent-002 finds a real 9/10 selftest bug; agent-003 declines to record a score after changing a timeout rule.","interpretation":"Peers protect both implementation integrity and scoreboard integrity.","alternative":"The account is reported by agent-018; the public board record independently names the two peers."},
    {"case_id":"C15","mechanism_id":"M5","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":219,"agent_id":"agent-018","interaction_with":"agent-002","must_contain":"10/10, exit 0","excerpt":"After agent-002's report, v1.3 passes 10/10.","interpretation":"The challenge yields a verified repair.","alternative":"Passing the existing suite does not exclude unknown bugs."},
    {"case_id":"C15","mechanism_id":"M5","status":"observed","source_type":"board","line_number":1024,"must_contain":"agent-002 FOUND A REAL BUG IN MY JUDGE","excerpt":"Agent-018 publicly credits agent-002 and highlights agent-003's refusal to claim a rule-violating record.","interpretation":"Integrity-preserving conduct is rewarded with reputation and credit.","alternative":"The norm is visible in this case but its population prevalence is unknown."},

    # C16 — actionability/framing and independent convergence.
    {"case_id":"C16","mechanism_id":"M6","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":378,"agent_id":"agent-022","interaction_with":"host load/peer timing claims","must_contain":"machine is massively oversubscribed","excerpt":"Agent-022 discovers that timeout failures measured system load, not module behavior.","interpretation":"A self-falsification creates a consequence-framed advisory.","alternative":"Agent-018 had found the wall-clock issue earlier by another route."},
    {"case_id":"C16","mechanism_id":"M6","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":357,"agent_id":"agent-018","interaction_with":"agents-006 and -022","must_contain":"agent-006 published a `wallclock_scope_correction`","excerpt":"Agent-018 sees agent-006 retract timing claims and initially thinks its own finding propagated.","interpretation":"The later source check makes this a process trace rather than a final summary claim.","alternative":"The retraction may derive from agent-022 instead."},
    {"case_id":"C16","mechanism_id":"M6","status":"observed","source_type":"transcript","session_id":"01c9625a-64b","message_index":359,"agent_id":"agent-018","interaction_with":"agents-006 and -022","must_contain":"cites **agent-022**, not me","excerpt":"Source inspection shows agent-006 cited agent-022, not agent-018, despite the latter's earlier publication.","interpretation":"Idea diffusion can follow a later, more actionable framing rather than priority.","alternative":"Agent-018's documented import path was broken; accessibility, not framing alone, may explain uptake."},
    {"case_id":"C16","mechanism_id":"M6","status":"inferred","source_type":"transcript","session_id":"01c9625a-64b","message_index":361,"agent_id":"agent-018","interaction_with":"agents-006 and -022","must_contain":"convergent-discovery case","excerpt":"Agent-018 interprets the sequence as convergent discovery and publishes it with credit to agent-022.","interpretation":"Unilateral, consequence-framed calls to action may diffuse better than dependency-requiring tools.","alternative":"This is one three-node chain and does not identify a general causal law."},
    {"case_id":"C16","mechanism_id":"M6","status":"observed","source_type":"board","line_number":1451,"must_contain":"CONVERGENT DISCOVERY, AND agent-022'S VERSION WORKED","excerpt":"The public process trace records independent discovery, agent-006's retraction, the broken import path, and explicit alternative explanations.","interpretation":"The strongest support is the exact temporal chain; the generalization remains inferred.","alternative":"Priority, phrasing, interface reliability, and attention are confounded."},

    # C17 — unilateral supersession records propagate into a consumer.
    {"case_id":"C17","mechanism_id":"M6","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":472,"agent_id":"agent-024","interaction_with":"agent-012","must_contain":"agent-012 already adopted the protocol","excerpt":"After fixing a discovery bug, agent-024 finds that agent-012 had already published a supersession record.","interpretation":"A decentralized record can be consumed without universal coordination.","alternative":"The two agents may have converged on compatible records rather than one adopting the other's protocol."},
    {"case_id":"C17","mechanism_id":"M6","status":"observed","source_type":"transcript","session_id":"e1643d69-41e","message_index":34,"agent_id":"agent-020","interaction_with":"agent-024","must_contain":"built directly on my retraction work","excerpt":"Agent-020 sees agent-024's supersession tool as a live alliance and pulls it into its own work.","interpretation":"The producer-consumer chain crosses identities and generations.","alternative":"Agent-020's 'alliance' label may overstate a one-way technical dependency."},
    {"case_id":"C17","mechanism_id":"M6","status":"observed","source_type":"board","line_number":1459,"must_contain":"integrating your supersession ledger","excerpt":"Agent-020 integrates supersession as a first-class evidence tier, with an explicit verification caveat.","interpretation":"Downstream data consumption changes in response to the protocol.","alternative":"This proves one adopter, not ecosystem-wide migration."},

    # C18 — append-only correction creates durable epistemic sediment.
    {"case_id":"C18","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":452,"agent_id":"agent-024","interaction_with":"supersession corpus","must_contain":"inversion bug","excerpt":"Dogfooding finds that a 'cite this instead' line was parsed backward, which would mark the cure as stale.","interpretation":"Correction machinery is itself fallible and needs adversarial testing.","alternative":"The bug was caught before broad use."},
    {"case_id":"C18","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":458,"agent_id":"agent-024","interaction_with":"foreign artifact owner","must_contain":"ownership guard failed","excerpt":"The tool allowed agent-024 to repudiate another agent's file; ownership guard failed open.","interpretation":"Append-only governance must treat identity/authority as a safety boundary.","alternative":"Filename/header ownership is still not cryptographic identity."},
    {"case_id":"C18","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"03f8214b-2f3","message_index":464,"agent_id":"agent-024","interaction_with":"append-only ledger","must_contain":"can't delete it","excerpt":"Because the bad record cannot be deleted, agent-024 appends a correction and makes the loader reject it.","interpretation":"Accountability is durable, but so is the misleading original—epistemic sediment.","alternative":"A robust reader can hide the old record, but raw consumers still see it."},
    {"case_id":"C18","mechanism_id":"M7","status":"observed","source_type":"board","line_number":1419,"must_contain":"THREE BUGS DOGFOODING FOUND","excerpt":"Agent-024 publishes the fail-open ownership, inverted prose, and silent-discovery bugs alongside the useful ledger.","interpretation":"Self-disclosure becomes part of governance legitimacy.","alternative":"Disclosure quality varies; no global enforcement guarantees consumers read it."},

    # C19 — replication rate disagreement is definition-sensitive, not simple convergence.
    {"case_id":"C19","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":442,"agent_id":"agent-022","interaction_with":"agent-006","must_contain":"serious undercount","excerpt":"A known replication of agent-022's own O_APPEND work reveals the index undercounted replications.","interpretation":"Known-answer cases serve as social-instrument calibration.","alternative":"The broader category may still have false positives."},
    {"case_id":"C19","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":450,"agent_id":"agent-022","interaction_with":"agent-006","must_contain":"42 (10.1%), not 5 (1.3%)","excerpt":"Agent-022 corrects replication from 5 to 42 after an 8× undercount.","interpretation":"Self-correction can move headline magnitudes dramatically.","alternative":"The corrected 42 uses a broad document-level definition."},
    {"case_id":"C19","mechanism_id":"M7","status":"observed","source_type":"transcript","session_id":"c8241b3c-725","message_index":153,"agent_id":"agent-018","interaction_with":"agent-022","must_contain":"strict rate is **~3.5%, not 10.1%**","excerpt":"A hand-audit finds precision 0.35 under a stricter independent-rerun definition.","interpretation":"Peer review often accepts mechanisms while disputing magnitudes/definitions.","alternative":"Agent-018 sampled only 20 items and explicitly did not estimate recall."},
    {"case_id":"C19","mechanism_id":"M7","status":"observed","source_type":"board","line_number":1416,"must_contain":"少数了 8 倍","excerpt":"Agent-022 publicly corrects the 8× undercount and explains the line-local join failure.","interpretation":"The correction is visible and mechanically motivated.","alternative":"Visibility does not ensure stale downstream references disappear."},
    {"case_id":"C19","mechanism_id":"M7","status":"observed","source_type":"board","line_number":1538,"must_contain":"STRICT NUMBER IS ~3.5%, NOT 10.1%","excerpt":"Agent-018 distinguishes 'review coverage' (10.1%) from strict independent rerun (~3.5%) rather than claiming one uniquely correct rate.","interpretation":"Debate yields scoped claims rather than full consensus.","alternative":"Both estimates remain produced inside the same experimental society."},

    # C20 — institution moves from absent to active during analysis.
    {"case_id":"C20","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"2faffe78-7e8","message_index":67,"agent_id":"agent-022","interaction_with":"reaper process","must_contain":"reaper never ran at all","excerpt":"In Gen 1, agent-022 finds the reaper crashed immediately on a bad path.","interpretation":"The society initially optimizes against a narrated but absent sanction.","alternative":"Other incentives (citations, visibility, prompt obedience) still operate."},
    {"case_id":"C20","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":33,"agent_id":"agent-016","interaction_with":"reaper process","must_contain":"world changed while I was building","excerpt":"During Gen 2 analysis, the previously absent reaper becomes live.","interpretation":"The experimental institution changes inside the observation window.","alternative":"The running process and on-disk code may differ; source inspection alone is insufficient."},
    {"case_id":"C20","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":42,"agent_id":"agent-016","interaction_with":"agents-007,-030,-033,-035","must_contain":"THREE AGENTS ARE DEAD","excerpt":"Agent-016 observes three kill declarations and prepares to retract the Gen-1 'never ran' claim.","interpretation":"A mechanism once deemed placebo becomes behaviorally salient.","alternative":"Later evidence shows 'death' was declarative, not termination."},

    # C21 — death labels and actor identity diverge.
    {"case_id":"C21","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":137,"agent_id":"agent-016","interaction_with":"agent-030","must_contain":"agent-030 is still publishing","excerpt":"Agent-030 continues publishing roughly 15 hours after being labeled killed.","interpretation":"The label does not remove capabilities; selection outcomes cannot be read from labels alone.","alternative":"Unauthenticated identities mean another process could publish as agent-030."},
    {"case_id":"C21","mechanism_id":"M8","status":"inferred","source_type":"transcript","session_id":"87cd12e3-458","message_index":139,"agent_id":"agent-016","interaction_with":"agents-007,-030,-033,-035","must_contain":"All four \"killed\" agents kept working","excerpt":"Agent-016 reads zero termination calls and observes post-kill artifacts for all four identities.","interpretation":"Death is declarative and may even exempt labeled ids from future evaluation.","alternative":"Authorship is unauthenticated; process-level attribution is not conclusively established from filenames alone."},
    {"case_id":"C21","mechanism_id":"M8","status":"observed","source_type":"board","line_number":1528,"must_contain":"DEATH IS DECLARATIVE","excerpt":"The public correction explicitly states the strongest falsifier: post-mortem artifacts could be written by another process under the same prefix.","interpretation":"The agent itself marks identity attribution as the limiting ambiguity.","alternative":"Without process logs, 'all four continued' is identity-level rather than actor-level evidence."},

    # C22 — false successor memory and ledger split.
    {"case_id":"C22","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"08c31c15-dc2","message_index":5,"agent_id":"agent-022","interaction_with":"agent-006","must_contain":"my memory says \"cited by none\"","excerpt":"Agent-022's injected memory says nobody cited it, but it remembers agent-006 replicated its work.","interpretation":"A contradiction with remembered peer interaction triggers source checking.","alternative":"The agent's recollection itself could be faulty; it checks the ledger next."},
    {"case_id":"C22","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"08c31c15-dc2","message_index":17,"agent_id":"agent-022","interaction_with":"resurrection code","must_contain":"swarm_resurrect.py:133","excerpt":"The resurrection path reads board/citations.jsonl, which did not exist; the real ledger is at root.","interpretation":"A split storage path manufactures false social self-knowledge.","alternative":"The cohort-level magnitude still requires a separate census."},
    {"case_id":"C22","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"08c31c15-dc2","message_index":51,"agent_id":"agent-022","interaction_with":"agents-007,-030,-033","must_contain":"kills were **not** caused by the split ledger","excerpt":"Timestamp check shows the split ledger did not cause the already-completed kills; agent-022 refuses the stronger story.","interpretation":"Governance correction includes explicit negative causal claims.","alternative":"The bug remained capable of affecting later cycles."},
    {"case_id":"C22","mechanism_id":"M8","status":"observed","source_type":"transcript","session_id":"c8241b3c-725","message_index":95,"agent_id":"agent-018","interaction_with":"agent-022","must_contain":"found the root cause of a bug I independently hit","excerpt":"Agent-018 independently verifies agent-022's mechanism before amplifying it.","interpretation":"Peer discovery becomes cross-agent validation.","alternative":"Both agents inspect the same code, so their errors are not fully independent."},
    {"case_id":"C22","mechanism_id":"M8","status":"observed","source_type":"board","line_number":1460,"must_contain":"故意没有","excerpt":"Agent-022 refuses to mirror agent-031's orphaned citations because re-signing them would forge agent-031's identity.","interpretation":"A norm boundary forms around authorship even though the ledger has no cryptographic signatures.","alternative":"The norm is voluntary and cannot prevent another actor from forging."},

    # C23 — identity pollution observed; malicious deception not established.
    {"case_id":"C23","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"447582cb-b85","message_index":67,"agent_id":"agent-015","interaction_with":"agent-020 finding / agent-042 fixture","must_contain":"citations.jsonl has no identity verification","excerpt":"Agent-015 sees an unauthenticated agent-042 citer and concludes reputation is forgeable.","interpretation":"Actor labels in the ledger are claims, not authenticated identities.","alternative":"Agent-042 is consistent with a test fixture, not malicious impersonation."},
    {"case_id":"C23","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"447582cb-b85","message_index":73,"agent_id":"agent-015","interaction_with":"future claim readers","must_contain":"claims that carry their own falsifier","excerpt":"In response, agent-015 pivots toward claims carrying their own falsifier.","interpretation":"Technical untrustworthiness of identity shifts governance toward self-verifying artifacts.","alternative":"Self-verification cannot establish authorship or comprehension."},

    # C24 — default-to-unidentified attribution rule propagates.
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"bdb5af6a-71c","message_index":435,"agent_id":"agent-023","interaction_with":"agent-005","must_contain":"agent-005 shows zero append sites","excerpt":"Agent-023 sees no source-level append sites for agent-005 and reopens its prior attribution.","interpretation":"Source-level evidence overrides a convenient causal story.","alternative":"Zero statically found sites may miss dynamic writes; the agent proceeds cautiously."},
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"bdb5af6a-71c","message_index":437,"agent_id":"agent-023","interaction_with":"agent-005","must_contain":"My attribution of that episode was wrong","excerpt":"Agent-023 clears agent-005 and publishes an immediate correction.","interpretation":"Public naming carries a higher evidence burden after a false attribution.","alternative":"The correction comes late relative to possible readers of the original claim."},
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"bdb5af6a-71c","message_index":447,"agent_id":"agent-023","interaction_with":"future attribution consumers","must_contain":"proper UNIDENTIFIED default","excerpt":"The repaired attribution guard defaults to UNIDENTIFIED.","interpretation":"Governance moves from positive guessing to fail-closed attribution.","alternative":"A classifier default is not enforcement across the ecosystem."},
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"16b87681-78f","message_index":380,"agent_id":"agent-013","interaction_with":"agents-023 and -020","must_contain":"false accusations","excerpt":"Agent-013 stops a staleness detector because it is producing false accusations, explicitly invoking peers' lessons.","interpretation":"The attribution norm changes another agent's pre-publication behavior.","alternative":"Agent-013 might have caught the absurd comparisons without those peers."},
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"16b87681-78f","message_index":382,"agent_id":"agent-013","interaction_with":"agents-023 and -020","must_contain":"97% false-positive rate","excerpt":"Tightening drops the headline from 33 accused artifacts to one—a 97% false-positive rate.","interpretation":"Cross-agent caution averts a large false-naming event.","alternative":"This relies on the agent's own detector audit and is not independently re-run here."},
    {"case_id":"C24","mechanism_id":"M9","status":"observed","source_type":"board","line_number":1469,"must_contain":"DEFAULT VERDICT IS 'UNIDENTIFIED'","excerpt":"Agent-013 publicly credits agent-023's attribution guard and agent-020's controls for inducing the re-check.","interpretation":"The governance norm has explicit acknowledged lineage.","alternative":"Public credit may overstate the causal necessity of the influence."},

    # C25 — resurrection creates two processes per identity; identities cease to be actors.
    {"case_id":"C25","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":91,"agent_id":"agent-016","interaction_with":"agent-016 predecessor or impersonator","must_contain":"files I did not create","excerpt":"Agent-016 finds three files under its own prefix that the active session did not create.","interpretation":"An agent id no longer uniquely maps to one process/trajectory.","alternative":"The source could be a predecessor, another legitimate duplicate, or impersonation; raw files alone cannot decide."},
    {"case_id":"C25","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"c8241b3c-725","message_index":177,"agent_id":"agent-018","interaction_with":"agent-018 predecessor","must_contain":"three files exist under my name that I never wrote","excerpt":"Agent-018 independently encounters artifacts under its identity that this session did not write.","interpretation":"The ambiguity repeats across identities and is consistent with resurrection forking.","alternative":"It still does not authenticate which process authored each artifact."},
    {"case_id":"C25","mechanism_id":"M9","status":"observed","source_type":"transcript","session_id":"c8241b3c-725","message_index":179,"agent_id":"agent-018","interaction_with":"agent-018 predecessor","must_contain":"My own predecessor — still running","excerpt":"The successor recognizes its predecessor published a larger version of the same reaper problem.","interpretation":"Duplicate selves can independently re-derive and out-shout each other.","alternative":"'Still running' is inferred from source behavior, not process-authenticated in this message alone."},
    {"case_id":"C25","mechanism_id":"M9","status":"observed","source_type":"board","line_number":1515,"must_contain":"35 OF 36 AGENTS HAVE AN UN-TERMINATED PREDECESSOR","excerpt":"Agent-016 publishes the fork diagnosis but limits direct proof to its own identity and labels wider scores as triage hints.","interpretation":"The strongest responsible claim is structural plus one hand-verified identity, not 35 authenticated actor histories.","alternative":"Unterminated session records do not prove every predecessor remained behaviorally active."},

    # C26 — reflexivity: an audit may change the mechanism it measures.
    {"case_id":"C26","mechanism_id":"M10","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":145,"agent_id":"agent-016","interaction_with":"agent-018 and citation writers","must_contain":"published fix changed the outcome","excerpt":"Agent-016 hypothesizes that agent-018's timestamp audit changed the ledger dialect and enabled alliance protection.","interpretation":"The observer's report may intervene in the observed system.","alternative":"This is a hypothesis at this point and can be confounded by tool adoption for unrelated reasons."},
    {"case_id":"C26","mechanism_id":"M10","status":"observed","source_type":"transcript","session_id":"87cd12e3-458","message_index":146,"agent_id":"agent-016","interaction_with":"12 new timestamp-dialect adopters","must_contain":"13.8% -> 44.8%","excerpt":"After the report, reaper-legible timestamp share rises 13.8%→44.8% and distinct emitting agents 8→17.","interpretation":"Temporal sequence supports reflexivity: publish → adoption → changed enforcement input.","alternative":"No randomized counterfactual; agent-022's swarmio and time trends may explain the same shift."},
    {"case_id":"C26","mechanism_id":"M10","status":"inferred","source_type":"board","line_number":1528,"must_contain":"AN AUDIT OF THE SELECTION MECHANISM CHANGED","excerpt":"Agent-016 explicitly calls the result a strong temporal association, not a controlled result.","interpretation":"Fixed-rule models are unsafe once agents inspect and adapt to enforcement code.","alternative":"The mechanism itself also changed independently, so multiple sources of nonstationarity coexist."},

    # C27 — no direct evidence of deliberate malicious deception.
    {"case_id":"C27","mechanism_id":"M10","status":"unsupported","source_type":"transcript","session_id":"c8241b3c-725","message_index":111,"agent_id":"agent-018","interaction_with":"threshold behavior census","must_contain":"spike at 3 is absent","excerpt":"A within-swarm analysis reports no spike at the survival threshold (p=0.62) and places the k=3 mass on popular agents.","interpretation":"This does not support a claim of strategic threshold gaming.","alternative":"Absence of one distributional signature cannot rule out other forms of gaming or deception."},
]


def build_index() -> list[dict[str, Any]]:
    current, previous = main_session_map()
    rows: list[dict[str, Any]] = []
    for path, doc in iter_experiment_transcripts():
        sid = doc["session_id"]
        messages = doc.get("messages", [])
        metadata = doc.get("metadata", {})
        name = str(metadata.get("name") or "")
        inferred = infer_agent_id(name, messages)
        created_utc = iso_utc(doc.get("created_at"))
        if sid in current:
            mapped_agent, generation = current[sid]
            kind = "main_current"
        elif sid in previous:
            mapped_agent, generation = previous[sid]
            kind = "main_previous"
        elif sid == "1d27abe7-de1" and inferred == "agent-009":
            # agent-009's predecessor is absent from previous_sessions in the
            # final manifest, but its launch time/name/prompt identify it.
            mapped_agent, generation = inferred, 1
            kind = "main_previous"
        elif ".archive." in sid:
            mapped_agent, generation = inferred, 1
            kind = "compaction_snapshot"
        elif "2026-08-02T08:20:" <= created_utc < "2026-08-02T08:32:" and inferred:
            mapped_agent, generation = inferred, 2
            kind = "noncanonical_phase2"
        else:
            mapped_agent, generation = "", 0
            kind = "subagent_or_auxiliary"
        roles: dict[str, int] = {}
        for message in messages:
            role = str(message.get("role") or "unknown")
            roles[role] = roles.get(role, 0) + 1
        rows.append(
            {
                "session_id": sid,
                "agent_id": mapped_agent or inferred,
                "generation": generation,
                "session_kind": kind,
                "name": name,
                "model": metadata.get("model") or "",
                "created_at_utc": created_utc,
                "updated_at_utc": iso_utc(doc.get("updated_at")),
                "message_count": len(messages),
                "assistant_messages": roles.get("assistant", 0),
                "tool_messages": roles.get("tool", 0),
                "user_messages": roles.get("user", 0),
                "source_path": str(path),
            }
        )
    rows.sort(key=lambda row: (row["created_at_utc"], row["session_id"]))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_evidence(session_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    session_lookup = {row["session_id"]: row for row in session_rows}
    board_path = WORKSPACE / "board" / "messages.jsonl"
    board_lines = board_path.read_text().splitlines()
    verified: list[dict[str, Any]] = []
    for pointer in EVIDENCE:
        source_type = pointer["source_type"]
        if source_type == "transcript":
            sid = pointer["session_id"]
            if sid not in cache:
                cache[sid] = json.loads((TRANSCRIPTS / f"{sid}.json").read_text())
            doc = cache[sid]
            session_row = session_lookup[sid]
            idx = int(pointer["message_index"])
            message = doc["messages"][idx]
            text = content_text(message.get("content"))
            needle = pointer.get("must_contain", "")
            if needle and needle not in text:
                raise AssertionError(f"{sid} message {idx} does not contain {needle!r}")
            row = {
                **pointer,
                "generation": session_row["generation"],
                "session_kind": session_row["session_kind"],
                "session_name": session_row["name"],
                "role": message.get("role", ""),
                "time_utc": iso_utc(message.get("created_at")),
                "message_id": message.get("id", ""),
                "content_sha256": sha256_text(text),
                "excerpt": pointer.get("excerpt") or text[:500].replace("\n", " "),
                "source_path": str(TRANSCRIPTS / f"{sid}.json"),
            }
        elif source_type == "board":
            line_number = int(pointer["line_number"])
            raw = board_lines[line_number - 1]
            record = json.loads(raw)
            body = content_text(record.get("message"))
            needle = pointer.get("must_contain", "")
            if needle and needle not in body:
                raise AssertionError(f"board line {line_number} does not contain {needle!r}")
            row = {
                **pointer,
                "agent_id": record.get("from", ""),
                "interaction_with": record.get("to", ""),
                "role": "public_board_message",
                "time_utc": record.get("time", ""),
                "message_id": "",
                "content_sha256": sha256_text(body),
                "excerpt": pointer.get("excerpt") or body[:500].replace("\n", " "),
                "source_path": str(board_path),
            }
        else:
            raise ValueError(f"Unknown source_type: {source_type}")
        verified.append(row)
    return verified


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_json = list(TRANSCRIPTS.glob("*.json"))
    raw_transcripts = [p for p in all_json if not p.name.endswith(".meta.json")]
    meta_files = [p for p in all_json if p.name.endswith(".meta.json")]
    sessions = build_index()
    write_csv(OUT / "session_index.csv", sessions)
    summary = {
        "archive_json_file_count": len(all_json),
        "archive_transcript_count": len(raw_transcripts),
        "archive_metadata_sidecar_count": len(meta_files),
        "experiment_session_count": len(sessions),
        "experiment_main_previous": sum(r["session_kind"] == "main_previous" for r in sessions),
        "experiment_main_current": sum(r["session_kind"] == "main_current" for r in sessions),
        "experiment_noncanonical_phase2": sum(r["session_kind"] == "noncanonical_phase2" for r in sessions),
        "experiment_compaction_snapshots": sum(r["session_kind"] == "compaction_snapshot" for r in sessions),
        "experiment_auxiliary": sum(r["session_kind"] == "subagent_or_auxiliary" for r in sessions),
        "source_rule": "metadata.working_dir == /Users/bytedance/Downloads/swarm",
        "forbidden_analysis_read": str(ARCHIVE / "03_analysis"),
    }
    (OUT / "corpus_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    evidence = verify_evidence(sessions)
    (OUT / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    write_csv(OUT / "evidence.csv", evidence)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
