import os
from dotenv import load_dotenv

# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import McpTool, ToolSet, ListSortOrder

# Load environment variables from .env file
load_dotenv()
project_endpoint = os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
mcp_subscription_key = os.getenv("MCP_SUBSCRIPTION_KEY")

# Connect to the agents client
agents_client = AgentsClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True
    )
)

# MCP server configuration
mcp_server_url = "https://apim-mcp-578435.azure-api.net/itconnect-mcp/mcp"
mcp_server_label = "ServiceNow_KB_Articles"

# Initialize agent MCP tool with subscription key in URL
mcp_tool = McpTool(
    server_label=mcp_server_label,
    server_url=mcp_server_url
)
mcp_tool.update_headers("Ocp-Apim-Subscription-Key", mcp_subscription_key)
mcp_tool.set_approval_mode("never")

toolset = ToolSet()
toolset.add(mcp_tool)



# Create agent with MCP tool and process agent run
with agents_client:

    # Create a new agent
    agent = agents_client.create_agent(
        model=model_deployment,
        name="my-mcp-agent",
        description="This agent uses the MCP server at https://learn.microsoft.com/api/mcp to find the latest official Microsoft documentation.",
        instructions="""
        You have access to an MCP server called `ServiceNow_KB_Articles` - this tool allows you to 
        search through ServiceNow Knowledge Base Articles to find answers. """
    )
    
    

    # Log info
    print(f"Created agent, ID: {agent.id}")
    print(f"MCP Server: {mcp_tool.server_label} at {mcp_tool.server_url}")

    # Create thread for communication
    thread = agents_client.threads.create()
    print(f"Created thread, ID: {thread.id}")    

    # Continuous conversation loop
    while True:
        # Get user input
        prompt = input("\nHow can I help? (type 'quit' to exit): ")
        
        # Check if user wants to quit
        if prompt.lower() == 'quit':
            print("Goodbye!")
            break
            
        if len(prompt.strip()) == 0:
            print("Please enter a valid prompt.")
            continue

        # Create a message on the thread
        message = agents_client.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
        )
        print(f"Created message, ID: {message.id}")

        # Create and process agent run in thread with MCP tools
        run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id, toolset=toolset)
        print(f"Created run, ID: {run.id}")
        
        # Check run status
        print(f"Run completed with status: {run.status}")
        if run.status == "failed":
            print(f"Run failed: {run.last_error}")
            continue

        # Display run steps and tool calls
        run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)
        for step in run_steps:
            print(f"Step {step['id']} status: {step['status']}")

            # Check if there are tool calls in the step details
            step_details = step.get("step_details", {})
            tool_calls = step_details.get("tool_calls", [])

            if tool_calls:
                # Display the MCP tool call details
                print("  MCP Tool calls:")
                for call in tool_calls:
                    print(f"    Tool Call ID: {call.get('id')}")
                    print(f"    Type: {call.get('type')}")
                    print(f"    Name: {call.get('name')}")

            print()  # add an extra newline between steps

        # Get the latest response from the agent
        messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        if messages:
            for message in messages: 
                if message.text_messages: 
                    if message.role == "assistant":
                        last_text = message.text_messages[-1]
                        print(f"\nASSISTANT: {last_text.text.value}")
                        print("-" * 50)

    # Show full conversation history at the end
    print("\nFull Conversation History:")
    print("=" * 50)
    messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    for msg in messages:
        if msg.text_messages:
            last_text = msg.text_messages[-1]
            print(f"{msg.role.upper()}: {last_text.text.value}")
            print("-" * 30)

    # Clean-up and delete the agent once the run is finished.
    agents_client.delete_agent(agent.id)
    print("Deleted agent")