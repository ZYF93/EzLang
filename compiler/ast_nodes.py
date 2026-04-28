"""
EzLang AST 节点定义。
所有语法树节点均继承自 ASTNode 基类，用于从 ANTLR4 Parse Tree 转换为独立的 AST 表示。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class SourceSpan:
    """源码范围。"""
    file: str = ""
    start_line: int = 0
    start_col: int = 0
    end_line: int = 0
    end_col: int = 0


@dataclass
class ASTNode:
    """AST 节点基类。"""
    span: SourceSpan = field(default_factory=SourceSpan)


# ======================== 类型节点 ========================

@dataclass
class TypeNode(ASTNode):
    """类型表达式基类。"""
    pass


@dataclass
class NamedType(TypeNode):
    """命名类型，如 I32, User, Pair<I32, Str>。"""
    name: str = ""
    type_args: list[TypeNode] = field(default_factory=list)


@dataclass
class OptionalType(TypeNode):
    """可选类型 Type?。"""
    inner: TypeNode = field(default_factory=TypeNode)


@dataclass
class ListType(TypeNode):
    """列表类型 Type[]。"""
    element: TypeNode = field(default_factory=TypeNode)


@dataclass
class UnionType(TypeNode):
    """联合类型 Type1 | Type2。"""
    types: list[TypeNode] = field(default_factory=list)


@dataclass
class FunctionType(TypeNode):
    """函数类型 (a: I32, b: Str) => Bool。"""
    params: list[ParamNode] = field(default_factory=list)
    return_type: TypeNode = field(default_factory=TypeNode)


@dataclass
class VecType(TypeNode):
    """SIMD 向量类型 Vec<T>[N]。"""
    element: TypeNode = field(default_factory=TypeNode)
    count: int = 0


@dataclass
class PointerType(TypeNode):
    """指针类型 *I8。"""
    pointee: str = ""


@dataclass
class ShapeField(ASTNode):
    """形状字段。"""
    name: str = ""
    type: TypeNode = field(default_factory=TypeNode)
    is_spread: bool = False
    # 动态键
    is_dynamic: bool = False
    key_type: Optional[TypeNode] = None


@dataclass
class ShapeType(TypeNode):
    """内联形状 { name: Str; age: I32 }。"""
    fields: list[ShapeField] = field(default_factory=list)


# ======================== 表达式节点 ========================

@dataclass
class ExprNode(ASTNode):
    """表达式基类。"""
    pass


@dataclass
class IntLiteral(ExprNode):
    value: int = 0


@dataclass
class FloatLiteral(ExprNode):
    value: float = 0.0


@dataclass
class StringLiteral(ExprNode):
    value: str = ""


@dataclass
class BoolLiteral(ExprNode):
    value: bool = False


@dataclass
class Identifier(ExprNode):
    name: str = ""


@dataclass
class BinaryExpr(ExprNode):
    op: str = ""
    left: ExprNode = field(default_factory=ExprNode)
    right: ExprNode = field(default_factory=ExprNode)


@dataclass
class UnaryExpr(ExprNode):
    op: str = ""
    operand: ExprNode = field(default_factory=ExprNode)


@dataclass
class AssignExpr(ExprNode):
    """赋值表达式 (包含 +=, -= 等)。"""
    op: str = "="
    target: ExprNode = field(default_factory=ExprNode)
    value: ExprNode = field(default_factory=ExprNode)


@dataclass
class ConditionalExpr(ExprNode):
    """条件表达式 (cond) ? then : else。"""
    condition: ExprNode = field(default_factory=ExprNode)
    then_expr: Union[ExprNode, BlockStmt] = field(default_factory=ExprNode)
    else_expr: Optional[Union[ExprNode, BlockStmt, 'ConditionalExpr']] = None


@dataclass
class MemberAccess(ExprNode):
    """成员访问 obj.field。"""
    object: ExprNode = field(default_factory=ExprNode)
    member: str = ""


@dataclass
class NamedArg(ASTNode):
    """命名参数 name = value。"""
    name: str = ""
    value: Optional[ExprNode] = None
    is_placeholder: bool = False   # name = ?
    is_spread: bool = False        # ...expr


@dataclass
class CallExpr(ExprNode):
    """函数/结构体调用 fn(a = 1, b = 2)。"""
    callee: ExprNode = field(default_factory=ExprNode)
    args: list[NamedArg] = field(default_factory=list)


@dataclass
class IndexExpr(ExprNode):
    """索引访问 arr[i]。"""
    object: ExprNode = field(default_factory=ExprNode)
    index: ExprNode = field(default_factory=ExprNode)


@dataclass
class PipeExpr(ExprNode):
    """管道 expr -> fn(a = %)。"""
    value: ExprNode = field(default_factory=ExprNode)
    func_name: str = ""
    args: list[NamedArg] = field(default_factory=list)


@dataclass
class ParamNode(ASTNode):
    """函数参数。"""
    name: str = ""
    type: TypeNode = field(default_factory=TypeNode)
    default: Optional[ExprNode] = None


@dataclass
class LambdaExpr(ExprNode):
    """Lambda / 函数表达式。"""
    type_params: list[str] = field(default_factory=list)
    params: list[ParamNode] = field(default_factory=list)
    return_type: Optional[TypeNode] = None
    body: Union[ExprNode, 'BlockStmt'] = field(default_factory=ExprNode)


@dataclass
class MatchArm(ASTNode):
    """match 分支。"""
    condition: ExprNode = field(default_factory=ExprNode)
    body: Union[ExprNode, 'BlockStmt'] = field(default_factory=ExprNode)


@dataclass
class MatchExpr(ExprNode):
    """match 表达式。"""
    arms: list[MatchArm] = field(default_factory=list)


@dataclass
class LoopExpr(ExprNode):
    """loop 表达式。"""
    var: Optional[str] = None
    start: Optional[ExprNode] = None
    end: Optional[ExprNode] = None
    body: 'BlockStmt' = field(default_factory=lambda: BlockStmt())


@dataclass
class CatchExpr(ExprNode):
    """catch { ... }。"""
    body: 'BlockStmt' = field(default_factory=lambda: BlockStmt())


@dataclass
class AwaitExpr(ExprNode):
    """await expression。"""
    expr: ExprNode = field(default_factory=ExprNode)


@dataclass
class TypeofExpr(ExprNode):
    """typeof 表达式。"""
    expr: ExprNode = field(default_factory=ExprNode)


@dataclass
class ArrayLiteral(ExprNode):
    """数组字面量 [1, 2, 3]。"""
    elements: list[ExprNode] = field(default_factory=list)


@dataclass
class VecLiteral(ExprNode):
    """向量字面量 Vec[1, 2, 3, 4]。"""
    elements: list[ExprNode] = field(default_factory=list)


@dataclass
class DictEntry(ASTNode):
    """字典条目。"""
    key: str = ""
    type: Optional[TypeNode] = None   # None 时推断
    value: ExprNode = field(default_factory=ExprNode)


@dataclass
class DictLiteral(ExprNode):
    """字典字面量 { name = "Alice", age = 20 }。"""
    entries: list[DictEntry] = field(default_factory=list)


@dataclass
class TypeAssertExpr(ExprNode):
    """类型断言 Type! expr。"""
    assert_type: TypeNode = field(default_factory=TypeNode)
    expr: ExprNode = field(default_factory=ExprNode)


# ======================== 语句节点 ========================

@dataclass
class StmtNode(ASTNode):
    """语句基类。"""
    pass


@dataclass
class LetDecl(StmtNode):
    """let 变量声明。"""
    name: str = ""
    type: Optional[TypeNode] = None
    value: ExprNode = field(default_factory=ExprNode)
    decorator: Optional[str] = None


@dataclass
class ConstDecl(StmtNode):
    """const 常量声明。"""
    name: str = ""
    type: Optional[TypeNode] = None
    value: ExprNode = field(default_factory=ExprNode)
    is_async: bool = False
    decorator: Optional[str] = None


@dataclass
class StaticDecl(StmtNode):
    """static 静态变量声明。"""
    name: str = ""
    type: Optional[TypeNode] = None
    value: ExprNode = field(default_factory=ExprNode)


@dataclass
class StructField(ASTNode):
    """结构体字段。"""
    name: str = ""
    type: Optional[TypeNode] = None
    default: Optional[ExprNode] = None
    is_spread: bool = False
    spread_name: Optional[str] = None


@dataclass
class StructDef(StmtNode):
    """struct 定义。"""
    name: str = ""
    type_params: list[str] = field(default_factory=list)
    fields: list[StructField] = field(default_factory=list)


@dataclass
class TypeDef(StmtNode):
    """type 别名定义。"""
    name: str = ""
    type_params: list[str] = field(default_factory=list)
    value: TypeNode = field(default_factory=TypeNode)


@dataclass
class DeclareStmt(StmtNode):
    """declare 外部声明。"""
    name: str = ""
    type: TypeNode = field(default_factory=TypeNode)


@dataclass
class ImportItem(ASTNode):
    """导入项。"""
    name: str = ""
    alias: Optional[str] = None


@dataclass
class ImportStmt(StmtNode):
    """import 语句。"""
    path: str = ""
    items: list[ImportItem] = field(default_factory=list)


@dataclass
class ExportStmt(StmtNode):
    """export 语句。"""
    declaration: StmtNode = field(default_factory=StmtNode)


@dataclass
class ReturnStmt(StmtNode):
    """return 语句。"""
    value: Optional[ExprNode] = None


@dataclass
class ThrowStmt(StmtNode):
    """throw 语句。"""
    value: ExprNode = field(default_factory=ExprNode)


@dataclass
class BreakStmt(StmtNode):
    """break 语句。"""
    pass


@dataclass
class ContinueStmt(StmtNode):
    """continue 语句。"""
    pass


@dataclass
class ExprStmt(StmtNode):
    """表达式语句。"""
    expr: ExprNode = field(default_factory=ExprNode)


@dataclass
class BlockStmt(StmtNode):
    """块语句 { ... }。"""
    statements: list[StmtNode] = field(default_factory=list)


@dataclass
class Program(ASTNode):
    """顶层程序节点。"""
    statements: list[StmtNode] = field(default_factory=list)
