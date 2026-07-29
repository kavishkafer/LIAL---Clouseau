from investigator import investigate_attack
from prompts_manager import get_prompt_chief_inspector, get_prompt_evaluation
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import InjectedToolArg, tool
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langgraph.graph import StateGraph, MessagesState
from datetime import datetime
from typing import Annotated
import constants
import prompts
import os
import json
import re
from handoff_logger import log_run_start, log_tool_event, log_run_end
import observability
import graph_assembly

# Matches the "- [SrcHost] -> [DstHost]: IP=.., Port=.., Timestamp=.., Process=..
# PID=.." line format the chief prompt asks for (prompts.py's "PIVOTS FOUND:"
# block). Only src/dst are required to match; every other field is extracted
# independently below so a partially-malformed LLM line (never guaranteed
# exact) still yields whatever it can, rather than an all-or-nothing regex
# silently dropping the whole pivot.
_PIVOT_LINE_RE = re.compile(r'^(?P<src>[^-].*?)\s*->\s*(?P<rest>.+)$')


def _parse_pivot_line(line: str) -> dict:
    detail = {'raw': line}
    m = _PIVOT_LINE_RE.match(line)
    if not m:
        return detail
    detail['src_host'] = m.group('src').strip()
    dst_part = m.group('rest').split(':', 1)
    detail['dst_host'] = dst_part[0].strip()
    kv_text = dst_part[1] if len(dst_part) > 1 else ''
    ip_m = re.search(r'IP=([\d.]+)', kv_text)
    if ip_m:
        detail['ip'] = ip_m.group(1)
    port_m = re.search(r'Port=(\d+)', kv_text)
    if port_m:
        detail['port'] = int(port_m.group(1))
    ts_m = re.search(r'Timestamp=([^,]+)', kv_text)
    if ts_m:
        detail['ts'] = ts_m.group(1).strip()
    proc_m = re.search(r'Process=(\S+)', kv_text)
    if proc_m:
        detail['process'] = proc_m.group(1)
    pid_m = re.search(r'PID=(\d+)', kv_text)
    if pid_m:
        detail['pid'] = int(pid_m.group(1))
    return detail

class investigate_ctx(dict):
    def __init__(self, llm: BaseChatModel, configs: dict):
        self.llm = llm
        self.configs = configs
        dict.__init__(self, self.configs)

@tool(parse_docstring=True)
def investigate_lead(ctx: Annotated[investigate_ctx, InjectedToolArg], lead: str) -> str:
    """Initiates an investigation based on the given lead, returns a summary of the investigation. Lead message should be consice and to the point and does not exceed 3 sentences.
    
    Examples: 
        lead="We found a suspicious connections to 138.98.11.83, identify any processes that communicated with this IP and inspect their execution tree and spawned processes. Identify any domain associated with this address. Report any unusual behavior or processes that may be related to this IP address."
        lead="Investigate the domain name malicious.xyz, find any processes who connected to this address, construct execution tree, and investigate these processes. Find any executables or script that may have been downdloaded around that time, inspect any frequent or unordinary connections around the time."
        lead="Investigate a process 'malicious.exe' running on the system. Construct execution tree and find all network connections or files associated with it. Look for any abnormal behavior around the time of execution of this process."
        lead="document.doc was downloaded from malicious sources around 1 PM. Check the logs for any abnormal behavior related to this file. Identify any processes that may have been exploited in the process of interacting with the file. Check for any abnormal network connections, process execution or file modifications around the time."
        lead="firefox.exe visited malicious site evil.com at 1 PM, investigate the browser activity afterward to determine the effect of this visit. Check for any malicious downloads, file modifications or executions around the visit time, check firefox.exe process tree to find any abnormal processes. Investigate any frequent connections made around the time of this malicious behavior."
        lead="Investigate malicious process 'malware.exe' with PID of 1234. It is clear this process has made contact with a C2 server at 138.98.11.83. We need to identify its subsequent actions after this, that is related to this attack. Check for any network connections, file modifications, or process creations made by this process or its associated processes, or around their time of execution."
        lead="Find all execution instances of malware.exe, then check their execution tree for any parent processes that may have spawned it. Check the process tree for any other processes that may have been spawned by malware.exe. inspect network connections made, find any frequent or abnormal network connections."
    
    Args:
        lead: investigation lead.

    Returns:
        str: a summary of the investigation.
    """
    return investigate_attack(ctx.llm, ctx.configs, lead)

class Clouseau:
    def __init__(self, model: BaseChatModel, configs: dict):
        # define tools
        tools = [investigate_lead]

        # define the workflow
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.call_tool)
        workflow.add_node("eval", self.call_eval)
        workflow.add_node("error", self.call_error)
        workflow.set_entry_point("agent")
        workflow.set_finish_point("eval")
        workflow.add_conditional_edges("agent", self.agent_router, ["tools", "error", "eval"])
        workflow.add_edge("error", "agent")
        workflow.add_edge("tools", "agent")

        # set agent properties
        self.ctx = investigate_ctx(llm=model, configs=configs)
        self.current_iteration = 0
        self.max_iterations = configs['max_investigations']
        self.max_tokens = configs['max_tokens']
        self.error_count = 0                                            # counts malformed <tool_call> XML responses
        self.max_errors = configs.get('chief_max_errors', constants.DEFAULT_CHIEF_MAX_ERRORS)
        self.graph = workflow.compile()
        self.tools = {t.name: t for t in tools}
        self.model_no_tools = model
        self.configs = configs.copy()
        self.model = model.bind_tools(tools)

    def call_error(self, state: MessagesState):
        return {"messages": [HumanMessage(content="Error: Invalid tool call format.")]}
    
    def agent_router(self, state: MessagesState):
        """Decides whether to call the model or the tools based on the last message."""
        messages = state["messages"]
        last_message = messages[-1]
        if type(last_message) == AIMessage:
            if last_message.tool_calls:
                if self.current_iteration > self.max_iterations:
                    print(f"{__name__}: Reached max iterations, model is not adhering to the workflow")
                    return "eval"
                return "tools"
            elif '<tool_call>' in last_message.content or '</tool_call>' in last_message.content:
                # Gemma 4 sometimes emits raw XML instead of structured tool calls.
                # Increment error_count (NOT current_iteration) so this always converges.
                self.error_count += 1
                if self.error_count > self.max_errors or self.current_iteration > self.max_iterations:
                    print(f"{__name__}: Exiting after {self.error_count} malformed tool calls (max={self.max_errors})")
                    return "eval"
                return "error"
        return "eval"

    def call_tool(self, state: MessagesState):
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            if t['name'] not in self.tools:      # check for bad tool name from LLM
                print(f"{__name__}: Received bad tool name from model {t['name']}")
                result = "bad tool name, retry"  # instruct LLM to retry if bad
            else:
                args = t['args'].copy()
                args['ctx'] = self.ctx
                host_label = self.configs.get('host_label') or self.configs.get('test_name')
                observability.emit(
                    self.configs.get('run_id'), 'lead_dispatched', role='chief', agent_id='chief-1',
                    host=host_label,
                    narration=f"Chief Inspector dispatches an Investigator: “{args.get('lead', '')}”",
                    detail={'lead': args.get('lead')},
                )
                result = self.tools[t['name']].invoke(args)
                self.current_iteration += 1
                log_tool_event(
                    configs=self.configs,
                    tool_name=t['name'],
                    iteration=self.current_iteration,
                    result=str(result),
                )
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
        return {'messages': results}
    
    def is_tool_call(self, message: AIMessage) -> bool:
        if type(message) != AIMessage:
            return False
        
        if message.tool_calls:
            return True
        return False

    def _emit_pivots(self, text: str) -> None:
        """Parse the "PIVOTS FOUND:" block the chief prompt asks for (prompts.py)
        and emit a pivot_found event per line — the signal that drives the
        multi-host lateral-movement view in the demo UI."""
        run_id = self.configs.get('run_id')
        if not run_id or not text or 'PIVOTS FOUND' not in text:
            return
        host_label = self.configs.get('host_label') or self.configs.get('test_name')
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('-') and '->' in line:
                detail = _parse_pivot_line(line.lstrip('- ').strip())
                if 'src_host' in detail and 'dst_host' in detail:
                    narration = f"Pivot identified: {detail['src_host']} → {detail['dst_host']}"
                    if 'process' in detail:
                        narration += f" (via {detail['process']}" + (f" PID={detail['pid']})" if 'pid' in detail else ')')
                else:
                    narration = f"Pivot identified: {detail['raw']}"
                observability.emit(
                    run_id, 'pivot_found', role='chief', agent_id='chief-1', host=host_label,
                    stage='Lateral Movement', narration=narration, detail=detail,
                )

    def call_model(self, state: MessagesState):

        messages = state['messages']
        if self.current_iteration > self.max_iterations:
            messages += [HumanMessage(content="Summarize your findings, compile the final report, and ensure that all attack artifacts are clearly identified by their PIDs.")]
            response = self.model_no_tools.invoke(messages, max_tokens=self.max_tokens)
            return {"messages": [response]}
        else:
            observability.emit(
                self.configs.get('run_id'), 'chief_thinking', role='chief', agent_id='chief-1',
                host=self.configs.get('host_label') or self.configs.get('test_name'),
                narration="The Chief Inspector is reviewing findings and planning the next step.",
            )
            response = self.model.invoke(messages, max_tokens=self.max_tokens)
            if isinstance(response.content, str):
                self._emit_pivots(response.content)
            if self.current_iteration < constants.DEFAULT_INVESTIGATION_MIN:
                #make sure the investigation is thorough, if the agent quits early we need to push it do more
                if not self.is_tool_call(response):
                    # not a tool call, the agent is quitting, push them a bit farther
                    warning = HumanMessage(content="This is an automated message, I have not received a tool call from you, meaning you believe you have exhausted all of your options. Take a moment to think before continuing. Reply with a tool call if you want to continue the investigation. otherwise we will proceed to the evaluation phase.")
                    tmp = messages.copy()
                    tmp.append(response)
                    tmp.append(warning)
                    f_response = self.model.invoke(tmp, max_tokens=self.max_tokens)
                    if not self.is_tool_call(f_response):
                        # not a tool call, the agent is quitting, return the initial f_response and print a warning
                        print(f"{__name__}: Agent is quitting without a tool call, returning initial response.")
                        #response.pretty_print()
                        #f_response.pretty_print()
                        
                        return {"messages": [response]}
                    messages += [response, warning]
                    return {"messages": [f_response]}
            return {"messages": [response]}
    
    def call_eval(self, state: MessagesState):
        observability.emit(
            self.configs.get('run_id'), 'eval_started', role='system', agent_id='system',
            narration="Evaluating the reconstructed report against ground truth.",
        )
        eval_prompt = get_prompt_evaluation()
        messages = state["messages"] + [HumanMessage(content=eval_prompt)]
        try:
            # Bind JSON response format for OpenAI-compatible endpoints
            json_model = self.model_no_tools.bind(response_format={"type": "json_object"})
            response = json_model.invoke(messages, max_tokens=self.max_tokens)
        except Exception:
            response = self.model_no_tools.invoke(messages, max_tokens=self.max_tokens)
        return {"messages": [response]}


def _emit_artifacts_from_eval(run_id: str, host_label, eval_json_text) -> None:
    """Emit artifact_found events from the final structured eval report (the
    same addresses/domains/files/malicious_processes/tainted_processes JSON
    evaluation.py scores against — see prompts.eval_agent). This is the
    grounded, deterministic signal for "what was found": mid-run SQL results
    don't reliably say which row is an attack artifact, that judgment only
    exists once the chief has produced its structured findings."""
    if not observability.is_enabled() or not isinstance(eval_json_text, str):
        return
    text = eval_json_text.strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return
    items = data[0] if isinstance(data, list) and data else data
    if not isinstance(items, dict):
        return

    def emit_artifact(artifact_type, value, **extra):
        if not value:
            return
        detail = {'artifact_type': artifact_type, 'value': value, **extra}
        stage = observability.infer_stage('artifact_found', detail)
        observability.emit(
            run_id, 'artifact_found', role='qa', agent_id='system', host=host_label, stage=stage,
            narration=f"Artifact recorded: {artifact_type} {value}.", detail=detail,
        )

    for addr in items.get('addresses') or []:
        emit_artifact('address', addr)
    for dom in items.get('domains') or []:
        emit_artifact('domain', dom)
    for f in items.get('files') or []:
        emit_artifact('file', f)
    for proc in items.get('malicious_processes') or []:
        emit_artifact('process', proc.get('name', 'unknown'), pid=proc.get('pid'), malicious=True)
    for proc in items.get('tainted_processes') or []:
        emit_artifact('process', proc.get('name', 'unknown'), pid=proc.get('pid'), hijack_time=proc.get('hijack_time'))


def ClouseauRun(llm: BaseChatModel, configs: dict) -> str:

    # run_id ties this run's events together for the demo UI (see observability.py).
    # Set on `configs` (not just a local var) so it also reaches evaluate_report()
    # in app.py, which emits the final 'metrics' event onto the same stream.
    configs['run_id'] = configs.get('run_id') or observability.new_run_id()
    host_label = configs.get('host_label') or configs.get('test_name')
    observability.start_run(configs['run_id'], poi=configs.get('clue', ''), hosts=[host_label] if host_label else None)

    graph_cfg = {'recursion_limit': 125}
    chief_prompt = HumanMessage(content=get_prompt_chief_inspector(
        configs['environment'],
        configs['max_investigations'],
        configs['clue']
        )
    )

    agent = Clouseau(llm, configs)
    log_run_start(configs)
    response = agent.graph.invoke({"messages": chief_prompt}, config=graph_cfg)
    messages = response["messages"]
    final_summary = messages[-1].content
    # messages[-2] is the chief's narrative report, before call_eval appended its
    # own JSON-only response as the new last message (see call_eval above).
    narrative = messages[-2].content if len(messages) >= 2 else final_summary
    if isinstance(narrative, str):
        observability.emit(
            configs['run_id'], 'final_report', role='chief', agent_id='chief-1', host=host_label,
            narration="Chief Inspector compiles the final report.", detail={'report': narrative},
        )
    _emit_artifacts_from_eval(configs['run_id'], host_label, final_summary)
    # Runs before end_run() queues its run_complete + sentinel, so the
    # assembled graph reaches the delivery queue (and any consumer) in order,
    # ahead of the connection closing — no backend changes needed.
    graph_assembly.assemble_and_emit(
        configs['run_id'], host_labels=[host_label] if host_label else [],
        eval_json_by_host={host_label: final_summary},
    )
    # Optional Phase 2 enrichment (CLOUSEAU_GRAPH_LLM=1) — may only add edges
    # between nodes assemble_and_emit already committed above; a no-op unless
    # explicitly enabled, and any failure leaves the deterministic graph above
    # completely unaffected. See graph_assembly.py's module docstring.
    graph_assembly.enrich_and_emit(
        configs['run_id'], host_labels=[host_label] if host_label else [],
        eval_json_by_host={host_label: final_summary}, llm=llm,
    )
    log_run_end(configs, final_summary)
    observability.end_run(configs['run_id'])
    return final_summary
    

def investigate_optc(llm: BaseChatModel, configs: dict = {}):
    """Investigate a clue using the OPTC database."""
    
    configs['environment'] = prompts.opt_env_context
    configs['is_darpa'] = True
    return ClouseauRun(llm=llm, configs=configs)
    

def investigate_atlas(llm: BaseChatModel, configs: dict = {}):
    """Investigate a clue using the ATLAS database."""
    
    configs['environment'] = prompts.atlas_env_context
    configs['is_darpa'] = False
    return ClouseauRun(llm=llm, configs=configs)