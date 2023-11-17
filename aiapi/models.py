import datetime
from uuid import uuid4, UUID

from pydantic import BaseModel, SecretStr, HttpUrl, Field
from typing import List, Dict, Union, Optional, Set, Any
import orjson


def orjson_dumps(v, *, default, **kwargs):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default, **kwargs).decode()


def now_tz():
    # Need datetime w/ timezone for cleanliness
    # https://stackoverflow.com/a/24666683
    return datetime.datetime.now(datetime.timezone.utc)


class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    functions: Optional[list] = None #function_call handled by role & content; functions are what user presents to AI
    received_at: datetime.datetime = Field(default_factory=now_tz)
    finish_reason: Optional[str] = None
    prompt_length: Optional[int] = None
    completion_length: Optional[int] = None
    total_length: Optional[int] = None

    def __str__(self) -> str:
        return str(self.model_dump(exclude_none=True))


class ChatSession(BaseModel):
    id: Union[str, UUID] = Field(default_factory=uuid4)
    created_at: datetime.datetime = Field(default_factory=now_tz)
    auth: Dict[str, SecretStr]
    api_url: HttpUrl
    model: str
    system: str
    params: Dict[str, Any] = {}
    messages: List[ChatMessage] = []
    input_fields: Set[str] = {}
    recent_messages: Optional[int] = None
    save_messages: Optional[bool] = True
    total_prompt_length: int = 0
    total_completion_length: int = 0
    total_length: int = 0
    title: Optional[str] = None

    def __str__(self) -> str:
        sess_start_str = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        last_message_str = self.messages[-1].received_at.strftime("%Y-%m-%d %H:%M:%S")
        return f"""Chat session started at {sess_start_str}:
        - {len(self.messages):,} Messages
        - Last message sent at {last_message_str}"""

    def format_input_messages(
        self, system_message: ChatMessage, user_message: ChatMessage
    ) -> list:
        recent_messages = (
            self.messages[-self.recent_messages :]
            if self.recent_messages
            else self.messages
        )
        return (
            [system_message.model_dump(include=self.input_fields, exclude_none=True)]
            + [
                m.model_dump(include=self.input_fields, exclude_none=True)
                for m in recent_messages
            ]
            + [user_message.model_dump(include=self.input_fields, exclude_none=True)]
        )

    def add_messages(
        self,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        save_messages: bool = None,
    ) -> None:

        # if save_messages is explicitly defined, always use that choice
        # instead of the default
        to_save = isinstance(save_messages, bool)

        if to_save:
            if save_messages:
                self.messages.append(user_message)
                self.messages.append(assistant_message)
        elif self.save_messages:
            self.messages.append(user_message)
            self.messages.append(assistant_message)

    def add_message(
        self,
        message: ChatMessage,
        save_messages: bool = None,
    ) -> None:

        # if save_messages is explicitly defined, always use that choice
        # instead of the default
        to_save = isinstance(save_messages, bool)

        if to_save:
            if save_messages:
                self.messages.append(message)

        elif self.save_messages:
            self.messages.append(message)

class AITool:
    instances = set() 
    def __init__(self, spec, func):
        # if any(instance.name == name for instance in self.__class__.instances):
        #    raise ValueError(f"An instance with the name '{name}' already exists")
        # Remove any existing instance with the same name; this will overwrite in the case of duplicate names
        self.__class__.instances = {instance for instance in self.__class__.instances if instance.name != spec['name']}
        self.name = spec['name']
        self.func = func
        self.spec = spec
        self.__class__.instances.add(self) 

    @classmethod
    def define_function(
        cls,
        spec: dict,
        func: callable,
    ):
        if isinstance(spec, dict):
            return cls(spec, func)
        elif isinstance(spec, list):
            instances = []
            for spec_item in spec:
                # Process each spec dictionary in the list
                instance = cls(spec_item, func)
                instances.append(instance)
            return instances
        else:
            raise ValueError("Invalid spec argument")

        return cls(spec, func)

    @classmethod
    def get_function_names(cls):
        functions = []
        for instance in cls.instances:
            functions.append(instance.name)
        return functions

    @classmethod
    def find_function_spec(cls, function_name):
       for instance in cls.instances:
           if instance.name == function_name:
               return instance.spec
               break # Stop after finding the first match

    @classmethod
    def execute_function(cls, function_call):
        function_name = function_call['function_call']['name']
        arguments = function_call['function_call'].get('arguments')
        if arguments is not None and arguments != "":
            arguments = orjson.loads(arguments)
        else:
            arguments = {}
        for instance in cls.instances:
           if instance.name == function_name:
                # catch instances from Vand's VandBasicAPITool
                if hasattr(instance.func, '__self__') and instance.func.__self__.__class__.__name__ == "VandBasicAPITool":
                    return instance.func(function_name, **arguments)
                else:
                    return instance.func(**arguments)
                    break # Stop after finding the first match

