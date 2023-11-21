
# Vand.io AIAPI Library

AIAPI is derived from [simpleaichat](https://github.com/minimaxir/simpleaichat) by minimaxir. Simpleaichat is an excellent library for interacting with AI models.  AIAPI adds function calling and access to a catalog of functions (tools) found on [Vand.io](https://www.vand.io).  If you're not interested in function calling (aka tool calling) you might want to consider using simpleaichat instead.

### AIAPI
AIAPI is a python library that provides convenient access to OpenAI (and soon other) APIs and LLMs.   AIAPI can be used from a browser interface (soon), command line, and embedded as a library in your application.  It has several advantages that simplify the development of applications that leverage AI models.

* Easy to use  sessions that string together all the messages (assistant, user, and function).  This is similar to OpenAI's Assistant API and it's concepts of Threads but handled client side giving you significantly more control including viewing, editing (including assistant messages) and truncating to reduce size to save tokens.
* Sessions can be saved, and loaded.
* Include functions / tools in your application to augment the AI model's capabilities.  These include your own custom tools as well as access to thousands of tools found on https://vand.io.

**Note!!** Utilizing 3rd party tools with your AI model may leak data!  You should be aware of the data flow and have a good understanding of the tools you decide to make available to your AI model.  This applies to OpenAI's GPTs & plugins as well.

### Installation

`pip install --upgrade https://github.com/vand-io/aiapi/tarball/master`

## Quickstart
You'll need to set OpenAI API Key either in an environment variable:
`export OPENAI_API_KEY="sk-..."`

or create a *.env* file in your working directory with the key.
```
OPENAI_API_KEY="sk-..."
```

### Quickstart - CLI
You can launch AIAPI from the console with:
`aiapi`

This will launch an interactive console:
```
GPT: How can I help you?
You: 
```

### Quickstart - code
```py3
# import AIChat
from aiapi import AIChat

# create a chat instance
ai = AIChat(system="You are a helpful assistant.  Take a deep breath and think step by step.")

# sent a user message to the model
ai("What's the difference between a duck and a loon?")
```

### Quickstart - browser
(coming soon)

## Using AIAPI in your code
We'll start off with three types of tool use (function calling) with your AI model.  
 1. Utilizing Tools (functions) imported from Vand.io  (see examples/get_weather.py)
 2. Using a Custom function  (see examples/functions.py)
 3.  Auto Tool

### Utilizing Tools from Vand.io
The quickest way to augment your AI model with a tool or function is to select from the thousands of tools available from the Vand.io catalog.  You can search and select tools at https://www.vand.io.

In this example we'll use a simple tool to get the weather in Detroit.  You can inspect the code and try this out yourself with the [get_weather.py](https://github.com/vand-io/aiapi/blob/main/examples/get_weather.py) file in the examples folder.

First we'll import our dependencies.
```py3
import os
from aiapi import AIChat
```
Set the AI model and fetch/set your OpenAI API key.
```py3
GPT_MODEL = "gpt-3.5-turbo-1106"
openai_api_key = os.getenv("OPENAI_API_KEY")
# or uncomment and set your key below
# openai.api_key = "sk-..."
```
Create the chat session and ask our model about the weather in Detroit without providing any tools.
```py3
ai = AIChat(console=False)

response = ai("What's the weather like in Detroit?")
print(response)
```
And we'll get something similar to:

> I'm sorry, but as an AI assistant, I don't have real-time information.
> However, you can easily check the current weather in Detroit by using
> a  weather website or app, or by asking a voice assistant like Siri or
> Google Assistant.

That's no fun.  Let's try again but this time we'll provide a weather tool.  We search Vand for an appropriate tool (https://vand.io/toolpacks?keyword=weather) and choose the Open-Meteo Weather API by copying it's tool ID (vand-b94925c2-748a-4811-abce-aedd89190663).   In the background AIAPI is fetching the details about the tool so we can make it available to the AI model and our code.

Let's add this to our call to let the model know it can use a tool.
```py3
response = ai("What's the weather like in Detroit?", functions=["vand-b94925c2-748a-4811-abce-aedd89190663"])
print(response)
```
Now we get a much better answer!

> The current weather in Detroit is clear sky with a temperature of 
> 280.99 Kelvin (7.84 degrees Celsius). The humidity is 71%, and the  wind speed is 2.57 meters per second.

Let's print the entire session (thread) so we can review.
```py3
ai.pprint_session()
```

### Using a Custom Function

In this example we'll write a very simple python function to get the current time from our system.  You can inspect the code and try this out yourself with the [custom_functions.py](https://github.com/vand-io/aiapi/blob/main/examples/custom_function.py) file in the examples folder.

First we'll import our dependencies.  Note we're importing a few more things from aiapi this time.
```py3
import os
from aiapi import AIChat, AITool, VandBasicAPITool
```
Set the AI model and fetch/set your OpenAI API key.
```py3
GPT_MODEL = "gpt-3.5-turbo-1106"
openai_api_key = os.getenv("OPENAI_API_KEY")
# or uncomment and set your key below
# openai.api_key = "sk-..."
```

Now let's write a simple python function that just grabs the current time.
```py3
from datetime import datetime
def currentTime():
    current_time = datetime.now().time()
    return str(current_time)
```
Now we need to write our function spec.  See [OpenAI's cookbook](https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models) for more detail.  It is important to note that the **name** in the function spec must match the name of the python function defined above.  In this case both are "currrentTime".
```py3
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
```
We add our new function and it's spec to our AITool class.
```
AITool.define_function(spec=currentTime_spec, func=currentTime)
```
Now we'll create the chat session and ask our model what time it is and let it know that it can use the "currentTime" function.
```
ai = AIChat(console=False)

response = ai("What time is it?", functions=["currentTime"])
print(response)
```

We should get a response similar to:

> The current time is 9:10 AM.

### Important! How Tools (Functions) Work
What's happening in the background is the function spec is sent to the model along with our message (`"What's the weather like in Detroit?"`).

The weather tool's function spec:
```
{
  "name": "getWeatherNow",
  "description": "Get the current weather information based on city, state, and country.",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "The city name."
      },
      "state": {
        "type": "string",
        "description": "The state code."
      },
      "country": {
        "type": "string",
        "description": "The country code."
      }
    },
    "required": []
  }
}
```
The model decides to use the function and sends back a function_call that AIAPI receives.
```
{
    'function_call': {
        'name': 'getWeatherNow', 
        'arguments': {"city": "Detroit", "country": "US"}
    }
}
```
AIAPI takes the function_call and calls the getWeather API with the parameters the model passed.  In this case AIAPI will make a call to the API with something like https://api.open-meteo.com/v1/forecast?latitude=42.3314&longitude=-83.0458&current_weather=true

**Note!** This is how data could leak.  Data in the parameters is passed to 3rd party APIs.

AIAPI receives the response from getWeather (abbreviated below) and passes it back to the AI model in a new message.
```
{
    "current_weather"
    {
        "time":"2023-11-17T06:30",
        "interval":900,
        "temperature":13.5,
        "windspeed":18.3,
        "winddirection":202,
        "is_day":0,
        "weathercode":3
    }
}
```

The AI model now has the current weather information and can provide a reliable and accurate response.
## Other useful items

List all the tools that you've defined/loaded. 
`tools = AITool.get_function_names()`

When you pass tools along with your chat message you can do it in several ways:
1. Dynamically load the tool from Vand.io.  Note that a single tool may have a few functions (e.g. "getCurrentWeather" and "getWeatherForecast").
`ai("What's the weather like in Detroit?", functions=["vand-b94925c2-748a-4811-abce-aedd89190663"])`

2. Pass all tools you've loaded to the model.
`
tools = AITool.get_function_names()
ai("What's the weather like in Detroit?", functions=tools)
`

3. Pass just specific tools that you've already defined/loaded.
`ai("What's the weather like in Detroit?", functions=["getWeather", "getStockQuotes"])`

Remember that tools (functions) count as part of your input tokens so the more tools you pass the larger the message.

You can also save chat sessions (as CSV or JSON) and load them later. The API key is not saved so you will have to provide that when loading.

```py3
ai.save_session()  # CSV, will only save messages
ai.save_session(output_path="weather_chat.json", format="json")
ai.save_session(format="json", minify=True)  # JSON

ai.load_session("weather_chat.json")
ai.load_session("my.csv")

```
