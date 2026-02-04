"""
Base Agent Framework for Invoice Automation.

This module implements a tool-using Agentic AI pattern where agents:
1. Observe the current state
2. Reason about what action to take
3. Execute tools to perform actions
4. Update state based on results

This demonstrates the Agentic AI concepts used in enterprise automation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json


class AgentRole(str, Enum):
    """Roles that agents can perform in the invoice processing pipeline."""
    ORCHESTRATOR = "orchestrator"
    EXTRACTOR = "extractor"
    VALIDATOR = "validator"
    ROUTER = "router"
    APPROVER = "approver"


@dataclass
class Tool:
    """Represents a tool that an agent can use."""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    required_params: List[str] = field(default_factory=list)

    def to_schema(self) -> Dict:
        """Convert tool to schema format for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required_params
            }
        }


@dataclass
class AgentThought:
    """Represents agent's reasoning process (Chain of Thought)."""
    observation: str
    reasoning: str
    action: str
    action_input: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentResponse:
    """Response from an agent action."""
    success: bool
    result: Any
    thoughts: List[AgentThought]
    tools_used: List[str]
    execution_time_ms: int
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Implements the ReAct (Reasoning + Acting) pattern:
    - Thought: Agent reasons about the current state
    - Action: Agent decides which tool to use
    - Observation: Agent observes the result
    - Repeat until task is complete
    """

    def __init__(self, name: str, role: AgentRole):
        self.name = name
        self.role = role
        self.tools: Dict[str, Tool] = {}
        self.thought_history: List[AgentThought] = []
        self.max_iterations = 10

    def register_tool(self, tool: Tool) -> None:
        """Register a tool that this agent can use."""
        self.tools[tool.name] = tool

    def get_available_tools(self) -> List[Dict]:
        """Get list of available tools in schema format."""
        return [tool.to_schema() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool with given parameters."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered")

        tool = self.tools[tool_name]

        # Validate required parameters
        for param in tool.required_params:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")

        # Execute the tool
        result = await tool.function(**kwargs)
        return result

    def record_thought(self, observation: str, reasoning: str,
                       action: str, action_input: Dict) -> AgentThought:
        """Record agent's thought process."""
        thought = AgentThought(
            observation=observation,
            reasoning=reasoning,
            action=action,
            action_input=action_input
        )
        self.thought_history.append(thought)
        return thought

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute the agent's main task. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent. Must be implemented by subclasses."""
        pass

    def format_thoughts_for_display(self) -> str:
        """Format thought history for human-readable display."""
        output = []
        for i, thought in enumerate(self.thought_history, 1):
            output.append(f"\n--- Step {i} ---")
            output.append(f"Observation: {thought.observation}")
            output.append(f"Reasoning: {thought.reasoning}")
            output.append(f"Action: {thought.action}")
            output.append(f"Input: {json.dumps(thought.action_input, indent=2)}")
        return "\n".join(output)

    def clear_history(self) -> None:
        """Clear thought history for new task."""
        self.thought_history = []


class AgentOrchestrator:
    """
    Orchestrates multiple agents to complete complex tasks.

    This is the "brain" of the Agentic AI system that:
    1. Receives a task (e.g., process an invoice)
    2. Breaks it down into sub-tasks
    3. Delegates to specialized agents
    4. Aggregates results
    5. Handles exceptions
    """

    def __init__(self):
        self.agents: Dict[AgentRole, BaseAgent] = {}
        self.execution_log: List[Dict] = []

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the orchestrator."""
        self.agents[agent.role] = agent

    async def process_invoice(self, document_path: str) -> Dict[str, Any]:
        """
        Main workflow: Process an invoice through the agent pipeline.

        Pipeline stages:
        1. EXTRACTOR: Extract data from document
        2. VALIDATOR: Validate extracted data
        3. ROUTER: Determine approval routing
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "document_path": document_path,
            "stages": [],
            "final_result": None,
            "errors": []
        }

        try:
            # Stage 1: Extraction
            if AgentRole.EXTRACTOR in self.agents:
                extractor = self.agents[AgentRole.EXTRACTOR]
                extraction_result = await extractor.run({"document_path": document_path})

                result["stages"].append({
                    "stage": "extraction",
                    "agent": extractor.name,
                    "success": extraction_result.success,
                    "result": extraction_result.result,
                    "thoughts": [t.__dict__ for t in extraction_result.thoughts]
                })

                if not extraction_result.success:
                    result["errors"].append(f"Extraction failed: {extraction_result.error}")
                    return result

                invoice_data = extraction_result.result

            # Stage 2: Validation
            if AgentRole.VALIDATOR in self.agents:
                validator = self.agents[AgentRole.VALIDATOR]
                validation_result = await validator.run({"invoice_data": invoice_data})

                result["stages"].append({
                    "stage": "validation",
                    "agent": validator.name,
                    "success": validation_result.success,
                    "result": validation_result.result,
                    "thoughts": [t.__dict__ for t in validation_result.thoughts]
                })

                validation_data = validation_result.result

            # Stage 3: Routing
            if AgentRole.ROUTER in self.agents:
                router = self.agents[AgentRole.ROUTER]
                routing_result = await router.run({
                    "invoice_data": invoice_data,
                    "validation_result": validation_data
                })

                result["stages"].append({
                    "stage": "routing",
                    "agent": router.name,
                    "success": routing_result.success,
                    "result": routing_result.result,
                    "thoughts": [t.__dict__ for t in routing_result.thoughts]
                })

                result["final_result"] = routing_result.result

            result["success"] = True
            result["processing_time_ms"] = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

        except Exception as e:
            result["errors"].append(str(e))

        return result

    def get_execution_summary(self) -> str:
        """Get human-readable summary of execution."""
        lines = ["=== Agent Execution Summary ==="]
        for log in self.execution_log:
            lines.append(f"\nAgent: {log.get('agent')}")
            lines.append(f"Status: {'SUCCESS' if log.get('success') else 'FAILED'}")
            lines.append(f"Duration: {log.get('duration_ms')}ms")
        return "\n".join(lines)
