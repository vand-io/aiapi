import os
from aiapi import AIChat, AITool, VandBasicAPITool


GPT_MODEL = "gpt-3.5-turbo-1106"
openai_api_key = os.getenv("OPENAI_API_KEY")
# or uncomment and set your key below
# openai.api_key = "sk-..."

if openai_api_key is None:
    print("Did you forget to set your OpenAI API Key? e.g. export OPENAI_API_KEY='sk-...' ")

# Define our function.  In this case a simple tool to get the current time.
from datetime import datetime
def currentTime():
    current_time = datetime.now().time()
    return str(current_time)

# write the function spec.  Note that the name MUST match the defined function.  In this case "currentTime"
# even though this function has no arguments we must create a dummy property for OpenAI's API to accept it.
currentTime_spec = {
    "name": "currentTime",
    "description": "Get the current time.",
    "parameters": {
        "type": "object",
        "properties": {
            "fake property": {
                "type": "null",
            },
        },
        "required": [],
    },
}


# Make the function available for use
AITool.define_function(spec=currentTime_spec, func=currentTime)

# Initiate a new AIChat session
ai = AIChat(console=False)

# Send a message to the AI model, include our 
response = ai("What time is it?", functions=["currentTime"])
print(response)

# Alternativly you can stream the response instead.
for chunk in ai.stream("What time is it?", functions=["currentTime"]):
    response_td = chunk["delta"]
    print(response_td, end="")
print("")

# Load a tool directly from Vand (https://vand.io)
# Note each tool could countain several "functions"
vand_tool = VandBasicAPITool.get_toolpack("vand-6657ac86-b112-4776-a5cc-fae3aa80ba56")
AITool.define_function(spec=vand_tool.functions, func=vand_tool.execute_tool_call)

# See what tools are available
tools = AITool.get_function_names()
print(tools)


response = ai("What's the weather like in Detriot?", functions=tools)
print(response)

ai.save_session(output_path="chat_session.json", format="json")

ai.pprint_session()