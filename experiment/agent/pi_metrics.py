"""Metrics for one Pi 1.6.0 JSON-mode invocation."""

from collections import Counter
import json
import math
import re


TOKEN_FIELDS = {
    "input": "input",
    "output": "output",
    "cache_read": "cacheRead",
    "cache_write": "cacheWrite",
    "total": "totalTokens",
}
LIMIT_ERROR = re.compile(
    r"(?i)\b(?:429\b|rate[ _-]*limit|usage[ _-]*limit|too many requests|"
    r"insufficient[ _-]*quota|quota[ _-]*exceeded|resource[ _-]*exhausted)"
)


def bash_command(event):
    """Get the command only from a bash execution start."""
    if event.get("type") == "tool_execution_start" and event.get("toolName") == "bash":
        args = event.get("args")
        if isinstance(args, dict):
            command = args.get("command")
            if isinstance(command, str):
                return command
    return None


class PiMetrics:
    def __init__(self):
        self.records = 0
        self.has_header = False
        self.settled = False
        self.aborted = False
        self.stream_error = None
        self.assistant_turns = 0
        self.final_assistant_seconds = None
        self.final_assistant_error = None
        self.tools = {}
        self.tokens = {name: None for name in TOKEN_FIELDS}
        self.costs = []
        self.limit_messages = []

    def read_record(self, raw, elapsed):
        """Consume one LF-framed stdout record and return the decoded event."""
        self.records += 1
        try:
            if not raw.endswith(b"\n"):
                raise ValueError("missing final LF")
            event = json.loads(raw.decode("utf-8"))
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("expected a typed JSON object")
        except ValueError as exc:
            self.stream_error = self.stream_error or f"Invalid Pi JSONL record {self.records} ({exc})"
            return None

        kind = event["type"]
        if self.records == 1:
            self.has_header = kind == "session"
        if kind == "agent_start":
            self.settled = False
        elif kind == "agent_settled":
            self.settled = True
            self.aborted = event.get("aborted") is True
        elif kind == "message_end":
            message = event.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                self._read_assistant(message, elapsed)
        elif kind == "message_update":
            update = event.get("assistantMessageEvent")
            if isinstance(update, dict) and update.get("type") == "error":
                error = update.get("error")
                if isinstance(error, dict):
                    self.record_diagnostic(error.get("errorMessage"))
        elif kind in {"tool_execution_start", "tool_execution_end"}:
            self._record_tool(event.get("toolCallId"), event.get("toolName"))
        elif kind in {"auto_retry_start", "compaction_end", "summarization_retry_scheduled"}:
            self.record_diagnostic(event.get("errorMessage"))
        elif kind == "auto_retry_end":
            self.record_diagnostic(event.get("finalError"))
        return event

    def _read_assistant(self, message, elapsed):
        self.assistant_turns += 1
        self.final_assistant_seconds = elapsed
        reason = message.get("stopReason")
        error = message.get("errorMessage")
        self.record_diagnostic(error)
        self.final_assistant_error = None
        if reason in ("error", "aborted", "length", "deferred", "pending"):
            self.final_assistant_error = (error if isinstance(error, str) and error
                                          else f"Final Pi assistant stop reason was {reason}")

        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "toolCall":
                    self._record_tool(block.get("id"), block.get("name"))

        usage = message.get("usage")
        if not isinstance(usage, dict):
            return
        for name, field in TOKEN_FIELDS.items():
            value = usage.get(field)
            if type(value) is int:
                self.tokens[name] = (self.tokens[name] or 0) + value
        cost = usage.get("cost")
        if isinstance(cost, dict):
            total = cost.get("total")
            if type(total) in {int, float} and math.isfinite(total):
                self.costs.append(total)

    def _record_tool(self, call_id, name):
        if isinstance(call_id, str) and isinstance(name, str):
            self.tools.setdefault(call_id, name)

    def record_diagnostic(self, message):
        if isinstance(message, str) and LIMIT_ERROR.search(message):
            if message not in self.limit_messages:
                self.limit_messages.append(message)

    def stream_errors(self):
        errors = []
        if self.stream_error:
            errors.append(self.stream_error)
        if not self.records:
            errors.append("Missing Pi JSONL stream")
        elif not self.has_header or not self.settled or not self.assistant_turns:
            errors.append("Incomplete Pi JSONL stream (expected session header, assistant message and agent_settled)")
        return errors

    def completion_errors(self):
        errors = []
        if self.aborted:
            errors.append("Pi reported an aborted run")
        if self.final_assistant_error:
            errors.append(self.final_assistant_error)
        return errors

    def result(self):
        by_tool = dict(sorted(Counter(self.tools.values()).items()))
        return {
            "final_assistant_seconds": self.final_assistant_seconds,
            "assistant_turns": self.assistant_turns,
            "tool_calls": sum(by_tool.values()),
            "tool_calls_by_name": by_tool,
            "bash_calls": by_tool.get("bash", 0),
            "tokens": self.tokens,
            "pi_reported_cost": math.fsum(self.costs) if self.costs else None,
            "rate_or_usage_limited": bool(self.limit_messages),
            "limit_error_messages": self.limit_messages,
        }
