"""Semantic analysis tests for EzLang."""

import pytest


class TestSymbolTable:
    """Test symbol table functionality."""

    def test_basic_symbol(self):
        """Test basic symbol creation."""
        from semantic.symbols import Symbol, SymbolKind, Scope

        scope = Scope()
        symbol = Symbol(
            name="x",
            kind=SymbolKind.VARIABLE,
            mutable=True,
            line=1,
            column=1
        )
        assert scope.define(symbol)
        assert scope.lookup("x") is symbol

    def test_redefine_symbol(self):
        """Test that redefining a symbol fails."""
        from semantic.symbols import Symbol, SymbolKind, Scope

        scope = Scope()
        symbol1 = Symbol("x", SymbolKind.VARIABLE, line=1, column=1)
        symbol2 = Symbol("x", SymbolKind.VARIABLE, line=2, column=1)

        assert scope.define(symbol1)
        assert not scope.define(symbol2)

    def test_nested_scope(self):
        """Test nested scope lookup."""
        from semantic.symbols import Symbol, SymbolKind, Scope

        global_scope = Scope()
        local_scope = Scope(parent=global_scope)

        global_symbol = Symbol("x", SymbolKind.VARIABLE, line=1, column=1)
        local_symbol = Symbol("y", SymbolKind.VARIABLE, line=2, column=1)

        global_scope.define(global_symbol)
        local_scope.define(local_symbol)

        assert local_scope.lookup("x") is global_symbol
        assert local_scope.lookup("y") is local_symbol
        assert global_scope.lookup("y", local_only=True) is None


class TestTypeChecker:
    """Test type checker."""

    def test_type_equality(self):
        """Test type equality checks."""
        from semantic.type_checker import TypeChecker
        from ast import BaseType, OptionalType, ArrayType

        checker = TypeChecker()

        t1 = BaseType(name='I32')
        t2 = BaseType(name='I32')
        t3 = BaseType(name='I64')

        assert checker._types_equal(t1, t2)
        assert not checker._types_equal(t1, t3)

    def test_optional_type(self):
        """Test optional type handling."""
        from semantic.type_checker import TypeChecker
        from ast import BaseType, OptionalType

        checker = TypeChecker()

        t_optional = OptionalType(base=BaseType(name='I32'))
        t_base = BaseType(name='I32')

        assert checker._is_assignable_to(t_base, t_optional)
        assert not checker._is_assignable_to(t_optional, t_base)

    def test_literal_type_inference(self):
        """Test literal type inference."""
        from semantic.type_checker import TypeChecker
        from ast import LiteralExpr, BaseType

        checker = TypeChecker()

        int_lit = LiteralExpr(value=42, type_name='integer')
        float_lit = LiteralExpr(value=3.14, type_name='float')
        str_lit = LiteralExpr(value="hello", type_name='string')
        bool_lit = LiteralExpr(value=True, type_name='bool')

        assert checker._infer_literal_type(int_lit).name == 'I32'
        assert checker._infer_literal_type(float_lit).name == 'F64'
        assert checker._infer_literal_type(str_lit).name == 'Str'
        assert checker._infer_literal_type(bool_lit).name == 'Bool'
