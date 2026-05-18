# Clouseau: Core Concepts & Architecture

This document summarizes the key architectural decisions and research concepts implemented in the Clouseau investigation system.

## 1. Point of Interest (POI)
### What it is:
A **POI** is the initial piece of evidence provided to the system to start an investigation. It can be a suspicious IP address, a domain name, or a filename.

### Why it is used:
*   **Real-world Simulation**: It mimics a Security Operations Center (SOC) where an investigation is always triggered by an alert (e.g., from an IDS or Firewall).
*   **Search Space Reduction**: Security databases contain millions of logs. Starting with a POI provides a "thread" for the AI to pull, preventing it from getting lost in irrelevant data.
*   **Testing Iteration**: The research goal is to see if an agent can reconstruct an *entire* attack narrative starting from only *one* small clue.

## 2. Nudging (The Thoroughness Check)
### Location: `chief_inspector.py` (lines 128-143)

### The Problem:
Early testing showed that Large Language Models (LLMs) tend to be "lazy"—they often try to conclude an investigation after just 1 or 2 queries, missing deeper attack stages like lateral movement or persistence.

### The Solution:
The **Chief Inspector** contains a hardcoded "nudge" mechanism:
*   **Minimum Iteration Check**: If the agent attempts to finish the investigation before a minimum number of steps (defined in `constants.py`), the system intercepts the response.
*   **Automated Warning**: The system injects a message: *"I have not received a tool call from you... Take a moment to think before continuing."*
*   **Impact**: This simple rule-based intervention significantly increases the Recall and F1 scores by forcing the model to re-evaluate if it truly found everything.

## 3. Hierarchical Architecture
### Chief Inspector vs. Investigator:
Clouseau uses a multi-agent hierarchy rather than a single agent:
*   **Chief Inspector (`chief_inspector.py`)**: The "Brain." It manages the high-level strategy and planning. It **cannot** talk to the database.
*   **Investigator (`investigator.py`)**: The "Brawn." It is a specialist in Text-to-SQL. It takes a lead from the Chief and returns a factual summary of the logs.

## 4. Core System Logic
This section describes the specific technical logic that enables the system to function without saturating its memory or hallucinating SQL.

### A. Agents as Tools (Recursive Pattern)
The Chief Inspector does not "talk" to the Investigator like a human. Instead, it sees the Investigator as a **Tool** called `investigate_lead`. 
*   **Isolation**: Every time the tool is called, a new, ephemeral Investigator agent is spawned, performs its task, and is then destroyed. 
*   **Impact**: This prevents the "messy" details of database searching (SQL errors, retries, raw data) from ever entering the Chief's long-term memory.

### B. The Information Funnel (Context Compression)
To prevent **Context Rot**, the Investigator acts as a data filter. 
*   **The Process**: Investigator (queries 1000 lines of logs) -> Summarizes into 1 paragraph -> Returns only the summary to the Chief.
*   **Impact**: The Chief maintains a high-level "Strategic Context" while the Investigator handles the "Low-level Data."

### C. Few-Shot SQL Generation
The system does not rely on the LLM's base knowledge of SQL. Instead, it uses **Hardcoded Few-Shot Examples** (found in `prompts.py`).
*   **The Cheat Sheet**: For every database table (DNS, Audit, HTTP), the AI is provided with 3-5 examples of "Perfect SQL" for that specific table.
*   **Impact**: This forces the model to use correct column names and SQLite-specific syntax without needing fine-tuning.

---

## 5. Ablation Agent
### What it is:
A "stripped-down" version of the system that uses only a single agent with direct database access, removing the Chief/Investigator hierarchy.

### Why it exists:
In research, this is used as a **Baseline**. By comparing Clouseau against the Ablation Agent, the authors proved that the **Hierarchical** approach is superior for complex investigations.

---

## 6. Identified Research Gaps & Future Work
The following gaps have been identified for future research and extension of the Clouseau framework:

### A. IT/OT Telemetry Convergence
*   **Gap**: The current system is "IT-centric" and designed for structured logs (SQL). It does not address **Heterogeneous Telemetry** (e.g., binary OT protocols like Modbus/S7comm, or time-series sensor data).
*   **Challenge**: In converged environments, an attack may cross the boundary between IT (digital) and OT (physical). Starting from an IT-only POI is insufficient for detecting the physical consequences of an attack.

### B. Context Rot in Advanced Persistent Threats (APTs)
*   **Gap**: While the hierarchical structure "compresses" information, long-term **APT investigations** (spanning months/years) will eventually saturate the Chief Inspector's context window.
*   **Future Direction**: Implement **Long-term Memory** (e.g., Vector DB or Knowledge Graphs) to replace the linear chat history for multi-month attack reconstructions.

### C. Heuristic Nudging vs. RL Alignment (GRPO)
*   **Gap**: The current "Nudging" mechanism is a **rule-based heuristic hack** not mentioned in the original paper. It forces thoroughness but is not "intelligent."
*   **Future Direction**: Replace hardcoded nudges with **Autonomous Alignment** using RL algorithms like **GRPO (Group Relative Policy Optimization)**. This would reward the model for intrinsic thoroughness, parsimony, and reasoning quality.

### D. Reconstruction vs. Recreation
*   **Gap**: Clouseau is a **Post-Incident Reconstruction** tool (looking backward at logs). It does not **Recreate** (simulate) the attack.
*   **Future Direction**: Integrate a **Digital Twin or Sandbox** to allow the agent to "verify" its hypothesis by simulating the identified attack packets to see if they produce the same physical symptoms.

