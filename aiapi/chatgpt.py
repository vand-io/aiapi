from pydantic import HttpUrl
from httpx import Client, AsyncClient
from typing import List, Dict, Union, Set, Any
import orjson

from .models import ChatMessage, ChatSession, AITool
from .utils import remove_a_key

from .vand_utils import VandBasicAPITool

tool_prompt = """From the list of tools below:
- Reply ONLY with the number of the tool appropriate in response to the user's last message.
- If no tool is appropriate, ONLY reply with \"0\".

{tools}"""


class ChatGPTSession(ChatSession):
    api_url: HttpUrl = "https://api.openai.com/v1/chat/completions"
    input_fields: Set[str] = {"role", "content", "name"}
    system: str = "You are a helpful assistant."
    params: Dict[str, Any] = {"temperature": 0.7}

    def prepare_request(
        self,
        prompt: str,
        function_name: str = None,
        system: str = None,
        params: Dict[str, Any] = None,
        stream: bool = False,
        functions: List = None,
        input_schema: Any = None,
        output_schema: Any = None,
        is_function_calling_required: bool = True,
    ):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth['api_key'].get_secret_value()}",
        }

        system_message = ChatMessage(role="system", content=system or self.system)
        #used for ChatMessage;
        function_list = []
        if functions:
            for function in functions:
                function_list.append(function['name'])

        if not input_schema:
            if function_name:
                user_message = ChatMessage(role="function", name=function_name, content=prompt, functions=function_list)
            else:
                user_message = ChatMessage(role="user", content=prompt, functions=function_list)
        else:
            assert isinstance(
                prompt, input_schema
            ), f"prompt must be an instance of {input_schema.__name__}"
            user_message = ChatMessage(
                role="function",
                content=prompt.model_dump_json(),
                name=input_schema.__name__,
            )

        gen_params = params or self.params
        data = {
            "model": self.model,
            "messages": self.format_input_messages(system_message, user_message),
            "stream": stream,
            **gen_params,
        }

        if functions:
            data["functions"] = functions

        # Add function calling parameters if a schema is provided
        if input_schema or output_schema:
            functions = []
            if input_schema:
                input_function = self.schema_to_function(input_schema)
                functions.append(input_function)
            if output_schema:
                output_function = self.schema_to_function(output_schema)
                functions.append(
                    output_function
                ) if output_function not in functions else None
                if is_function_calling_required:
                    data["function_call"] = {"name": output_schema.__name__}
            data["functions"] = functions

        return headers, data, user_message

    def schema_to_function(self, schema: Any):
        assert schema.__doc__, f"{schema.__name__} is missing a docstring."
        assert (
            "title" not in schema.__fields__.keys()
        ), "`title` is a reserved keyword and cannot be used as a field name."
        schema_dict = schema.model_json_schema()
        remove_a_key(schema_dict, "title")

        return {
            "name": schema.__name__,
            "description": schema.__doc__,
            "parameters": schema_dict,
        }

    def process_function_call(self, func_call):
        function_name = func_call['function_call']["name"]
        tools = []
        print(f"function call: {func_call}")
        if AITool.find_function_spec(function_name):
            toolMessage = AITool.execute_function(func_call)
            # here we check to see if the tool call resulted in a new tool being added
            if isinstance(toolMessage, tuple):
                toolMessage, toolPack = toolMessage
                if toolPack:
                    for tool in toolPack:
                        tools.append(tool['name'])
                    print(f"Message {toolMessage} and we got a toolpack! {toolPack}")
                    # get the name of the first tool and use that to find the correct instance of VandBasicAPITool
                    vand_tool = VandBasicAPITool._find_function(tools[0])
                    AITool.define_function(spec=vand_tool.functions, func=vand_tool.execute_tool_call)
        else:
            raise ValueError(f"No function exists with name {function_name}.")
        print (toolMessage)
        return function_name, toolMessage, tools

    def gen(
        self,
        prompt: str,
        client: Union[Client, AsyncClient],
        function_name: str = None,
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
        functions: List[Any] = None,
        input_schema: Any = None,
        output_schema: Any = None,
    ):
        headers, data, user_message = self.prepare_request(
            prompt, function_name, system, params, False, functions, input_schema, output_schema
        )

        r = client.post(
            str(self.api_url),
            json=data,
            headers=headers,
            timeout=None,
        )
        r = r.json()

        try:
            if not output_schema:
                if r["choices"][0]["message"]["content"]:
                    content = r["choices"][0]["message"]["content"]

                    assistant_message = ChatMessage(
                        role=r["choices"][0]["message"]["role"],
                        content=str(content),
                        finish_reason=r["choices"][0]["finish_reason"],
                        prompt_length=r["usage"]["prompt_tokens"],
                        completion_length=r["usage"]["completion_tokens"],
                        total_length=r["usage"]["total_tokens"],
                    )
                    self.add_messages(user_message, assistant_message, save_messages)
                else:
                    self.add_message(user_message, save_messages)

                if r["choices"][0]["message"].get("function_call"):
                    func_call = {'function_call': r["choices"][0]["message"]["function_call"]}
                    #function_name=func_call["function_call"]["name"]
                    # check for local function
                    # if AITool.find_function_spec(function_name):
                    #     toolMessage = AITool.execute_function(func_call)
                    #     if isinstance(toolMessage, tuple):
                    #         toolMessage, toolPack = toolMessage
                    #     else:
                    #         toolMessage = toolMessage
                    #         toolPack = None

                    function_name, toolMessage, tools = self.process_function_call(func_call)

                    
                    # else:
                    #     toolMessage, toolPack = VandBasicAPITool.execute_function_call(func_call)
                    
                    # this is the function call message
                    assistant_message = ChatMessage(
                        role=r["choices"][0]["message"]["role"],
                        content=str(func_call),
                        finish_reason=r["choices"][0]["finish_reason"],
                        prompt_length=r["usage"]["prompt_tokens"],
                        completion_length=r["usage"]["completion_tokens"],
                        total_length=r["usage"]["total_tokens"],
                    )
                    self.add_message(assistant_message, save_messages)

                    # debugging 
                    '''
                    print(f"tool message: {toolMessage}")
                    if toolPack is not None:
                        tools = []
                        for tool in toolPack:
                            tools.append(tool['name'])
                        print(f"functions: {tools}")
                    '''
                    # end debugging

                    prompt = toolMessage
                    functions = tools
                    # prepare message and return results of function call to model
                    return self.gen(
                        prompt,
                        client=client,
                        function_name=function_name,
                        system=system,
                        save_messages=save_messages,
                        params=params,
                        functions=functions,
                        input_schema=input_schema,
                        output_schema=output_schema,
                    ) 
            else:
                content = r["choices"][0]["message"]["function_call"]["arguments"]
                content = orjson.loads(content)

            self.total_prompt_length += r["usage"]["prompt_tokens"]
            self.total_completion_length += r["usage"]["completion_tokens"]
            self.total_length += r["usage"]["total_tokens"]
        except KeyError:
            raise KeyError(f"No AI generation: {r}")

        return content


    def stream(
        self,
        prompt: str,
        client: Union[Client, AsyncClient],
        function_name: str = None,
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
        functions: List[Any] = None,
        input_schema: Any = None,
    ):
        # if functions:
        #     if functions[0] == "default":
        #         vand_id = functions[0]
        #         vand_tool = VandBasicAPITool.get_toolpack(vand_id)
        #         functions = vand_tool.functions
        #     print(f"functions passed: {functions[0]['name']}")

        if functions:
            function_specs= []
            for function in functions:
                if function.startswith("vand-") or function=="default":
                    vand_tool = VandBasicAPITool.get_toolpack(function)
                    AITool.define_function(spec=vand_tool.functions, func=vand_tool.execute_tool_call)
                    print(f"functions: {AITool.get_function_names()}")
                    function_specs += vand_tool.functions
                else:
                    # check for locally defined functions
                    if AITool.find_function_spec(function):
                        function_specs.append(AITool.find_function_spec(function))
            print(f"functions passed: {functions}")
            functions = function_specs


        headers, data, user_message = self.prepare_request(
            prompt, function_name, system, params, True, functions, input_schema
        )

        function_called = False

        with client.stream(
            "POST",
            str(self.api_url),
            json=data,
            headers=headers,
            timeout=None,
        ) as r:
            content = []
            func_call = {'function_call': 
                            {
                                'name': '',
                                'arguments': '',
                            }
                        }
            for chunk in r.iter_lines():
                if len(chunk) > 0:
                    #print(f"here's the chunk: {chunk}")  
                    if not chunk.startswith("data: "):
                        content.append(chunk)
                        # catch errors from OpenAI here, typically: {"error"
                        # e.g. service not available
                    else:
                        chunk = chunk[6:]
                        #chunk = chunk[6:]  # SSE JSON chunks are prepended with "data: "
                        if chunk != "[DONE]":                  
                            chunk_dict = orjson.loads(chunk)
                            funct = chunk_dict["choices"][0]["delta"].get("function_call")
                            if funct:
                                if "name" in funct:
                                    func_call['function_call']["name"] = funct["name"]
                                if "arguments" in funct:
                                    func_call['function_call']["arguments"] += funct["arguments"]
                            if chunk_dict["choices"][0]["finish_reason"] == "function_call":
                                print(f"Function call detected: {func_call}")
                                function_called = True
                            
                            delta = chunk_dict["choices"][0]["delta"].get("content")
                            if delta:
                                content.append(delta)                                
                                yield {"delta": delta, "response": "".join(content)}
                                  
        # streaming does not currently return token counts
        if content:
            assistant_message = ChatMessage(
                role="assistant",
                content="".join(content),
            )
            self.add_messages(user_message, assistant_message, save_messages)
        else:
            self.add_message(user_message, save_messages) 
  

        if function_called:
            # function_name = func_call['function_call']["name"]
            function_name, toolMessage, tools = self.process_function_call(func_call)
            # tools = []
            # if AITool.find_function_spec(function_name):
            #     toolMessage = AITool.execute_function(func_call)
            #     if isinstance(toolMessage, tuple):
            #         toolMessage, toolPack = toolMessage
            #         if toolPack:
            #             print(f"Message {toolMessage} and we got a toolpack! {toolPack}")
            #             AITool.define_function(spec=toolPack, func=vand_tool.execute_tool_call)
            #             for tool in toolPack:
            #                 tools.append(tool['name'])

            # toolMessage, toolPack = VandBasicAPITool.execute_function_call(func_call)
            # print(f"Response from function (toolMessage): {toolMessage} and toolPack: {toolPack[0]['name']}")

            for chunk_function in self.stream(toolMessage, client, function_name, functions=tools):
                delta_function = chunk_function["delta"]
                resonse_function = chunk_function["response"]
                yield {"delta": chunk_function["delta"], "response": chunk_function["response"]}

        #creating below so that function will return something but do NOT want an empty assistant message in the message log
        if not content:
            assistant_message = ChatMessage(
                role="function",
                name=function_name,
                content=toolMessage,
            )

        return assistant_message

    def gen_with_tools(
        self,
        prompt: str,
        tools: List[Any],
        client: Union[Client, AsyncClient],
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:

        # call 1: select tool and populate context
        tools_list = "\n".join(f"{i+1}: {f.__doc__}" for i, f in enumerate(tools))
        tool_prompt_format = tool_prompt.format(tools=tools_list)

        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(tools) + 1)}

        tool_idx = int(
            self.gen(
                prompt,
                client=client,
                system=tool_prompt_format,
                save_messages=False,
                params={
                    "temperature": 0.0,
                    "max_tokens": 1,
                    "logit_bias": logit_bias,
                },
            )
        )

        # if no tool is selected, do a standard generation instead.
        if tool_idx == 0:
            return {
                "response": self.gen(
                    prompt,
                    client=client,
                    system=system,
                    save_messages=save_messages,
                    params=params,
                ),
                "tool": None,
            }
        selected_tool = tools[tool_idx - 1]
        context_dict = selected_tool(prompt)
        if isinstance(context_dict, str):
            context_dict = {"context": context_dict}

        context_dict["tool"] = selected_tool.__name__

        # call 2: generate from the context
        new_system = f"{system or self.system}\n\nYou MUST use information from the context in your response."
        new_prompt = f"Context: {context_dict['context']}\n\nUser: {prompt}"

        context_dict["response"] = self.gen(
            new_prompt,
            client=client,
            system=new_system,
            save_messages=False,
            params=params,
        )

        # manually append the nonmodified user message + normal AI response
        user_message = ChatMessage(role="user", content=prompt)
        assistant_message = ChatMessage(
            role="assistant", content=context_dict["response"]
        )
        self.add_messages(user_message, assistant_message, save_messages)

        return context_dict

    async def gen_async(
        self,
        prompt: str,
        client: Union[Client, AsyncClient],
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
        input_schema: Any = None,
        output_schema: Any = None,
    ):
        headers, data, user_message = self.prepare_request(
            prompt, system, params, False, input_schema, output_schema
        )

        r = await client.post(
            str(self.api_url),
            json=data,
            headers=headers,
            timeout=None,
        )
        r = r.json()

        try:
            if not output_schema:
                content = r["choices"][0]["message"]["content"]
                assistant_message = ChatMessage(
                    role=r["choices"][0]["message"]["role"],
                    content=content,
                    finish_reason=r["choices"][0]["finish_reason"],
                    prompt_length=r["usage"]["prompt_tokens"],
                    completion_length=r["usage"]["completion_tokens"],
                    total_length=r["usage"]["total_tokens"],
                )
                self.add_messages(user_message, assistant_message, save_messages)
            else:
                content = r["choices"][0]["message"]["function_call"]["arguments"]
                content = orjson.loads(content)

            self.total_prompt_length += r["usage"]["prompt_tokens"]
            self.total_completion_length += r["usage"]["completion_tokens"]
            self.total_length += r["usage"]["total_tokens"]
        except KeyError:
            raise KeyError(f"No AI generation: {r}")

        return content

    async def stream_async(
        self,
        prompt: str,
        client: Union[Client, AsyncClient],
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
        input_schema: Any = None,
    ):
        headers, data, user_message = self.prepare_request(
            prompt, system, params, True, input_schema
        )

        async with client.stream(
            "POST",
            str(self.api_url),
            json=data,
            headers=headers,
            timeout=None,
        ) as r:
            content = []
            async for chunk in r.aiter_lines():
                if len(chunk) > 0:
                    chunk = chunk[6:]  # SSE JSON chunks are prepended with "data: "
                    if chunk != "[DONE]":
                        chunk_dict = orjson.loads(chunk)
                        delta = chunk_dict["choices"][0]["delta"].get("content")
                        if delta:
                            content.append(delta)
                            yield {"delta": delta, "response": "".join(content)}

        # streaming does not currently return token counts
        assistant_message = ChatMessage(
            role="assistant",
            content="".join(content),
        )

        self.add_messages(user_message, assistant_message, save_messages)

    async def gen_with_tools_async(
        self,
        prompt: str,
        tools: List[Any],
        client: Union[Client, AsyncClient],
        system: str = None,
        save_messages: bool = None,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:

        # call 1: select tool and populate context
        tools_list = "\n".join(f"{i+1}: {f.__doc__}" for i, f in enumerate(tools))
        tool_prompt_format = tool_prompt.format(tools=tools_list)

        logit_bias_weight = 100
        logit_bias = {str(k): logit_bias_weight for k in range(15, 15 + len(tools) + 1)}

        tool_idx = int(
            await self.gen_async(
                prompt,
                client=client,
                system=tool_prompt_format,
                save_messages=False,
                params={
                    "temperature": 0.0,
                    "max_tokens": 1,
                    "logit_bias": logit_bias,
                },
            )
        )

        # if no tool is selected, do a standard generation instead.
        if tool_idx == 0:
            return {
                "response": await self.gen_async(
                    prompt,
                    client=client,
                    system=system,
                    save_messages=save_messages,
                    params=params,
                ),
                "tool": None,
            }
        selected_tool = tools[tool_idx - 1]
        context_dict = await selected_tool(prompt)
        if isinstance(context_dict, str):
            context_dict = {"context": context_dict}

        context_dict["tool"] = selected_tool.__name__

        # call 2: generate from the context
        new_system = f"{system or self.system}\n\nYou MUST use information from the context in your response."
        new_prompt = f"Context: {context_dict['context']}\n\nUser: {prompt}"

        context_dict["response"] = await self.gen_async(
            new_prompt,
            client=client,
            system=new_system,
            save_messages=False,
            params=params,
        )

        # manually append the nonmodified user message + normal AI response
        user_message = ChatMessage(role="user", content=prompt)
        assistant_message = ChatMessage(
            role="assistant", content=context_dict["response"]
        )
        self.add_messages(user_message, assistant_message, save_messages)

        return context_dict


