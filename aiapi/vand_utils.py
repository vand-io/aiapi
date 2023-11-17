'''
Utility to make it easy to use use OpenAI function calls
'''
import orjson
import requests
from typing import List, Optional, Tuple, Union, Self
from dataclasses import dataclass, field



@dataclass
class VandBasicAPITool:
    """
    Simplified data from API specs

    Attributes:
        servers: The servers for the API.
        description: The description of the API / application.
        endpoints: The endpoints in the API (method & path).
        functions: The OpenAI function specs for a function_call
    """
    description: str
    servers: List[dict]
    endpoints: List[Tuple[str, str, str, dict]] 
    functions: List[dict] = field(default_factory=list)

    instances = []

    def __post_init__(self):
        self.instances.append(self)

    def _find_endpoint(self, operation_id: str) -> Optional[Tuple[str, str, str, dict]]:
        for endpoint in self.endpoints:
            if endpoint[1] == operation_id:
                return endpoint
        return None

    def get_functions_by_names(self, names: Union[str, List[str]]) -> List[dict]:
        if isinstance(names, str):
            names = [names]  # Convert single name to a list
        result = []
        for function in self.functions:
            if function.get("name") in names:
                result.append(function)
        return result

    @classmethod
    def vand(cls):
        vandToolPack = cls.get_toolpack("default")
        return vandToolPack

    @classmethod
    def _find_function(cls, functionName: str) -> Self:
        for instance in cls.instances:
            for function in instance.functions:
                if function['name'] == functionName:
                    return instance
        return None

    @classmethod
    def get_toolpack(cls, toolpack_id: str) -> Self:
        """Instantiate VandBasicAPITool from an ID."""
        #TODO: Catch when a bad ID is passed
        base_url = "https://api.vand.io/api/v1"
        url = f"{base_url}/getToolPack/{toolpack_id}"
        try:
            response = requests.get(url).json()
        except (orjson.JSONDecodeError, requests.RequestException) as e:
            raise e  # Reraise the exception if there's an error

        if len(response) == 0:
            print(f"No tool found for {toolpack_id}")
            return None

        return cls(**response)

    @classmethod
    def execute_function_call(cls, message):
        functionName = message["function_call"]["name"]
        args = orjson.loads(message["function_call"].get("arguments", {}))
        functions = None # normal functions will not return additional function calls
        # default function for chat complettion calls.

        toolPack = cls._find_function(functionName)
        if toolPack is None:
            # Handle Vand.io tools being called before loaded.
            
            if functionName in ["getToolPack", "getLucky"]: #looking for default tools that may not be loaded yet
                new_instance = cls.vand()
                # confirm we now have the required function otherwise exit
                if new_instance and new_instance._find_function(functionName):
                    return new_instance.execute_function_call(message)

            result_message = f"No function found with the name {functionName}. Are you sure that's the right function?"
            return result_message, functions

        base_url = toolPack.servers[0]["url"]
        endpoint = toolPack._find_endpoint(functionName)
        if endpoint:
            method, path = endpoint[0].split()
            params = endpoint[3].get('parameters', [])
            props = endpoint[3].get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {}).get('properties', {})
        else:
            result_message = f"No endpoint found for the function {functionName}."
            return result_message, functions

        # Replace path parameters in the path
        for param in params:
            if param['in'] == 'path' and param['name'] in args:
                path = path.replace('{' + param['name'] + '}', str(args[param['name']]))
        
        query_params = {param['name']: args[param['name']] for param in params if param['in'] == 'query' and param['name'] in args}
        
        if props == {}:
            body_params = None
        else:
            body_params = {param: args[param] for param in props if param in args}
        
        headers = {}
        api_response = requests.request(method, base_url + path, headers=headers, params=query_params, json=body_params)
            
        if api_response.status_code != 200:
            result_message = (
                f"{api_response.status_code}: {api_response.reason}"
                + f"\nFor {functionName} "
                + f"Called with params: {query_params}"
            )
        else:
            try:
                result_message = api_response.text
            except Exception: 
                result_message = api_response.text

        # if the function call was to vand.io it includes new functions; need to add them to our toolPack instances.
        if 'vand.io' in api_response.url.lower():    
            if functionName in ["getToolPack" , "getLucky"]: #looking for default tools
                result_json = api_response.json()
                result_message = result_json.pop('message', "Consider the tools/functions available and choose the best one to use.")
                functions = result_json.get('functions', [])
                if functions: 
                    instance =  cls(**result_json)
            if functionName in ["findToolPacks"]:
                result_message = f"Here is a list of tools you can select from.  You should choose the best tool from these options (not just the first one) and call the getToolPack function with the id. {response.json()}"
        if not functions:
            # if default tool has been loaded return it as available tool; otherwise tool was called directly and default tool not being used.
            if cls._find_function("getLucky"):
                functions = cls._find_function("getLucky").functions
        return result_message, functions

    def execute_tool_call(self, functionName, **args):
        functions = None # normal functions will not return additional function calls
        # default function for chat complettion calls.
        base_url = self.servers[0]["url"]
        endpoint = self._find_endpoint(functionName)
     
        if endpoint:
            method, path = endpoint[0].split()
            params = endpoint[3].get('parameters', [])
            props = endpoint[3].get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema', {}).get('properties', {})
        else:
            result_message = f"No endpoint found for the function {functionName}."
            return result_message, functions

        # Replace path parameters in the path
        for param in params:
            if param['in'] == 'path' and param['name'] in args:
                path = path.replace('{' + param['name'] + '}', str(args[param['name']]))
        
        query_params = {param['name']: args[param['name']] for param in params if param['in'] == 'query' and param['name'] in args}
        
        if props == {}:
            body_params = None
        else:
            body_params = {param: args[param] for param in props if param in args}
        
        headers = {}
        api_response = requests.request(method, base_url + path, headers=headers, params=query_params, json=body_params)
            
        if api_response.status_code != 200:
            result_message = (
                f"{api_response.status_code}: {api_response.reason}"
                + f"\nFor {functionName} "
                + f"Called with params: {query_params}"
            )
        else:
            try:
                result_message = api_response.text
            except Exception: 
                result_message = api_response.text

        # if the function call was to vand.io it may include new tools; need to add them to our toolPack instances.
        if 'vand.io' in api_response.url.lower():    
            if functionName in ["getToolPack" , "getLucky"]: #looking for default tools
                result_json = api_response.json()
                result_message = result_json.pop('message', "Consider the tools/functions available and choose the best one to use.")
                functions = result_json.get('functions', [])
                if functions: 
                    instance =  self.__class__(**result_json)
            if functionName in ["findToolPacks"]:
                result_message = f"Here is a list of tools you can select from.  You should choose the best tool from these options (not just the first one) and call the getToolPack function with the id. {response.json()}"
        if not functions:
            # if default tool has been loaded return it as available tool; otherwise tool was called directly and default tool not being used.
            if self.__class__._find_function("getLucky"):
                functions = self.__class__._find_function("getLucky").functions
        return result_message, functions

