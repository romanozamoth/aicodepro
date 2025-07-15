import traceback
from copy import deepcopy
from datetime import datetime
import json
import uuid
import logging
from .helpers.access import (
    get_agent_by_name,
    get_external_tools,
)
from .helpers.state import (
    construct_state_from_response
)
from .helpers.control import get_latest_assistant_msg, get_latest_non_assistant_messages, get_last_agent_name
from .swarm_wrapper import run as swarm_run, run_streamed as swarm_run_streamed, create_response, get_agents
from src.utils.common import common_logger as logger
import asyncio

# Create a dedicated logger for swarm wrapper
logger.setLevel(logging.INFO)
print("Logger level set to INFO")

def order_messages(messages):
    """
    Sorts each message's keys in a specified order and returns a new list of ordered messages.
    """
    ordered_messages = []
    for msg in messages:
        # Filter out None values
        msg = {k: v for k, v in msg.items() if v is not None}

        # Specify the exact order
        ordered = {}
        for key in ['role', 'sender', 'content', 'created_at', 'timestamp']:
            if key in msg:
                ordered[key] = msg[key]

        # Add remaining keys in alphabetical order
        remaining_keys = sorted(k for k in msg if k not in ordered)
        for key in remaining_keys:
            ordered[key] = msg[key]

        ordered_messages.append(ordered)
    return ordered_messages


def clean_up_history(agent_data):
    """
    Ensures each agent's history is sorted using order_messages.
    """
    for data in agent_data:
        data["history"] = order_messages(data["history"])
    return agent_data

def create_final_response(response, turn_messages, tokens_used, all_agents):
    """
    Constructs the final response data (messages, tokens_used, updated state) that a caller would need.
    """
    # Ensure response has a messages attribute
    if not hasattr(response, 'messages'):
        response.messages = []

    # Assign the appropriate messages to the response
    response.messages = turn_messages

    # Ensure tokens_used is a valid dictionary
    if not isinstance(tokens_used, dict):
        tokens_used = {"total": 0, "prompt": 0, "completion": 0}  # Default values if not a dictionary

    # Ensure response has a tokens_used attribute that's a dictionary
    if not hasattr(response, 'tokens_used') or not isinstance(response.tokens_used, dict):
        response.tokens_used = {}

    response.tokens_used = tokens_used

    # Ensure response has an agent attribute for state construction
    if not hasattr(response, 'agent'):
        if all_agents and len(all_agents) > 0:
            response.agent = all_agents[0]  # Set default agent if missing

    new_state = construct_state_from_response(response, all_agents)
    return response.messages, response.tokens_used, new_state


async def run_turn(
    messages, start_agent_name, agent_configs, tool_configs, start_turn_with_start_agent, state={}, additional_tool_configs=[], complete_request={}
):
    """
    Coordinates a single 'turn' of conversation or processing among agents.
    Includes validation, agent setup, optional greeting logic, error handling, and post-processing steps.
    """
    logger.info("Running stateless turn")
    print("Running stateless turn")

    # Sort messages by the specified ordering
    #messages = order_messages(messages)

    # Merge any additional tool configs
    tool_configs = tool_configs + additional_tool_configs

    # Determine if this is a greeting turn
    greeting_turn = not any(msg.get("role") != "system" for msg in messages)
    turn_messages = []
    # Initialize tokens_used as a dictionary
    tokens_used = {"total": 0, "prompt": 0, "completion": 0}

    agent_data = state.get("agent_data", [])

    # If not a greeting turn, localize the last user or system messages
    if not greeting_turn:
        latest_assistant_msg = get_latest_assistant_msg(messages)
        latest_non_assistant_msgs = get_latest_non_assistant_messages(messages)
        msg_type = latest_non_assistant_msgs[-1]["role"]

        # Determine the last agent from state/config
        last_agent_name = get_last_agent_name(
            state=state,
            agent_configs=agent_configs,
            start_agent_name=start_agent_name,
            msg_type=msg_type,
            latest_assistant_msg=latest_assistant_msg,
            start_turn_with_start_agent=start_turn_with_start_agent
        )
    else:
        # For a greeting turn, we assume the last agent is the start_agent_name
        last_agent_name = start_agent_name

    state["agent_data"] = agent_data

    # Initialize all agents
    logger.info("Initializing agents")
    print("Initializing agents")
    new_agents = get_agents(
        agent_configs=agent_configs,
        tool_configs=tool_configs,
        complete_request=complete_request
    )
    # Prepare escalation agent
    last_new_agent = get_agent_by_name(last_agent_name, new_agents)

    # Gather external tools for Swarm
    external_tools = get_external_tools(tool_configs)
    logger.info(f"Found {len(external_tools)} external tools")
    print(f"Found {len(external_tools)} external tools")

    # If no validation error yet, proceed with the main run

    logger.info("Running swarm run")
    print("Running swarm run")

    response = await swarm_run(
        agent=last_new_agent,
        messages=messages,
        external_tools=external_tools,
        tokens_used=tokens_used
    )

    logger.info("Swarm run completed")
    print("Swarm run completed")

    # Initialize response.messages if it doesn't exist
    if not hasattr(response, 'messages'):
        response.messages = []

    # Convert the ResponseOutputMessage to a standard message format
    if hasattr(response, 'new_items') and response.new_items and hasattr(response.new_items[-1], 'raw_item'):
        raw_item = response.new_items[-1].raw_item
        # Extract text content from ResponseOutputText objects
        content = ""
        if hasattr(raw_item, 'content') and raw_item.content:
            for content_item in raw_item.content:
                if hasattr(content_item, 'text'):
                    content += content_item.text

        # Create a standard message dictionary
        standard_message = {
            "role": raw_item.role if hasattr(raw_item, 'role') else "assistant",
            "content": content,
            "sender": last_new_agent.name,
            "created_at": None,
            "response_type": "internal"
        }

        # Add the converted message to response messages
        response.messages.append(standard_message)

    logger.info("Converted message added to response messages")
    print("Converted message added to response messages")

    # Use a dictionary for tokens_used
    tokens_used = {"total": 0, "prompt": 0, "completion": 0}  # Default values as placeholders

    # Ensure turn_messages can be extended with response.messages
    if hasattr(response, 'messages') and isinstance(response.messages, list):
        turn_messages.extend(response.messages)

    logger.info(f"Completed run of agent: {last_new_agent.name}")
    print(f"Completed run of agent: {last_new_agent.name}")


    # Otherwise, duplicate the last response as external
    logger.info("No post-processing agent found. Duplicating last response and setting to external.")
    print("No post-processing agent found. Duplicating last response and setting to external.")
    if turn_messages:
        duplicate_msg = deepcopy(turn_messages[-1])
        duplicate_msg["response_type"] = "external"
        duplicate_msg["sender"] += " >> External"

        # Ensure tokens_used remains a proper dictionary
        if not isinstance(tokens_used, dict):
            tokens_used = {"total": 0, "prompt": 0, "completion": 0}  # Default values if not a dictionary

        response = create_response(
            messages=[duplicate_msg],
            tokens_used=tokens_used,
            agent=last_new_agent,
            error_msg=''
        )

        # Ensure response has messages attribute
        if hasattr(response, 'messages') and isinstance(response.messages, list):
            turn_messages.extend(response.messages)

    # Finalize the response
    logger.info("Finalizing response")
    print("Finalizing response")
    return create_final_response(
        response=response,
        turn_messages=turn_messages,
        tokens_used=tokens_used,
        all_agents=new_agents
    )

async def run_turn_streamed(
    messages,
    start_agent_name,
    agent_configs,
    tool_configs,
    start_turn_with_start_agent,
    state={},
    additional_tool_configs=[],
    complete_request={}
):
    final_state = None  # Initialize outside try block
    try:
        # Initialize agents and get external tools
        new_agents = get_agents(agent_configs=agent_configs, tool_configs=tool_configs, complete_request=complete_request)
        last_agent_name = get_last_agent_name(
            state=state,
            agent_configs=agent_configs,
            start_agent_name=start_agent_name,
            msg_type="user",
            latest_assistant_msg=None,
            start_turn_with_start_agent=start_turn_with_start_agent
        )
        last_new_agent = get_agent_by_name(last_agent_name, new_agents)
        external_tools = get_external_tools(tool_configs)

        current_agent = last_new_agent
        tokens_used = {"total": 0, "prompt": 0, "completion": 0}

        stream_result = await swarm_run_streamed(
            agent=last_new_agent,
            messages=messages,
            external_tools=external_tools,
            tokens_used=tokens_used
        )

        # Process streaming events
        async for event in stream_result.stream_events():
            print('='*50)
            print("Received event: ", event)
            print('-'*50)

            # Handle raw response events and accumulate tokens
            if event.type == "raw_response_event":
                if hasattr(event.data, 'type') and event.data.type == "response.completed":
                    if hasattr(event.data.response, 'usage'):
                        tokens_used["total"] += event.data.response.usage.total_tokens
                        tokens_used["prompt"] += event.data.response.usage.input_tokens
                        tokens_used["completion"] += event.data.response.usage.output_tokens
                        print('-'*50)
                        print(f"Found usage information. Updated cumulative tokens: {tokens_used}")
                        print('-'*50)

                # Handle ResponseFunctionWebSearch specifically
                if hasattr(event, 'data') and hasattr(event.data, 'raw_item'):
                    raw_item = event.data.raw_item

                    # Check if it's a web search call
                    if (hasattr(raw_item, 'type') and raw_item.type == 'web_search_call') or (
                        isinstance(raw_item, dict) and raw_item.get('type') == 'web_search_call'
                    ):
                        # Get call_id safely, regardless of structure
                        call_id = None
                        if hasattr(raw_item, 'id'):
                            call_id = raw_item.id
                        elif isinstance(raw_item, dict) and 'id' in raw_item:
                            call_id = raw_item['id']
                        else:
                            call_id = str(uuid.uuid4())

                        # Get status safely
                        status = 'unknown'
                        if hasattr(raw_item, 'status'):
                            status = raw_item.status
                        elif isinstance(raw_item, dict) and 'status' in raw_item:
                            status = raw_item['status']

                        # Emit a tool call for web search
                        message = {
                            'content': None,
                            'role': 'assistant',
                            'sender': current_agent.name if current_agent else None,
                            'tool_calls': [{
                                'function': {
                                    'name': 'web_search',
                                    'arguments': json.dumps({
                                        'search_id': call_id,
                                        'status': status
                                    })
                                },
                                'id': call_id,
                                'type': 'function'
                            }],
                            'tool_call_id': None,
                            'tool_name': None,
                            'response_type': 'internal'
                        }
                        print("Yielding web search raw response message: ", message)
                        yield ('message', message)

                continue

            # Update current agent when it changes
            elif event.type == "agent_updated_stream_event":
                if current_agent.name == event.new_agent.name:
                    continue

                tool_call_id = str(uuid.uuid4())

                # yield the transfer invocation
                message = {
                    'content': None,
                    'role': 'assistant',
                    'sender': current_agent.name,
                    'tool_calls': [{
                        'function': {
                            'name': 'transfer_to_agent',
                            'arguments': json.dumps({
                                'assistant': event.new_agent.name
                            })
                        },
                        'id': tool_call_id,
                        'type': 'function'
                    }],
                    'tool_call_id': None,
                    'tool_name': None,
                    'response_type': 'internal'
                }
                print("Yielding message: ", message)
                yield ('message', message)

                # yield the transfer result
                message = {
                    'content': json.dumps({
                        'assistant': event.new_agent.name
                    }),
                    'role': 'tool',
                    'sender': None,
                    'tool_calls': None,
                    'tool_call_id': tool_call_id,
                    'tool_name': 'transfer_to_agent',
                }
                print("Yielding message: ", message)
                yield ('message', message)

                current_agent = event.new_agent
                continue

            # Handle run items (tools, messages, etc)
            elif event.type == "run_item_stream_event":
                current_agent = event.item.agent
                if event.item.type == "tool_call_item":
                    # Check if it's a ResponseFunctionWebSearch object
                    if hasattr(event.item.raw_item, 'type') and event.item.raw_item.type == 'web_search_call':
                        call_id = event.item.raw_item.id if hasattr(event.item.raw_item, 'id') else str(uuid.uuid4())
                        message = {
                            'content': None,
                            'role': 'assistant',
                            'sender': current_agent.name if current_agent else None,
                            'tool_calls': [{
                                'function': {
                                    'name': 'web_search',
                                    'arguments': json.dumps({
                                        'search_id': call_id
                                    })
                                },
                                'id': call_id,
                                'type': 'function'
                            }],
                            'tool_call_id': None,
                            'tool_name': None,
                            'response_type': 'internal'
                        }
                        print("Yielding message: ", message)
                        yield ('message', message)

                        result_message = {
                        'content': "Web search done",
                        'role': 'tool',
                        'sender': None,
                        'tool_calls': None,
                        'tool_call_id': call_id,
                        'tool_name': 'web_search',
                        'response_type': 'internal'
                        }

                        print("Yielding web search results: ", result_message)
                        yield ('message', result_message)
                    else:
                        # Handle normal tool calls
                        message = {
                            'content': None,
                            'role': 'assistant',
                            'sender': current_agent.name if current_agent else None,
                            'tool_calls': [{
                                'function': {
                                    'name': event.item.raw_item.name,
                                    'arguments': event.item.raw_item.arguments
                                },
                                'id': event.item.raw_item.call_id,
                                'type': 'function'
                            }],
                            'tool_call_id': None,
                            'tool_name': None,
                            'response_type': 'internal'
                        }
                        print("Yielding message: ", message)
                        yield ('message', message)


                elif event.item.type == "tool_call_output_item":
                    # Check if it's a web search result
                    if isinstance(event.item.raw_item, dict) and event.item.raw_item.get('type') == 'web_search_results':
                        call_id = event.item.raw_item.get('search_id', event.item.raw_item.get('id', str(uuid.uuid4())))
                        message = {
                            'content': str(event.item.output),
                            'role': 'tool',
                            'sender': None,
                            'tool_calls': None,
                            'tool_call_id': call_id,
                            'tool_name': 'web_search',
                            'response_type': 'internal'
                        }
                    else:
                        # Safe extraction of call_id and name
                        call_id = None
                        tool_name = None

                        # Handle different types of raw_item
                        if isinstance(event.item.raw_item, dict):
                            call_id = event.item.raw_item.get('call_id')
                            tool_name = event.item.raw_item.get('name')
                        elif hasattr(event.item.raw_item, 'call_id'):
                            call_id = event.item.raw_item.call_id
                            if hasattr(event.item.raw_item, 'name'):
                                tool_name = event.item.raw_item.name

                        message = {
                            'content': str(event.item.output),
                            'role': 'tool',
                            'sender': None,
                            'tool_calls': None,
                            'tool_call_id': call_id,
                            'tool_name': tool_name,
                            'response_type': 'internal'
                        }

                    print("Yielding message: ", message)
                    yield ('message', message)

                elif event.item.type == "message_output_item":
                    content = ""
                    url_citations = []

                    # Extract text content and any URL citations
                    if hasattr(event.item.raw_item, 'content'):
                        for content_item in event.item.raw_item.content:
                            # Handle text content
                            if hasattr(content_item, 'text'):
                                content += content_item.text

                            # Extract URL citations if present
                            if hasattr(content_item, 'annotations'):
                                for annotation in content_item.annotations:
                                    if hasattr(annotation, 'type') and annotation.type == 'url_citation':
                                        citation = {
                                            'url': annotation.url if hasattr(annotation, 'url') else '',
                                            'title': annotation.title if hasattr(annotation, 'title') else '',
                                            'start_index': annotation.start_index if hasattr(annotation, 'start_index') else 0,
                                            'end_index': annotation.end_index if hasattr(annotation, 'end_index') else 0
                                        }
                                        url_citations.append(citation)

                    # Create message with URL citations if they exist
                    message = {
                        'content': content,
                        'role': 'assistant',
                        'sender': current_agent.name,
                        'tool_calls': None,
                        'tool_call_id': None,
                        'tool_name': None,
                        'response_type': 'external'
                    }

                    # Add citations if any were found
                    if url_citations:
                        message['citations'] = url_citations

                    print("Yielding message: ", message)
                    yield ('message', message)

                # Handle web search function call events
                elif event.item.type == "web_search_call_item" or (hasattr(event.item, 'raw_item') and hasattr(event.item.raw_item, 'type') and event.item.raw_item.type == 'web_search_call'):
                    # Extract web search call ID if available
                    call_id = None
                    if hasattr(event.item.raw_item, 'id'):
                        call_id = event.item.raw_item.id

                    message = {
                        'content': None,
                        'role': 'assistant',
                        'sender': current_agent.name if current_agent else None,
                        'tool_calls': [{
                            'function': {
                                'name': 'web_search',
                                'arguments': json.dumps({
                                    'search_id': call_id
                                })
                            },
                            'id': call_id or str(uuid.uuid4()),
                            'type': 'function'
                        }],
                        'tool_call_id': None,
                        'tool_name': None,
                        'response_type': 'internal'
                    }
                    print("Yielding web search message: ", message)
                    yield ('message', message)

                # Handle web search results
                elif event.item.type == "web_search_results_item" or (
                    hasattr(event.item, 'raw_item') and (
                        (hasattr(event.item.raw_item, 'type') and event.item.raw_item.type == 'web_search_results') or
                        (isinstance(event.item.raw_item, dict) and event.item.raw_item.get('type') == 'web_search_results')
                    )
                ):
                    # Extract call_id safely
                    call_id = None
                    raw_item = event.item.raw_item

                    # Try several ways to get the search_id or id
                    if hasattr(raw_item, 'search_id'):
                        call_id = raw_item.search_id
                    elif isinstance(raw_item, dict) and 'search_id' in raw_item:
                        call_id = raw_item['search_id']
                    elif hasattr(raw_item, 'id'):
                        call_id = raw_item.id
                    elif isinstance(raw_item, dict) and 'id' in raw_item:
                        call_id = raw_item['id']
                    else:
                        call_id = str(uuid.uuid4())

                    # Extract results content safely
                    results = {}

                    # Try event.item.output first
                    if hasattr(event.item, 'output'):
                        results = event.item.output
                    # Then try raw_item.results
                    elif hasattr(raw_item, 'results'):
                        results = raw_item.results
                    elif isinstance(raw_item, dict) and 'results' in raw_item:
                        results = raw_item['results']

                    # Format the results for output
                    results_str = ""
                    try:
                        results_str = json.dumps(results) if results else ""
                    except Exception as e:
                        print(f"Error serializing results: {str(e)}")
                        results_str = str(results)

                    message = {
                        'content': results_str,
                        'role': 'tool',
                        'sender': None,
                        'tool_calls': None,
                        'tool_call_id': call_id,
                        'tool_name': 'web_search',
                        'response_type': 'internal'
                    }
                    print("Yielding web search results: ", message)
                    yield ('message', message)

            print(f"\n{'='*50}\n")

        # After all events are processed, set final state
        final_state = {
            "last_agent_name": current_agent.name if current_agent else None,
            "tokens": tokens_used
        }
        yield ('done', {'state': final_state})

    except Exception as e:
        print(traceback.format_exc())
        print(f"Error in stream processing: {str(e)}")
        yield ('error', {'error': str(e), 'state': final_state})  # Include final_state in error response