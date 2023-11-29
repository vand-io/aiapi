# be sure to have installed Gradio with `pip install gradio`
import os
from aiapi import AIChat, AITool, VandBasicAPITool
import gradio as gr


GPT_MODEL = "gpt-3.5-turbo-1106"
openai_api_key = os.getenv("OPENAI_API_KEY")
# or uncomment and set your key below
# openai.api_key = "sk-..."

if openai_api_key is None:
    print("Did you forget to set your OpenAI API Key? e.g. export OPENAI_API_KEY='sk-...' ")

ai = AIChat(console=False, model=GPT_MODEL)

def get_vand_toolpack(toolpack_id):
    tools = []
    vand_tool = VandBasicAPITool.get_toolpack(toolpack_id)
    if vand_tool.functions:
        for tool in vand_tool.functions:
            tools.append(tool['name'])
    # Make the tools available for use
    AITool.define_function(spec=vand_tool.functions, func=vand_tool.execute_tool_call)
    # return the list of tool names
    return tools

'''
Load a toolpack directly from Vand (https://vand.io)
Note each toolpack could countain several tools (aka functions)

Other tools to try by replacing the vand-xxx toolpack_id below:
vand-1b4c9b3b-cefc-4965-a74b-3fcc593586ec - Search and web text extraction
vand-b94925c2-748a-4811-abce-aedd89190663 - Weather

'''
vand_tool = VandBasicAPITool.get_toolpack("vand-b94925c2-748a-4811-abce-aedd89190663") # replace vand-xxx and restart to try other tools
AITool.define_function(spec=vand_tool.functions, func=vand_tool.execute_tool_call)

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

# See what tools are available
tools = AITool.get_function_names()

def predict(message, history, tools, tokens):

    print(f"These are tools: {tools}")
    params = {"temperature": 0.8, "max_tokens": tokens}
       
    for chunk in ai.stream(message, functions=tools, params=params):
        response_td = chunk["response"]
        yield response_td


demo = gr.ChatInterface(predict,
                        additional_inputs=[    
                            gr.CheckboxGroup(tools, label="Tools", info="Select the tools you'd like to make available to the model."),
                            gr.Slider(10, 500, value=200, label="Max Tokens"),
                        ],
                        additional_inputs_accordion=gr.Accordion(label="Options", open=True),
                        analytics_enabled=False,
                        undo_btn=None,
                        clear_btn=None,
                        retry_btn=None,                     
                       )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0")

'''

# tab one
tab1 = gr.ChatInterface(predict,
                        additional_inputs=[                            
                            gr.Dropdown(
                                AITool.get_function_names(), multiselect=True, label="Tools", info="Select the tools you'd like to include in your chat.  Add more tools in the 'Tool Finder' tab."
                            ),
                            gr.Slider(10, 500, value=200, label="Max Tokens"),
                        ],
                        additional_inputs_accordion=gr.Accordion(label="Options", open=True),
                        analytics_enabled=False,
                        undo_btn=None,
                        clear_btn=None,                    
                       )
# tab two
tab2 = gr.Interface(
    fn=get_vand_toolpack,
    inputs=[
        gr.Textbox(
            label="Vand Tool ID",
            info="vand-xxx",
            lines=1,
            value="vand-b94925c2-748a-4811-abce-aedd89190663",
        ),
    ],
    outputs=[
        gr.Textbox(
            label="Tools",
            info="Available tools",
            lines=7,
            value=AITool.get_function_names(),
        ),
    ],
    title="Add tools",
    allow_flagging="never",
    article="Find tools at [Vand.io](https://vand.io)"

)

demo = gr.TabbedInterface([tab1, tab2], ["Chatbot", "Tool Finder"], analytics_enabled=False)


if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0")

'''

# tools_list = ["tool1", "tool2", "tool3"]
# import random
# with gr.Blocks() as demo:
#     chatbot = gr.Chatbot()
#     with gr.Row():
#        msg = gr.Textbox(container=False, scale=4)
#        btn = gr.Button("Submit", scale=1)
#     gr.Dropdown(tools, multiselect=True, label="Tools", info="Select the tools you'd like made available to the model.")
#     clear = gr.ClearButton([msg, chatbot])

#     def respond(message, chat_history, tools):
#        bot_message = random.choice(["How are you?", "I love you", "I'm very hungry"])
#        print(tools)
#        chat_history.append((message, bot_message))
#        return "", chat_history
#     inputs={msg, chatbot, tools_list}
#     msg.submit(respond, inputs=inputs, outputs=[msg, chatbot])
#     btn.click(respond, inputs=inputs, outputs=[msg, chatbot])

# demo.queue()
# demo.launch(server_name="0.0.0.0")