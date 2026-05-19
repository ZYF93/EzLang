"""Type checker for EzLang."""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, Set, Tuple
from ast import (
    ASTNode, Module, TypeNode, BaseType, OptionalType, UnionType,
    ArrayType, VecType, GenericType, FunctionType, TypeofType,
    Expr, LiteralExpr, IdentifierExpr, UnaryExpr, BinaryExpr,
    ConditionalExpr, MemberAccessExpr, CallExpr, IndexExpr,
    TypeAssertionExpr, OptionalUnwrapExpr, PipelineExpr,
    StructLiteralExpr, ArrayLiteralExpr, VecLiteralExpr,
    FunctionLiteralExpr, Param, BlockExpr, FlowExpr,
    MatchExpr, MatchClause, CatchExpr, LoopExpr, IfLikeExpr,
    Stmt, VariableDeclStmt, StructDeclStmt, StructField,
    StructMethod, StructSpread, TypeAliasDeclStmt, TypeShape,
    TypeShapeField, TypeShapeSpread, FunctionDeclStmt,
    ImportDeclStmt, ExportDeclStmt, ExternDeclStmt,
    DeclareDeclStmt, ExprStmt, AssignmentStmt, ReturnStmt,
    BreakStmt, ContinueStmt, ThrowStmt
)
from .symbols import SymbolTable, Symbol, SymbolKind


@dataclass
class TypeError:
    """Represents a type error."""
    message: str
    line: int
    column: int


class TypeChecker:
    """Performs type checking on EzLang AST."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.symbols = SymbolTable()
        self.errors: List[TypeError] = []
        self._current_function_return_type: Optional[TypeNode] = None

    def check(self, ast: Module) -> List[TypeError]:
        """Check the entire module for type errors."""
        self.errors = []
        self._check_module(ast)
        return self.errors

    def error(self, message: str, node: Optional[ASTNode] = None):
        """Report a type error."""
        line = node.line if node else 0
        column = node.column if node else 0
        self.errors.append(TypeError(message, line, column))
        if self.verbose:
            print(f"Type error at {line}:{column}: {message}")

    # === Type operations ===

    def _types_equal(self, t1: TypeNode, t2: TypeNode) -> bool:
        """Check if two types are equal."""
        if type(t1) != type(t2):
            return False
        if isinstance(t1, BaseType):
            return t1.name == t2.name
        if isinstance(t1, OptionalType):
            return self._types_equal(t1.base, t2.base)
        if isinstance(t1, UnionType):
            if len(t1.types) != len(t2.types):
                return False
            for a, b in zip(t1.types, t2.types):
                if not self._types_equal(a, b):
                    return False
            return True
        if isinstance(t1, ArrayType):
            return self._types_equal(t1.element, t2.element)
        if isinstance(t1, VecType):
            return t1.size == t2.size and self._types_equal(t1.element, t2.element)
        if isinstance(t1, FunctionType):
            if len(t1.params) != len(t2.params):
                return False
            for p1, p2 in zip(t1.params, t2.params):
                if not self._types_equal(p1.type_, p2.type_):
                    return False
            return self._types_equal(t1.return_type, t2.return_type)
        if isinstance(t1, GenericType):
            if t1.base.name != t2.base.name or len(t1.args) != len(t2.args):
                return False
            for a1, a2 in zip(t1.args, t2.args):
                if not self._types_equal(a1, a2):
                    return False
            return True
        return False

    def _is_assignable_to(self, from_type: TypeNode, to_type: TypeNode) -> bool:
        """Check if from_type is assignable to to_type."""
        if self._types_equal(from_type, to_type):
            return True
        # Optional can accept non-optional
        if isinstance(to_type, OptionalType) and not isinstance(from_type, OptionalType):
            return self._is_assignable_to(from_type, to_type.base)
        # Union membership
        if isinstance(to_type, UnionType):
            for t in to_type.types:
                if self._is_assignable_to(from_type, t):
                    return True
        return False

    def _infer_literal_type(self, expr: LiteralExpr) -> TypeNode:
        """Infer the type of a literal expression."""
        if expr.type_name == 'integer':
            return BaseType(name='I32')
        if expr.type_name == 'float':
            return BaseType(name='F64')
        if expr.type_name == 'string':
            return BaseType(name='Str')
        if expr.type_name == 'bool':
            return BaseType(name='Bool')
        return BaseType(name='Void')

    # === Node visiting ===

    def _check_module(self, module: Module):
        """Check a module."""
        for stmt in module.statements:
            self._check_statement(stmt)

    def _check_statement(self, stmt: Stmt) -> Optional[TypeNode]:
        """Check a statement and return its type if it produces a value."""
        if isinstance(stmt, VariableDeclStmt):
            return self._check_variable_decl(stmt)
        if isinstance(stmt, StructDeclStmt):
            return self._check_struct_decl(stmt)
        if isinstance(stmt, TypeAliasDeclStmt):
            return self._check_type_alias_decl(stmt)
        if isinstance(stmt, FunctionDeclStmt):
            return self._check_function_decl(stmt)
        if isinstance(stmt, ImportDeclStmt):
            return self._check_import_decl(stmt)
        if isinstance(stmt, ExportDeclStmt):
            return self._check_export_decl(stmt)
        if isinstance(stmt, ExternDeclStmt):
            return self._check_extern_decl(stmt)
        if isinstance(stmt, DeclareDeclStmt):
            return self._check_declare_decl(stmt)
        if isinstance(stmt, ExprStmt):
            return self._check_expr_stmt(stmt)
        if isinstance(stmt, AssignmentStmt):
            return self._check_assignment_stmt(stmt)
        if isinstance(stmt, ReturnStmt):
            return self._check_return_stmt(stmt)
        if isinstance(stmt, BreakStmt):
            return BaseType(name='Void')
        if isinstance(stmt, ContinueStmt):
            return BaseType(name='Void')
        if isinstance(stmt, ThrowStmt):
            return self._check_throw_stmt(stmt)
        return BaseType(name='Void')

    def _check_variable_decl(self, stmt: VariableDeclStmt) -> TypeNode:
        """Check a variable declaration."""
        init_type = self._check_expression(stmt.initializer)

        if stmt.type_:
            if not self._is_assignable_to(init_type, stmt.type_):
                self.error(
                    f"Type mismatch: cannot assign {self._type_name(init_type)} "
                    f"to {self._type_name(stmt.type_)}",
                    stmt
                )
            var_type = stmt.type_
        else:
            var_type = init_type

        # Register symbol
        kind_map = {
            'let': SymbolKind.VARIABLE,
            'const': SymbolKind.CONSTANT,
            'static': SymbolKind.STATIC
        }
        symbol = Symbol(
            name=stmt.name,
            kind=kind_map.get(stmt.kind, SymbolKind.VARIABLE),
            type_=var_type,
            mutable=(stmt.kind == 'let'),
            line=stmt.line,
            column=stmt.column
        )
        if not self.symbols.define(symbol):
            self.error(f"Redefinition of variable '{stmt.name}'", stmt)

        return var_type

    def _check_struct_decl(self, stmt: StructDeclStmt) -> TypeNode:
        """Check a struct declaration."""
        symbol = Symbol(
            name=stmt.name,
            kind=SymbolKind.STRUCT,
            mutable=False,
            line=stmt.line,
            column=stmt.column
        )
        if not self.symbols.define(symbol):
            self.error(f"Redefinition of struct '{stmt.name}'", stmt)

        self.symbols.push_scope(f"struct_{stmt.name}")
        for member in stmt.members:
            if isinstance(member, StructField):
                if member.default_value:
                    self._check_expression(member.default_value)
            elif isinstance(member, StructMethod):
                self._check_expression(member.function)
            # StructSpread is handled at instantiation
        self.symbols.pop_scope()

        return BaseType(name=stmt.name)

    def _check_type_alias_decl(self, stmt: TypeAliasDeclStmt) -> TypeNode:
        """Check a type alias declaration."""
        symbol = Symbol(
            name=stmt.name,
            kind=SymbolKind.TYPE_ALIAS,
            mutable=False,
            line=stmt.line,
            column=stmt.column
        )
        if not self.symbols.define(symbol):
            self.error(f"Redefinition of type '{stmt.name}'", stmt)
        return BaseType(name=stmt.name)

    def _check_function_decl(self, stmt: FunctionDeclStmt) -> TypeNode:
        """Check a function declaration."""
        func_type = self._check_expression(stmt.function)

        symbol = Symbol(
            name=stmt.name,
            kind=SymbolKind.FUNCTION,
            type_=func_type,
            mutable=False,
            line=stmt.line,
            column=stmt.column
        )
        if not self.symbols.define(symbol):
            self.error(f"Redefinition of function '{stmt.name}'", stmt)

        return func_type

    def _check_import_decl(self, stmt: ImportDeclStmt) -> TypeNode:
        """Check an import declaration."""
        # Imports are resolved separately; just register symbols
        for orig, alias in stmt.imports.items():
            symbol = Symbol(
                name=alias,
                kind=SymbolKind.VARIABLE,
                mutable=False,
                exported=False,
                line=stmt.line,
                column=stmt.column
            )
            self.symbols.define(symbol)
        return BaseType(name='Void')

    def _check_export_decl(self, stmt: ExportDeclStmt) -> TypeNode:
        """Check an export declaration."""
        inner_type = self._check_statement(stmt.declaration)
        if hasattr(stmt.declaration, 'name'):
            symbol = self.symbols.lookup(stmt.declaration.name, local_only=True)
            if symbol:
                symbol.exported = True
        return inner_type

    def _check_extern_decl(self, stmt: ExternDeclStmt) -> TypeNode:
        """Check an extern declaration."""
        # Extern paths are resolved at link time
        return BaseType(name='Void')

    def _check_declare_decl(self, stmt: DeclareDeclStmt) -> TypeNode:
        """Check a declare declaration."""
        kind_map = {
            'let': SymbolKind.VARIABLE,
            'const': SymbolKind.CONSTANT,
            'static': SymbolKind.STATIC
        }
        symbol = Symbol(
            name=stmt.name,
            kind=kind_map.get(stmt.kind, SymbolKind.VARIABLE),
            type_=stmt.type_,
            mutable=(stmt.kind == 'let'),
            line=stmt.line,
            column=stmt.column
        )
        if not self.symbols.define(symbol):
            self.error(f"Redefinition of external symbol '{stmt.name}'", stmt)
        return stmt.type_

    def _check_expr_stmt(self, stmt: ExprStmt) -> TypeNode:
        """Check an expression statement."""
        return self._check_expression(stmt.expr)

    def _check_assignment_stmt(self, stmt: AssignmentStmt) -> TypeNode:
        """Check an assignment statement."""
        lhs_type = self._check_expression(stmt.lhs)
        rhs_type = self._check_expression(stmt.rhs)

        # Check mutability
        if isinstance(stmt.lhs, IdentifierExpr):
            symbol = self.symbols.lookup(stmt.lhs.name)
            if symbol and not symbol.mutable:
                self.error(f"Cannot assign to immutable variable '{stmt.lhs.name}'", stmt)

        # Handle compound assignment operators
        if stmt.op != '=':
            base_op = stmt.op.rstrip('=')
            if base_op in {'+', '-', '*', '/', '%', '&', '|', '^', '<<', '>>'}:
                # Both operands must support the operation
                if isinstance(lhs_type, BaseType) and isinstance(rhs_type, BaseType):
                    if not (lhs_type.name.startswith(('I', 'U', 'F')) and
                            rhs_type.name.startswith(('I', 'U', 'F'))):
                        self.error(f"Cannot apply operator '{base_op}' to non-numeric types", stmt)
            else:
                pass  # Will be checked elsewhere

        if not self._is_assignable_to(rhs_type, lhs_type):
            self.error(
                f"Type mismatch: cannot assign {self._type_name(rhs_type)} "
                f"to {self._type_name(lhs_type)}",
                stmt
            )

        return lhs_type

    def _check_return_stmt(self, stmt: ReturnStmt) -> TypeNode:
        """Check a return statement."""
        value_type = self._check_expression(stmt.value) if stmt.value else BaseType(name='Void')

        if self._current_function_return_type:
            if not self._is_assignable_to(value_type, self._current_function_return_type):
                self.error(
                    f"Return type mismatch: expected {self._type_name(self._current_function_return_type)}, "
                    f"got {self._type_name(value_type)}",
                    stmt
                )

        return value_type

    def _check_throw_stmt(self, stmt: ThrowStmt) -> TypeNode:
        """Check a throw statement."""
        self._check_expression(stmt.value)
        return BaseType(name='Void')

    def _check_expression(self, expr: Expr) -> TypeNode:
        """Check an expression and return its type."""
        if isinstance(expr, LiteralExpr):
            return self._infer_literal_type(expr)
        if isinstance(expr, IdentifierExpr):
            return self._check_identifier_expr(expr)
        if isinstance(expr, UnaryExpr):
            return self._check_unary_expr(expr)
        if isinstance(expr, BinaryExpr):
            return self._check_binary_expr(expr)
        if isinstance(expr, ConditionalExpr):
            return self._check_conditional_expr(expr)
        if isinstance(expr, MemberAccessExpr):
            return self._check_member_access_expr(expr)
        if isinstance(expr, CallExpr):
            return self._check_call_expr(expr)
        if isinstance(expr, IndexExpr):
            return self._check_index_expr(expr)
        if isinstance(expr, TypeAssertionExpr):
            return self._check_type_assertion_expr(expr)
        if isinstance(expr, OptionalUnwrapExpr):
            return self._check_optional_unwrap_expr(expr)
        if isinstance(expr, PipelineExpr):
            return self._check_pipeline_expr(expr)
        if isinstance(expr, StructLiteralExpr):
            return self._check_struct_literal_expr(expr)
        if isinstance(expr, ArrayLiteralExpr):
            return self._check_array_literal_expr(expr)
        if isinstance(expr, VecLiteralExpr):
            return self._check_vec_literal_expr(expr)
        if isinstance(expr, FunctionLiteralExpr):
            return self._check_function_literal_expr(expr)
        if isinstance(expr, BlockExpr):
            return self._check_block_expr(expr)
        if isinstance(expr, FlowExpr):
            return self._check_flow_expr(expr)
        if isinstance(expr, MatchExpr):
            return self._check_match_expr(expr)
        if isinstance(expr, CatchExpr):
            return self._check_catch_expr(expr)
        if isinstance(expr, LoopExpr):
            return self._check_loop_expr(expr)
        if isinstance(expr, IfLikeExpr):
            return self._check_if_like_expr(expr)
        return BaseType(name='Void')

    def _check_identifier_expr(self, expr: IdentifierExpr) -> TypeNode:
        """Check an identifier expression."""
        symbol = self.symbols.lookup(expr.name)
        if not symbol:
            self.error(f"Undefined identifier '{expr.name}'", expr)
            return BaseType(name='Void')
        return symbol.type_ or BaseType(name='Void')

    def _check_unary_expr(self, expr: UnaryExpr) -> TypeNode:
        """Check a unary expression."""
        operand_type = self._check_expression(expr.operand)

        if expr.op == '!':
            if not isinstance(operand_type, BaseType) or operand_type.name != 'Bool':
                self.error(f"Logical '!' requires Bool operand", expr)
            return BaseType(name='Bool')

        if expr.op in {'+', '-'}:
            if not isinstance(operand_type, BaseType):
                self.error(f"Arithmetic operator requires numeric operand", expr)
                return BaseType(name='I32')
            if not operand_type.name.startswith(('I', 'U', 'F')):
                self.error(f"Arithmetic operator requires numeric operand", expr)
            return operand_type

        if expr.op == '~':
            if not isinstance(operand_type, BaseType):
                self.error(f"Bitwise '~' requires integer operand", expr)
                return BaseType(name='I32')
            if not operand_type.name.startswith(('I', 'U')):
                self.error(f"Bitwise '~' requires integer operand", expr)
            return operand_type

        return operand_type

    def _check_binary_expr(self, expr: BinaryExpr) -> TypeNode:
        """Check a binary expression."""
        left_type = self._check_expression(expr.left)
        right_type = self._check_expression(expr.right)

        op = expr.op

        # Comparison operators
        if op in {'==', '!=', '<', '>', '<=', '>='}:
            return BaseType(name='Bool')

        # Logical operators
        if op in {'&&', '||'}:
            return BaseType(name='Bool')

        # Arithmetic and bitwise operators return common type
        if isinstance(left_type, BaseType) and isinstance(right_type, BaseType):
            # Floating point takes precedence
            if left_type.name.startswith('F') or right_type.name.startswith('F'):
                return BaseType(name='F64')
            # Larger integer type wins
            left_size = int(left_type.name[1:]) if left_type.name[1:].isdigit() else 32
            right_size = int(right_type.name[1:]) if right_type.name[1:].isdigit() else 32
            size = max(left_size, right_size)
            prefix = 'U' if left_type.name.startswith('U') and right_type.name.startswith('U') else 'I'
            return BaseType(name=f"{prefix}{size}")

        return left_type

    def _check_conditional_expr(self, expr: ConditionalExpr) -> TypeNode:
        """Check a ternary conditional expression."""
        cond_type = self._check_expression(expr.condition)
        if isinstance(cond_type, BaseType) and cond_type.name != 'Bool':
            self.error(f"Condition must be Bool, got {self._type_name(cond_type)}", expr)

        then_type = self._check_expression(expr.then_branch)
        else_type = self._check_expression(expr.else_branch)

        if self._types_equal(then_type, else_type):
            return then_type
        return UnionType(types=[then_type, else_type])

    def _check_member_access_expr(self, expr: MemberAccessExpr) -> TypeNode:
        """Check a member access expression."""
        obj_type = self._check_expression(expr.object)
        # Member access type checking requires struct type info
        # For now, return generic type
        return BaseType(name='Unknown')

    def _check_call_expr(self, expr: CallExpr) -> TypeNode:
        """Check a function call expression."""
        func_type = self._check_expression(expr.callee)

        if isinstance(func_type, FunctionType):
            # Check parameters
            for param in func_type.params:
                if param.name not in expr.args:
                    if param.default_value is None:
                        self.error(f"Missing required argument '{param.name}'", expr)

            # Check argument types
            for arg_name, arg_value in expr.args.items():
                arg_type = self._check_expression(arg_value)
                # Find matching param
                matching_params = [p for p in func_type.params if p.name == arg_name]
                if matching_params and not self._is_assignable_to(arg_type, matching_params[0].type_):
                    self.error(
                        f"Argument '{arg_name}' type mismatch: expected "
                        f"{self._type_name(matching_params[0].type_)}, got "
                        f"{self._type_name(arg_type)}",
                        expr
                    )

            return func_type.return_type

        return BaseType(name='Unknown')

    def _check_index_expr(self, expr: IndexExpr) -> TypeNode:
        """Check an index expression."""
        array_type = self._check_expression(expr.array)
        index_type = self._check_expression(expr.index)

        if isinstance(index_type, BaseType) and not index_type.name.startswith(('I', 'U')):
            self.error(f"Array index must be integer", expr)

        if isinstance(array_type, ArrayType):
            return array_type.element

        return BaseType(name='Unknown')

    def _check_type_assertion_expr(self, expr: TypeAssertionExpr) -> TypeNode:
        """Check a type assertion expression."""
        # Type assertion is unchecked at compile time (runtime check)
        return self._check_expression(expr.expr)

    def _check_optional_unwrap_expr(self, expr: OptionalUnwrapExpr) -> TypeNode:
        """Check an optional unwrap expression."""
        inner_type = self._check_expression(expr.expr)
        if isinstance(inner_type, OptionalType):
            return inner_type.base
        return inner_type

    def _check_pipeline_expr(self, expr: PipelineExpr) -> TypeNode:
        """Check a pipeline expression."""
        value_type = self._check_expression(expr.value)
        # Pipeline rewrites to function call; type checking deferred
        return BaseType(name='Unknown')

    def _check_struct_literal_expr(self, expr: StructLiteralExpr) -> TypeNode:
        """Check a struct literal expression."""
        struct_type = BaseType(name=expr.struct_name)
        # Validate fields against struct definition
        symbol = self.symbols.lookup(expr.struct_name)
        if not symbol or symbol.kind != SymbolKind.STRUCT:
            self.error(f"Undefined struct '{expr.struct_name}'", expr)
        return struct_type

    def _check_array_literal_expr(self, expr: ArrayLiteralExpr) -> TypeNode:
        """Check an array literal expression."""
        if not expr.elements:
            return ArrayType(element=BaseType(name='Unknown'))

        # Get common element type
        element_types = [self._check_expression(e) for e in expr.elements]
        common_type = element_types[0]
        for t in element_types[1:]:
            if not self._types_equal(t, common_type):
                common_type = BaseType(name='Unknown')
                break

        return ArrayType(element=common_type)

    def _check_vec_literal_expr(self, expr: VecLiteralExpr) -> TypeNode:
        """Check a SIMD vector literal expression."""
        if not expr.elements:
            return VecType(element=BaseType(name='I32'), size=0)

        element_types = [self._check_expression(e) for e in expr.elements]
        return VecType(element=element_types[0], size=len(expr.elements))

    def _check_function_literal_expr(self, expr: FunctionLiteralExpr) -> TypeNode:
        """Check a function literal expression."""
        self.symbols.push_scope("function")

        # Register parameters
        for param in expr.params:
            symbol = Symbol(
                name=param.name,
                kind=SymbolKind.PARAMETER,
                type_=param.type_,
                mutable=True,
                line=param.line,
                column=param.column
            )
            self.symbols.define(symbol)

        old_return_type = self._current_function_return_type
        self._current_function_return_type = expr.return_type

        # Check body
        body_type = self._check_expression(expr.body)

        self._current_function_return_type = old_return_type
        self.symbols.pop_scope()

        # Check return type matches
        if expr.return_type and not self._is_assignable_to(body_type, expr.return_type):
            self.error(
                f"Function body returns {self._type_name(body_type)}, "
                f"declared return type is {self._type_name(expr.return_type)}",
                expr
            )

        return FunctionType(
            params=expr.params,
            return_type=expr.return_type or body_type
        )

    def _check_block_expr(self, expr: BlockExpr) -> TypeNode:
        """Check a block expression."""
        self.symbols.push_scope("block")
        last_type = BaseType(name='Void')
        for stmt in expr.statements:
            last_type = self._check_statement(stmt) or BaseType(name='Void')
        self.symbols.pop_scope()
        return last_type

    def _check_flow_expr(self, expr: FlowExpr) -> TypeNode:
        """Check a flow expression."""
        return self._check_expression(expr.body)

    def _check_match_expr(self, expr: MatchExpr) -> TypeNode:
        """Check a match expression."""
        result_type = BaseType(name='Void')
        for clause in expr.clauses:
            cond_type = self._check_expression(clause.condition)
            if isinstance(cond_type, BaseType) and cond_type.name != 'Bool':
                self.error(f"Match condition must be Bool", clause)
            body_type = self._check_expression(clause.body)
            result_type = body_type  # Use last body type
        return result_type

    def _check_catch_expr(self, expr: CatchExpr) -> TypeNode:
        """Check a catch expression."""
        self._check_expression(expr.body)
        # Returns Error or Void
        return BaseType(name='Error')

    def _check_loop_expr(self, expr: LoopExpr) -> TypeNode:
        """Check a loop expression."""
        if expr.variable:
            self.symbols.push_scope("loop")
            symbol = Symbol(
                name=expr.variable,
                kind=SymbolKind.VARIABLE,
                type_=BaseType(name='I32'),
                mutable=True,
                line=expr.line,
                column=expr.column
            )
            self.symbols.define(symbol)

        if expr.range_expr:
            self._check_expression(expr.range_expr)

        self._check_expression(expr.body)

        if expr.variable:
            self.symbols.pop_scope()

        return BaseType(name='Void')

    def _check_if_like_expr(self, expr: IfLikeExpr) -> TypeNode:
        """Check an if-like expression."""
        cond_type = self._check_expression(expr.condition)
        if isinstance(cond_type, BaseType) and cond_type.name != 'Bool':
            self.error(f"If condition must be Bool", expr)

        then_type = self._check_expression(expr.then_branch)

        if expr.else_branch:
            else_type = self._check_expression(expr.else_branch)
            if self._types_equal(then_type, else_type):
                return then_type
            return UnionType(types=[then_type, else_type])

        return BaseType(name='Void')

    def _type_name(self, t: Optional[TypeNode]) -> str:
        """Get a human-readable type name."""
        if not t:
            return 'Void'
        if isinstance(t, BaseType):
            return t.name
        if isinstance(t, OptionalType):
            return f"{self._type_name(t.base)}?"
        if isinstance(t, UnionType):
            return " | ".join(self._type_name(x) for x in t.types)
        if isinstance(t, ArrayType):
            return f"{self._type_name(t.element)}[]"
        if isinstance(t, VecType):
            return f"Vec<{self._type_name(t.element)}>[{t.size}]"
        if isinstance(t, FunctionType):
            params = ", ".join(f"{p.name}: {self._type_name(p.type_)}" for p in t.params)
            return f"({params}) => {self._type_name(t.return_type)}"
        if isinstance(t, GenericType):
            args = ", ".join(self._type_name(a) for a in t.args)
            return f"{t.base.name}<{args}>"
        return 'Unknown'
