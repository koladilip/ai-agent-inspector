"""
Multi-Agent System Example for Agent Inspector.

This example demonstrates how to use Agent Inspector to trace a multi-agent
system with agent spawning, communication, handoffs, and task assignments.

The example uses REAL LLM calls with OpenAI-compatible provider.

PER-AGENT MODEL CONFIGURATION:
    Each agent can use a different model by setting environment variables:
    - MODEL_TRIAGE: Model for triage agent (defaults to MODEL_NAME)
    - MODEL_BILLING: Model for billing agent (defaults to MODEL_NAME)
    - MODEL_TECHNICAL: Model for technical agent (defaults to MODEL_NAME)
    - MODEL_MANAGER: Model for manager agent (defaults to MODEL_NAME)

    Example examples/.env:
        MODEL_NAME=gpt-4o-mini          # Default model
        MODEL_BILLING=gpt-4o              # Use GPT-4o for billing
        MODEL_MANAGER=gpt-4o              # Use GPT-4o for manager

Setup:
    1. Copy .env.example to .env in examples directory:
       cp examples/.env.example examples/.env

    2. Edit examples/.env and add your API key:
        OPENAI_API_KEY=sk-...

    3. Install dependencies (REQUIRED for real LLM calls):
        uv add openai python-dotenv

    Usage:
    uv run python examples/multi_agent.py

Note: Without openai package and valid API key, this example will use
simulated responses. Install 'openai' and configure OPENAI_API_KEY in examples/.env
for real LLM calls.

Then view the traces with:
    agent-inspector server
"""

import os
import time
import uuid
from typing import Dict, List, Optional
from dotenv import load_dotenv

from agent_inspector import trace, TraceConfig, set_trace, Trace

# Load environment variables from .env file in examples directory
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

# Configuration
USE_REAL_LLM = False
client = None
model_name = "simulated"
base_url = None
api_key = None

print("=" * 70)
print("Multi-Agent Customer Support System")
print("=" * 70)

# Configure OpenAI
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
model_name = os.getenv("OPENAI_MODEL") or os.getenv("MODEL_NAME", "gpt-4o-mini")
temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))

# Initialize OpenAI client
if api_key:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        USE_REAL_LLM = True
        print(f"✅ Model: {model_name}")
        print(f"✅ API: {base_url}")
        print(f"✅ Temperature: {temperature}")
        print(f"✅ Timeout: {timeout}s\n")
    except ImportError:
        print("⚠️  ERROR: openai package not installed!")
        print("   Install with: uv add openai\n")
else:
    print("⚠️  ERROR: OPENAI_API_KEY not found in examples/.env!")
    print("   Copy examples/.env.example to examples/.env and add your API key\n")

if not USE_REAL_LLM:
    print("=" * 70)
    print("⚠️  FALLBACK: Using SIMULATED responses (no real LLM calls)")
    print("=" * 70)
    print("\nTo use real LLM calls:")
    print("  1. Install: uv add openai python-dotenv")
    print("  2. Copy: cp examples/.env.example examples/.env")
    print("  3. Edit examples/.env and set OPENAI_API_KEY")
    print("  4. Update OPENAI_BASE_URL and OPENAI_MODEL if needed\n")
    print()

# Configure tracing with 100% sampling
config = TraceConfig(sample_rate=1.0)
set_trace(Trace(config=config))


def get_agent_model(agent_type: str) -> str:
    """
    Get the model for a specific agent type from environment variables.

    Args:
        agent_type: The agent type (e.g., 'triage', 'billing', 'technical', 'manager')

    Returns:
        The model name from env var MODEL_<AGENT_TYPE> or default MODEL_NAME
    """
    env_var = f"MODEL_{agent_type.upper()}"
    return os.getenv(env_var, model_name)


class SupportAgent:
    """AI agent that uses LLM to process customer requests."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        capabilities: List[str],
        model: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.model = model or model_name
        self.system_prompt = f"""You are a {role} in a customer support team.
Capabilities: {", ".join(capabilities)}.
Provide helpful, concise responses (2-3 sentences).
Be professional and empathetic."""

    def process_request(self, request: str) -> str:
        """Process customer request using LLM."""
        if USE_REAL_LLM and client:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": request},
                    ],
                    max_tokens=150,
                    temperature=temperature,
                )

                # Safely extract response text
                if not response.choices or not response.choices[0]:
                    response_text = "I apologize, but I'm unable to generate a response at this time. Please try again or contact human support."
                else:
                    message = response.choices[0].message
                    response_text = (
                        message.content
                        if message and message.content
                        else "I apologize, but I received an empty response. Please try again."
                    )

                # Emit LLM trace event with real token usage
                trace.llm(
                    model=self.model,
                    prompt=f"System: {self.system_prompt}\n\nUser: {request}",
                    response=response_text,
                    prompt_tokens=getattr(
                        response.usage, "prompt_tokens", len(request.split())
                    ),
                    completion_tokens=getattr(
                        response.usage, "completion_tokens", len(response_text.split())
                    ),
                    total_tokens=getattr(
                        response.usage,
                        "total_tokens",
                        len((request + response_text).split()),
                    ),
                )

                return response_text

            except Exception as e:
                print(f"  ❌ Error: {str(e)[:50]}", flush=True)
                trace.error(error_type=type(e).__name__, error_message=str(e))
                return "I apologize, but I'm experiencing technical difficulties. Please try again later."
        else:
            # Simulated response
            time.sleep(0.5)
            response_text = self._simulated_response(request)

            # Ensure response is not empty
            if not response_text or not response_text.strip():
                response_text = (
                    "I apologize, but I'm unable to generate a response at this time."
                )

            trace.llm(
                model=f"{self.model} (simulated)",
                prompt=f"System: {self.system_prompt}\n\nUser: {request}",
                response=response_text,
                prompt_tokens=len(request.split()),
                completion_tokens=len(response_text.split()),
            )
            return f"[{self.name}] {response_text}"

    def _simulated_response(self, request: str) -> str:
        """Generate contextual simulated response."""
        req = request.lower()

        if "bill" in req or "payment" in req:
            return """I've reviewed your account and found the issue. There's a $2.99 processing fee that was incorrectly applied on your last billing cycle.

I've processed a refund for this fee which will appear on your statement within 3-5 business days. Is there anything else I can help you with regarding your billing?"""

        elif "technical" in req or "error" in req or "login" in req:
            return """I understand you're having trouble logging in. Based on our system logs, this appears to be related to session timeouts after inactivity.

Here's what I recommend:
1. Clear your browser cache and cookies
2. Try logging in with an incognito/private window
3. If that works, disable your browser extensions one by one

I'll also open a ticket (TKT-4821) so our technical team can monitor your account. Can you try these steps now and let me know the result?"""

        elif "complex" in req or "escalate" in req:
            return """I've reviewed this situation and you're absolutely right - this requires specialized attention.

I'm taking personal ownership of your case (CASE-7352) and will be coordinating with:
- Our billing team to resolve the disputed charges
- Our technical team to investigate the system error
- Our customer success team to ensure this doesn't happen again

I'll follow up with you directly within 4 hours with a complete update. You can reach me at extension 4827 if you have any questions in the meantime."""

        return f"""Thank you for contacting us! As your {self.role}, I'm here to help.

To assist you better, could you please provide:
1. Your account number or customer ID
2. More details about what you're experiencing
3. Any error messages you're seeing

Once I have this information, I'll be able to look into this right away."""


class MultiAgentSupportSystem:
    """Multi-agent customer support system."""

    def __init__(self):
        self.agents: Dict[str, SupportAgent] = {}
        self.active_tasks: Dict[str, Dict] = {}

    def spawn_agent(
        self, name: str, role: str, capabilities: List[str], model: Optional[str] = None
    ) -> SupportAgent:
        """Spawn a new agent.

        Args:
            name: Agent identifier (e.g., 'triage_agent')
            role: Agent's role description
            capabilities: List of agent capabilities
            model: Optional specific model for this agent (defaults to MODEL_NAME)

        Returns:
            The spawned SupportAgent instance
        """
        agent_id = f"{name}_{uuid.uuid4().hex[:8]}"
        agent = SupportAgent(agent_id, name, role, capabilities, model)
        # Store by name for easy routing access
        self.agents[name] = agent
        self.agents[agent_id] = agent

        trace.agent_spawn(
            agent_id=agent_id,
            agent_name=name,
            agent_role=role,
            agent_config={
                "capabilities": capabilities,
                "role": role,
                "model": agent.model,
            },
        )

        trace.agent_join(
            agent_id=agent_id,
            agent_name=name,
            group_id="support_system",
            group_name="Customer Support Team",
        )

        print(f"🤖 Spawned: {name} ({role})", flush=True)
        return agent

    def route_request(self, customer_request: str) -> Optional[SupportAgent]:
        """Route request to appropriate agent."""
        req = customer_request.lower()
        print(f"   🔍 Routing analysis: '{req}'\n", flush=True)

        if any(word in req for word in ["bill", "payment", "charge"]):
            print(f"   ✓ Matched: BILLING pattern\n", flush=True)
            return self.agents.get("billing_agent")
        elif any(word in req for word in ["technical", "error", "bug"]):
            print(f"   ✓ Matched: TECHNICAL pattern\n", flush=True)
            return self.agents.get("technical_agent")

        print(f"   ✓ Matched: TRIAGE (default)\n", flush=True)
        return self.agents.get("triage_agent")

    def handoff_task(
        self,
        from_agent: SupportAgent,
        to_agent: SupportAgent,
        task_id: str,
        description: str,
        reason: str,
    ) -> None:
        """Hand off task between agents."""
        trace.agent_handoff(
            from_agent_id=from_agent.agent_id,
            from_agent_name=from_agent.name,
            to_agent_id=to_agent.agent_id,
            to_agent_name=to_agent.name,
            handoff_reason=reason,
            context_summary=description[:100],
        )
        trace.agent_communication(
            from_agent_id=from_agent.agent_id,
            from_agent_name=from_agent.name,
            to_agent_id=to_agent.agent_id,
            to_agent_name=to_agent.name,
            message_type="handoff",
            message_content=f"Handing off {task_id}. Reason: {reason}",
        )
        print(f"🔀 Handoff: {from_agent.name} → {to_agent.name}")

    def assign_task(self, agent: SupportAgent, task_id: str, description: str) -> None:
        """Assign task to agent."""
        trace.task_assign(
            task_id=task_id,
            task_name=description[:50],
            assigned_to_agent_id=agent.agent_id,
            assigned_to_agent_name=agent.name,
            priority="high",
        )
        self.active_tasks[task_id] = {
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "description": description,
            "started_at": int(time.time() * 1000),
        }
        print(f"📝 Assigned: {task_id} → {agent.name}")

    def complete_task(self, task_id: str, result: str, success: bool = True) -> None:
        """Complete task."""
        task = self.active_tasks.get(task_id)
        if not task:
            return
        completion_time = int(time.time() * 1000) - task["started_at"]
        trace.task_complete(
            task_id=task_id,
            task_name=task["description"][:50],
            completed_by_agent_id=task["agent_id"],
            completed_by_agent_name=task["agent_name"],
            success=success,
            result=result[:200],
            completion_time_ms=completion_time,
        )
        del self.active_tasks[task_id]
        status = "✓" if success else "✗"
        print(f"{status} Completed: {task_id} ({completion_time}ms)")

    def handle_customer_request(self, customer_id: str, request: str) -> str:
        """Handle customer request with realistic agent workflow."""
        import sys

        print(f"\n{'=' * 70}", flush=True)
        print(f"📞 CUSTOMER: {customer_id}", flush=True)
        print(f"   REQUEST: {request}", flush=True)
        print(f"{'=' * 70}\n", flush=True)

        # Route to appropriate agent
        agent = self.route_request(request)
        if not agent:
            print("❌ No agents available for this request type\n", flush=True)
            return "No agents available"

        print(f"📋 Routing to: {agent.name}\n", flush=True)

        # Create task
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self.assign_task(agent, task_id, request)

        # Simulate tool usage to make it realistic
        self._simulate_tool_usage(customer_id, request, agent)

        # Agent processes request
        print(f"\n{'─' * 70}", flush=True)
        print(f"🤖 {agent.name} PROCESSING...", flush=True)
        print(f"{'─' * 70}\n", flush=True)
        response = agent.process_request(request)

        # Display full response
        print(f"\n{'─' * 70}", flush=True)
        print(f"💬 AGENT RESPONSE:", flush=True)
        print(f"{'─' * 70}", flush=True)
        print(response, flush=True)
        print(f"{'─' * 70}\n", flush=True)

        # Escalate complex issues
        if "complex" in request.lower() or "escalate" in request.lower():
            manager = self.agents.get("manager_agent")
            if manager:
                print(f"\n🔄 ESCALATION TRIGGERED", flush=True)
                self.handoff_task(agent, manager, task_id, request, "escalation")

                print(f"\n{'─' * 70}", flush=True)
                print(f"👔 MANAGER (Support Manager) TAKING OVER...", flush=True)
                print(f"{'─' * 70}\n", flush=True)

                self._simulate_tool_usage(
                    customer_id, "Escalated: " + request, manager, escalated=True
                )
                response = manager.process_request(request)

                print(f"\n{'─' * 70}", flush=True)
                print(f"💬 MANAGER RESPONSE:", flush=True)
                print(f"{'─' * 70}", flush=True)
                print(response, flush=True)
                print(f"{'─' * 70}\n", flush=True)

        self.complete_task(task_id, response)
        print(f"\n✅ Task {task_id} completed successfully\n", flush=True)
        return response

    def _simulate_tool_usage(
        self,
        customer_id: str,
        request: str,
        agent: SupportAgent,
        escalated: bool = False,
    ):
        """Simulate realistic tool usage by agent."""
        req_lower = request.lower()

        # Determine tools based on request type
        tools_to_call = []
        if "bill" in req_lower or "payment" in req_lower or "charge" in req_lower:
            tools_to_call = [
                ("get_customer_profile", f"customer_id={customer_id}"),
                ("check_billing_history", f"customer_id={customer_id}, months=3"),
                ("verify_transaction", f"transaction_id=TXN-{uuid.uuid4().hex[:8]}"),
            ]
        elif "technical" in req_lower or "error" in req_lower or "login" in req_lower:
            tools_to_call = [
                ("get_customer_profile", f"customer_id={customer_id}"),
                ("check_system_logs", f"customer_id={customer_id}, hours=24"),
                ("get_device_info", f"customer_id={customer_id}"),
            ]
        elif "complex" in req_lower or "escalate" in req_lower:
            tools_to_call = [
                ("get_full_case_history", f"customer_id={customer_id}"),
                ("check_all_integrations", f"customer_id={customer_id}"),
                (
                    "create_escalation_ticket",
                    f"customer_id={customer_id}, priority=critical",
                ),
            ]
        else:
            tools_to_call = [
                ("get_customer_profile", f"customer_id={customer_id}"),
            ]

        # Execute tool calls with traces
        for tool_name, tool_args in tools_to_call:
            print(f"  🔧 Tool: {tool_name}({tool_args})", flush=True)

            # Parse tool args into dict
            args_dict = {}
            if "=" in tool_args:
                for item in tool_args.split(", "):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        args_dict[k] = v
                trace.tool(
                    tool_name=tool_name,
                    tool_args=args_dict,
                    tool_result=self._get_tool_result(tool_name, customer_id),
                    tool_type="api",
                )
            else:
                trace.tool(
                    tool_name=tool_name,
                    tool_args={"query": tool_args},
                    tool_result=self._get_tool_result(tool_name, customer_id),
                    tool_type="api",
                )
            time.sleep(0.2)  # Simulate tool execution time

    def _get_tool_result(self, tool_name: str, customer_id: str) -> dict:
        """Generate realistic tool results."""
        results = {
            "get_customer_profile": {
                "customer_id": customer_id,
                "name": "John Smith",
                "tier": "Premium",
                "account_age_days": 1247,
                "email": "john.smith@example.com",
            },
            "check_billing_history": {
                "customer_id": customer_id,
                "transactions": [
                    {"date": "2025-01-15", "amount": 99.99, "status": "completed"},
                    {"date": "2025-01-14", "amount": 2.99, "status": "completed"},
                    {"date": "2025-01-10", "amount": 49.99, "status": "completed"},
                ],
                "disputed": 1,
            },
            "verify_transaction": {
                "transaction_id": "TXN-" + uuid.uuid4().hex[:8].upper(),
                "amount": 2.99,
                "status": "verified",
                "refund_eligible": True,
            },
            "check_system_logs": {
                "customer_id": customer_id,
                "failed_attempts": 3,
                "last_login": "2025-02-05 14:23:45 UTC",
                "session_timeout": True,
            },
            "get_device_info": {
                "customer_id": customer_id,
                "device": "iPhone 15 Pro",
                "os_version": "iOS 18.1",
                "browser": "Chrome 120.0",
                "location": "San Francisco, CA",
            },
            "get_full_case_history": {
                "customer_id": customer_id,
                "total_cases": 12,
                "open_cases": 2,
                "recent_issues": [
                    "billing dispute",
                    "login failure",
                    "payment processing",
                ],
            },
            "check_all_integrations": {
                "customer_id": customer_id,
                "billing_status": "active",
                "technical_status": "degraded",
                "crm_status": "active",
            },
            "create_escalation_ticket": {
                "ticket_id": "CASE-" + uuid.uuid4().hex[:8].upper(),
                "priority": "critical",
                "assigned_to": "Support Team Lead",
                "sla_deadline": "4 hours",
                "status": "assigned",
            },
        }
        return results.get(
            tool_name, {"status": "success", "data": "operation completed"}
        )

    def agent_communicates(
        self, from_agent: SupportAgent, to_agent: SupportAgent, message: str
    ) -> None:
        """Agent communication."""
        trace.agent_communication(
            from_agent_id=from_agent.agent_id,
            from_agent_name=from_agent.name,
            to_agent_id=to_agent.agent_id,
            to_agent_name=to_agent.name,
            message_type="collaboration",
            message_content=message,
        )
        print(f"💬 {from_agent.name} → {to_agent.name}: {message[:40]}...")


def run_multi_agent_example():
    """Run example."""
    with trace.run(
        run_name="multi_agent_support",
        agent_type="support_team",
        session_id=f"session_{uuid.uuid4().hex[:8]}",
    ):
        support_system = MultiAgentSupportSystem()

        # Spawn agents
        print("\n--- Spawning Agents ---")
        triage_agent = support_system.spawn_agent(
            "triage_agent",
            "Triage Specialist",
            ["routing", "assessment"],
            model=get_agent_model("triage"),
        )
        billing_agent = support_system.spawn_agent(
            "billing_agent",
            "Billing Specialist",
            ["billing", "refunds"],
            model=get_agent_model("billing"),
        )
        technical_agent = support_system.spawn_agent(
            "technical_agent",
            "Technical Support",
            ["debugging"],
            model=get_agent_model("technical"),
        )
        manager_agent = support_system.spawn_agent(
            "manager_agent",
            "Support Manager",
            ["escalation"],
            model=get_agent_model("manager"),
        )

        # Communication
        print("\n--- Agent Communication ---")
        support_system.agent_communicates(
            manager_agent, triage_agent, "Prioritize billing issues today."
        )

        # Process requests
        print("\n--- Processing Requests ---")
        requests = [
            ("customer_001", "I need help with my bill, incorrect charge"),
            ("customer_002", "Application error when I try to login"),
            ("customer_003", "Complex issue needs escalation"),
        ]

        for customer_id, request in requests:
            support_system.handle_customer_request(customer_id, request)
            if customer_id != requests[-1][0]:
                time.sleep(1)

        # End shift
        print("\n--- End of Shift ---")
        trace.agent_leave(
            agent_id=billing_agent.agent_id,
            agent_name=billing_agent.name,
            reason="shift_complete",
        )
        trace.agent_leave(
            agent_id=technical_agent.agent_id,
            agent_name=technical_agent.name,
            reason="shift_complete",
        )

        trace.final(answer=f"Processed {len(requests)} requests")

    trace.shutdown()

    print("\n" + "=" * 70)
    print("Complete! Run: agent-inspector server → http://localhost:8080")
    print("=" * 70)


if __name__ == "__main__":
    run_multi_agent_example()
