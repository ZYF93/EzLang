"""Abstract Syntax Tree nodes for EzLang."""

from dataclasses import dataclass, field
from typing import Optional, List, Union, Dict, Any


@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    line: int = 0
    column: int = 0


@dataclass
class TypeNode(ASTNode):
    """Base class for type nodes."""
    pass


@dataclass
class BaseType(TypeNode):
    """Base type like I32, Str, Bool, etc."""
    name: str = ""


@dataclass
class OptionalType(TypeNode):
    """Optional type: Type?"""
    base: TypeNode = None


@dataclass
class UnionType(TypeNode):
    """Union type: Type1 | Type2"""
    types: List[TypeNode] = field(default_factory=list)


@dataclass
class ArrayType(TypeNode):
    """Array type: Type[]"""
    element: TypeNode = None


@dataclass
class VecType(TypeNode):
    """SIMD vector type: Vec<Type>[N]"""
    element: TypeNode = None
    size: int = 0


@dataclass
class GenericType(TypeNode):
    """Generic type with parameters."""
    base: TypeNode = None
    args: List[TypeNode] = field(default_factory=list)


@dataclass
class FunctionType(TypeNode):
    """Function type: (args) => ReturnType"""
    params: List["Param"] = field(default_factory=list)
    return_type: TypeNode = None


@dataclass
class TypeofType(TypeNode):
    """Type derived from expression: typeof expr"""
    expr: "Expr" = None


@dataclass
class Expr(ASTNode):
    """Base class for expressions."""
    pass


@dataclass
class LiteralExpr(Expr):
    """Literal value: integer, float, string, bool"""
    value: Any = None
    type_name: str = ""


@dataclass
class IdentifierExpr(Expr):
    """Identifier reference."""
    name: str = ""


@dataclass
class UnaryExpr(Expr):
    """Unary operator: !, -, +, ~"""
    op: str = ""
    operand: Expr = None


@dataclass
class BinaryExpr(Expr):
    """Binary operator: +, -, *, /, %, &, |, ^, <<, >>, ==, !=, <, >, <=, >=, &&, ||"""
    op: str = ""
    left: Expr = None
    right: Expr = None


@dataclass
class ConditionalExpr(Expr):
    """Ternary conditional: cond ? then : else"""
    condition: Expr = None
    then_branch: Expr = None
    else_branch: Expr = None


@dataclass
class MemberAccessExpr(Expr):
    """Member access: obj.field"""
    object: Expr = None
    member: str = ""


@dataclass
class CallExpr(Expr):
    """Function call: fn(a = 1, b = 2)"""
    callee: Expr = None
    args: Dict[str, Expr] = field(default_factory=dict)


@dataclass
class IndexExpr(Expr):
    """Array index: arr[i]"""
    array: Expr = None
    index: Expr = None


@dataclass
class TypeAssertionExpr(Expr):
    """Type assertion: Type! expr"""
    target_type: TypeNode = None
    expr: Expr = None


@dataclass
class OptionalUnwrapExpr(Expr):
    """Optional unwrap: expr?"""
    expr: Expr = None


@dataclass
class PipelineExpr(Expr):
    """Pipeline: value -> fn(a = %)"""
    value: Expr = None
    function: str = ""
    args: Dict[str, Union[Expr, str]] = field(default_factory=dict)


@dataclass
class StructLiteralExpr(Expr):
    """Struct literal: Struct(field = value)"""
    struct_name: str = ""
    generic_args: List[TypeNode] = field(default_factory=list)
    fields: Dict[str, Expr] = field(default_factory=dict)
    spread: Optional[Expr] = None


@dataclass
class ArrayLiteralExpr(Expr):
    """Array literal: [1, 2, 3]"""
    elements: List[Expr] = field(default_factory=list)


@dataclass
class VecLiteralExpr(Expr):
    """SIMD vector literal: Vec[1, 2, 3, 4]"""
    elements: List[Expr] = field(default_factory=list)


@dataclass
class FunctionLiteralExpr(Expr):
    """Function literal: (a: T) => expr"""
    generic_params: List[str] = field(default_factory=list)
    params: List["Param"] = field(default_factory=list)
    return_type: Optional[TypeNode] = None
    body: Union[Expr, "BlockExpr"] = None


@dataclass
class Param(ASTNode):
    """Function parameter."""
    name: str = ""
    type_: TypeNode = None
    default_value: Optional[Expr] = None


@dataclass
class BlockExpr(Expr):
    """Block expression: { statements }"""
    statements: List["Stmt"] = field(default_factory=list)


@dataclass
class FlowExpr(Expr):
    """Flow concurrent block: flow { ... }"""
    body: BlockExpr = None


@dataclass
class MatchExpr(Expr):
    """Match expression: match { (cond) ? expr, ... }"""
    clauses: List["MatchClause"] = field(default_factory=list)


@dataclass
class MatchClause(ASTNode):
    """Single match clause: (condition) ? body"""
    condition: Expr = None
    body: Union[Expr, BlockExpr] = None


@dataclass
class CatchExpr(Expr):
    """Catch expression: catch { throw expr }"""
    body: BlockExpr = None


@dataclass
class LoopExpr(Expr):
    """Loop expression: loop i in 0...10 { ... }"""
    variable: Optional[str] = None
    range_expr: Optional[Expr] = None
    body: BlockExpr = None


@dataclass
class IfLikeExpr(Expr):
    """If-like expression: (cond) ? { then } : { else }"""
    condition: Expr = None
    then_branch: Union[Expr, BlockExpr] = None
    else_branch: Optional[Union[Expr, BlockExpr]] = None


@dataclass
class Stmt(ASTNode):
    """Base class for statements."""
    pass


@dataclass
class VariableDeclStmt(Stmt):
    """Variable declaration: let/const/static x: T = expr"""
    kind: str = ""  # let, const, static
    name: str = ""
    type_: Optional[TypeNode] = None
    initializer: Expr = None


@dataclass
class StructDeclStmt(Stmt):
    """Struct declaration: struct Name { ... }"""
    name: str = ""
    generic_params: List[str] = field(default_factory=list)
    members: List[Union["StructField", "StructMethod", "StructSpread"]] = field(default_factory=list)


@dataclass
class StructField(ASTNode):
    """Struct field: name: Type = default"""
    name: str = ""
    type_: TypeNode = None
    default_value: Optional[Expr] = None


@dataclass
class StructMethod(ASTNode):
    """Struct method: name = (this: Type) => expr"""
    name: str = ""
    function: FunctionLiteralExpr = None


@dataclass
class StructSpread(ASTNode):
    """Struct spread: ...Base"""
    base_type: TypeNode = None


@dataclass
class TypeAliasDeclStmt(Stmt):
    """Type alias: type Name = { ... }"""
    name: str = ""
    generic_params: List[str] = field(default_factory=list)
    shape: "TypeShape" = None


@dataclass
class TypeShape(ASTNode):
    """Type shape definition: { field: Type; ... }"""
    members: List[Union["TypeShapeField", "TypeShapeSpread"]] = field(default_factory=list)


@dataclass
class TypeShapeField(ASTNode):
    """Field in type shape."""
    name: str = ""
    type_: TypeNode = None
    is_dynamic_key: bool = False


@dataclass
class TypeShapeSpread(ASTNode):
    """Spread in type shape: ...Base"""
    base_type: TypeNode = None


@dataclass
class FunctionDeclStmt(Stmt):
    """Function declaration: const fn = () => expr"""
    kind: str = ""  # let, const
    name: str = ""
    generic_params: List[str] = field(default_factory=list)
    function: FunctionLiteralExpr = None


@dataclass
class ImportDeclStmt(Stmt):
    """Import declaration: from "path" import { a, b as c }"""
    path: str = ""
    imports: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExportDeclStmt(Stmt):
    """Export declaration: export decl"""
    declaration: Stmt = None


@dataclass
class ExternDeclStmt(Stmt):
    """External library declaration: extern "path" for target"""
    path: str = ""
    target: Optional[str] = None


@dataclass
class DeclareDeclStmt(Stmt):
    """External symbol declaration: declare const fn: Type"""
    kind: str = ""  # let, const, static
    name: str = ""
    type_: TypeNode = None


@dataclass
class ExprStmt(Stmt):
    """Expression statement: expr;"""
    expr: Expr = None


@dataclass
class AssignmentStmt(Stmt):
    """Assignment statement: lhs op = rhs"""
    lhs: Expr = None
    op: str = ""
    rhs: Expr = None


@dataclass
class ReturnStmt(Stmt):
    """Return statement: return expr"""
    value: Optional[Expr] = None


@dataclass
class BreakStmt(Stmt):
    """Break statement: break"""
    pass


@dataclass
class ContinueStmt(Stmt):
    """Continue statement: continue"""
    pass


@dataclass
class ThrowStmt(Stmt):
    """Throw statement: throw expr"""
    value: Expr = None


@dataclass
class Module(ASTNode):
    """Root module node."""
    statements: List[Stmt] = field(default_factory=list)
