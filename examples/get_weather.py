import os
from aiapi import AIChat


'''
1. Create an AIChat session
2. Send a request that needs the tool (e.g. what's the weather like in Detroit?)
3. Get function call
4. execute function
5. return funciton results to model

'''

GPT_MODEL = "gpt-3.5-turbo-1106"
openai_api_key = os.getenv("OPENAI_API_KEY")
# or uncomment and set your key below
# openai.api_key = "sk-..."

if openai_api_key is None:
    print("Did you forget to set your OpenAI API Key? e.g. export OPENAI_API_KEY='sk-...' ")

# create the chat session
ai = AIChat(console=False)

# send a chat request to the session and get the response
response = ai("What's the weather like in Detroit?")
print(response)
'''
I'm sorry, but as an AI assistant, I don't have real-time information. 
However, you can easily check the current weather in Detroit by using a 
weather website or app, or by asking a voice assistant like Siri or 
Google Assistant.
'''

# this time provide a tool (function) for getting the weather
# you can find other tools (functions) at https://vand.io
response = ai("What's the weather like in Detroit?", functions=["vand-b94925c2-748a-4811-abce-aedd89190663"])
print(response)
'''
The current weather in Detroit is clear sky with a temperature of 
280.99 Kelvin (7.84 degrees Celsius). The humidity is 71%, and the 
wind speed is 2.57 meters per second.
'''

'''
NOTE: the function call (an https request to a weather service api) is made from the 
machine running this code.
'''

# print the entier conversation to see the function call and response.
ai.pprint_session()