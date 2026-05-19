"""Symbol table and scope management for EzLang."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set
from enum import Enum


class SymbolKind(Enum):
    """Kind of symbol."""
    VARIABLE = "variable"
    CONSTANT = "constant"
    STATIC = "static"
    FUNCTION = "function"
    STRUCT = "struct"
    TYPE_ALIAS = "type_alias"
    PARAMETER = "parameter"
    EXTERN = "extern"


@dataclass
class Symbol:
    """Represents a symbol in the symbol table."""
    name: str
    kind: SymbolKind
    type_: Any = None  # TypeNode
    mutable: bool = True
    exported: bool = False
    line: int = 0
    column: int = 0


class Scope:
    """Represents a lexical scope."""

    def __init__(self, parent: Optional['Scope'] = None, name: str = ""):
        self.parent = parent
        self.name = name
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []
        if parent:
            parent.children.append(self)

    def define(self, symbol: Symbol) -> bool:
        """Define a symbol in this scope. Returns False if already defined."""
        if symbol.name in self.symbols:
            return False
        self.symbols[symbol.name] = symbol
        return True

    def lookup(self, name: str, local_only: bool = False) -> Optional[Symbol]:
        """Look up a symbol in this scope and parent scopes."""
        if name in self.symbols:
            return self.symbols[name]
        if not local_only and self.parent:
            return self.parent.lookup(name)
        return None

    def get_all_names(self) -> Set[str]:
        """Get all symbol names in this scope and children."""
        names = set(self.symbols.keys())
        for child in self.children:
            names.update(child.get_all_names())
        return names


class SymbolTable:
    """Symbol table managing nested scopes."""

    def __init__(self):
        self.global_scope = Scope(name="global")
        self.current_scope = self.global_scope
        self.scope_stack: List[Scope] = [self.global_scope]

    def push_scope(self, name: str = "") -> Scope:
        """Push a new scope onto the stack."""
        new_scope = Scope(parent=self.current_scope, name=name)
        self.scope_stack.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def pop_scope(self) -> Optional[Scope]:
        """Pop the current scope from the stack."""
        if len(self.scope_stack) <= 1:
            return None
        scope = self.scope_stack.pop()
        self.current_scope = self.scope_stack[-1]
        return scope

    def define(self, symbol: Symbol) -> bool:
        """Define a symbol in the current scope."""
        return self.current_scope.define(symbol)

    def lookup(self, name: str, local_only: bool = False) -> Optional[Symbol]:
        """Look up a symbol in the current scope chain."""
        return self.current_scope.lookup(name, local_only)

    def lookup_global(self, name: str) -> Optional[Symbol]:
        """Look up a symbol only in the global scope."""
        return self.global_scope.lookup(name, local_only=True)

    @property
    def depth(self) -> int:
        """Get current scope depth."""
        return len(self.scope_stack)
