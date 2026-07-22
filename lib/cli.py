import sys
from enum import Enum


class Appearance(Enum):
    OPTIONAL = "optional"
    MUST = "must"


class Order(Enum):
    LOCK = "lock"
    ANY = "any"


class PropertyType(Enum):
    ALL = "all" 
    FLAGS = "flags" 
    OPTIONS = "options"


class Option:
    def __init__(self, name, dtype, appearance, default, order):
        self.name = name
        self.type = dtype
        self.appearance = appearance
        self.default = default
        self.order = order


class Flag:
    def __init__(self, name, appearance, order):
        self.name = name
        self.appearance = appearance
        self.order = order


class Command:
    def __init__(self, name, min_property=0, max_property=None, property_type=PropertyType.ALL):
        self.name = name
        self.min_property = min_property
        self.max_property = max_property
        self.property_type = property_type

        self.options = []
        self.flags = []

        self.callback_function = None


    def option(self, name, dtype, appearance, value, order):
        if appearance == Appearance.OPTIONAL and value is None:
            raise Exception(f'Optional option "{name}" requires default value.')

        self.options.append(Option(name, dtype, appearance, value, order))
        return self

    def flag(self, name, appearance, order):
        self.flags.append(Flag(name, appearance, order))
        return self

    def callback(self, func):
        self.callback_function = func
        return self


class CLI:
    def __init__(self):
        self.commands = {}

    def register(self, name, min_property=0, max_property=None, property_type=PropertyType.ALL):
        cmd = Command(name, min_property, max_property, property_type)
        self.commands[name] = cmd
        return cmd

    def run(self):
        argv = sys.argv[1:]
        if len(argv) == 0:
            raise Exception("No command given.")

        command_name = argv[0]
        if command_name not in self.commands:
            raise Exception(f'Unknown command "{command_name}"')

        cmd = self.commands[command_name]
        tokens = argv[1:]
        result = {}

        for opt in cmd.options:
            result[opt.name] = opt.default

        for flag in cmd.flags:
            result[flag.name] = False

        flag_count = 0
        option_count = 0
        i = 0

        while i < len(tokens):
            token = tokens[i]
            matched = False

            for flag in cmd.flags:
                if token == flag.name:
                    result[flag.name] = True
                    flag_count += 1
                    matched = True
                    break

            if matched:
                i += 1
                continue

            if token.startswith("-"):
                key = token[1:]
                found = None
                for opt in cmd.options:
                    if opt.name == key:
                        found = opt
                        break

                if found is None:
                    raise Exception(f"Unknown option {token}")

                if i + 1 >= len(tokens):
                    raise Exception(f"{token} requires a value.")

                raw = tokens[i + 1]
                try:
                    value = found.type(raw)
                except Exception:
                    raise Exception(f"{token} expects {found.type.__name__}")

                result[found.name] = value
                option_count += 1
                i += 2
                continue
            raise Exception(f"Unexpected token '{token}'")

        for opt in cmd.options:
            if (opt.appearance == Appearance.MUST and result[opt.name] is None):
                raise Exception(f'Missing required option "-{opt.name}"')

        if cmd.property_type == PropertyType.FLAGS:
            property_count = flag_count
        elif cmd.property_type == PropertyType.OPTIONS:
            property_count = option_count
        else:
            property_count = flag_count + option_count

        if property_count < cmd.min_property:
            raise Exception(f'"{cmd.name}" requires at least ' f'{cmd.min_property} propert{"y" if cmd.min_property == 1 else "ies"}.')

        if (cmd.max_property is not None and property_count > cmd.max_property):
            raise Exception(f'"{cmd.name}" accepts at most ' f'{cmd.max_property} propert{"y" if cmd.max_property == 1 else "ies"}.')

        if cmd.callback_function:
            cmd.callback_function(result)