import sys
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union


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
    def __init__(
        self,
        name: str,
        dtype: Type[Any],
        appearance: Appearance,
        default: Optional[Any],
        order: Order,
    ) -> None:
        self.name: str = name
        self.type: Type[Any] = dtype
        self.appearance: Appearance = appearance
        self.default: Optional[Any] = default
        self.order: Order = order
        self.locked: bool = False


class Flag:
    def __init__(self, name: str, appearance: Appearance, order: Order) -> None:
        self.name: str = name
        self.appearance: Appearance = appearance
        self.order: Order = order
        self.locked: bool = False


LockedItem = Union[Option, Flag]


# --------------------------------------------------------------------
# Standalone helpers used inside `.locked([...])`.
# These only describe the *shape* of each item (name / type / value) —
# appearance and order for the whole group are set once, as the 2nd
# and 3rd arguments to `.locked()` itself, not per item.
#
# `option()` strips a leading "-" so "-x" and "x" both resolve to the
# same internal name used by the parser (options are matched without
# their dash, e.g. "-x" -> key "x").
# `flag()` keeps the name as-is (e.g. "--test") since flags are matched
# against the raw token verbatim.
# --------------------------------------------------------------------
def option(name: str, dtype: Type[Any], value: Optional[Any] = None) -> Option:
    clean_name = name.lstrip("-")
    return Option(clean_name, dtype, Appearance.OPTIONAL, value, Order.ANY)


def flag(name: str) -> Flag:
    return Flag(name, Appearance.OPTIONAL, Order.ANY)


class Command:
    def __init__(
        self,
        name: str,
        min_property: int = 0,
        max_property: Optional[int] = None,
        property_type: PropertyType = PropertyType.ALL,
    ) -> None:
        self.name: str = name
        self.min_property: int = min_property
        self.max_property: Optional[int] = max_property
        self.property_type: PropertyType = property_type

        self.options: List[Option] = []
        self.flags: List[Flag] = []
        self.locked_group: List[LockedItem] = []
        self.locked_appearance: Appearance = Appearance.OPTIONAL
        self.locked_order: Order = Order.ANY

        self.callback_function: Optional[Callable[[Dict[str, Any]], None]] = None

    def option(
        self,
        name: str,
        dtype: Type[Any],
        appearance: Appearance,
        value: Optional[Any],
        order: Order,
    ) -> "Command":
        if appearance == Appearance.OPTIONAL and value is None:
            raise Exception(f'Optional option "{name}" requires default value.')

        self.options.append(Option(name, dtype, appearance, value, order))
        return self

    def flag(self, name: str, appearance: Appearance, order: Order) -> "Command":
        self.flags.append(Flag(name, appearance, order))
        return self

    def locked(
        self,
        items: List[LockedItem],
        appearance: Appearance = Appearance.MUST,
        order: Order = Order.LOCK,
    ) -> "Command":
        """
        Register a mutually-exclusive group of flags/options built with
        the standalone option()/flag() helpers.

        appearance:
          - Appearance.MUST     exactly one item from the group must be used.
          - Appearance.OPTIONAL the group may be used zero or one times.
          (Either way, using MORE than one item from the group is always
          an error — that's what makes it a "locked"/exclusive group.)

        order:
          - Order.LOCK  whichever item is used MUST be the first argument
                        after the command name (index 3, using <file>=1,
                        <command>=2, <args..>=3+). Using it anywhere else
                        is an error.
          - Order.ANY   the item may appear anywhere in the arguments.

        Items NOT in the locked group behave exactly as before and can
        appear anywhere (subject to their own appearance/order rules).
        """
        self.locked_group = list(items)
        self.locked_appearance = appearance
        self.locked_order = order
        for item in self.locked_group:
            item.locked = True
            if isinstance(item, Option):
                self.options.append(item)
            elif isinstance(item, Flag):
                self.flags.append(item)
            else:
                raise Exception(
                    "locked() items must be built with the option()/flag() helper functions."
                )
        return self

    def callback(self, func: Callable[[Dict[str, Any]], None]) -> "Command":
        self.callback_function = func
        return self


class CLI:
    def __init__(self) -> None:
        self.commands: Dict[str, Command] = {}

    def register(
        self,
        name: str,
        min_property: int = 0,
        max_property: Optional[int] = None,
        property_type: PropertyType = PropertyType.ALL,
    ) -> Command:
        cmd = Command(name, min_property, max_property, property_type)
        self.commands[name] = cmd
        return cmd

    def run(self) -> None:
        argv: List[str] = sys.argv[1:]
        if len(argv) == 0:
            raise Exception("No command given.")

        command_name = argv[0]
        if command_name not in self.commands:
            raise Exception(f'Unknown command "{command_name}"')

        cmd = self.commands[command_name]
        tokens: List[str] = argv[1:]
        result: Dict[str, Any] = {}

        for opt in cmd.options:
            result[opt.name] = opt.default

        for fl in cmd.flags:
            result[fl.name] = False

        # Map the literal token a user would type -> the locked item.
        # Options are keyed by "-name" (dash + stripped name); flags are
        # keyed by their raw name (already includes dashes).
        locked_token_map: Dict[str, LockedItem] = {}
        for item in cmd.locked_group:
            if isinstance(item, Option):
                locked_token_map["-" + item.name] = item
            else:
                locked_token_map[item.name] = item

        locked_order = cmd.locked_order
        locked_appearance = cmd.locked_appearance
        locked_used_token: Optional[str] = None

        flag_count = 0
        option_count = 0
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token in locked_token_map:
                # Only one item from the locked group may ever be used.
                if locked_used_token is not None:
                    raise Exception(
                        f'"{token}" conflicts with "{locked_used_token}" — only one '
                        f'property from this locked group may be used at a time.'
                    )
                # Order.LOCK pins that single usage to the first argument slot.
                if locked_order == Order.LOCK and i != 0:
                    raise Exception(
                        f'"{token}" is a locked property and can only appear at index 3 '
                        f'(the first argument) — found instead at index {i + 3}.'
                    )
                locked_used_token = token

            matched = False
            for fl in cmd.flags:
                if token == fl.name:
                    result[fl.name] = True
                    flag_count += 1
                    matched = True
                    break

            if matched:
                i += 1
                continue

            if token.startswith("-"):
                key = token[1:]
                found: Optional[Option] = None
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

        if (locked_token_map and locked_appearance == Appearance.MUST
                and locked_used_token is None):
            where = " as the first argument (index 3)" if locked_order == Order.LOCK else ""
            raise Exception(
                f'"{cmd.name}" requires one of the locked properties'
                f'{where}: {", ".join(sorted(locked_token_map.keys()))}.'
            )

        for opt in cmd.options:
            if (opt.appearance == Appearance.MUST and result[opt.name] is None):
                raise Exception(f'Missing required option "-{opt.name}"')

        property_count: int
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