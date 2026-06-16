"""EzLang 符号表与作用域管理"""

from enum import Enum, auto
from typing import Optional


class SymbolKind(Enum):
    VARIABLE = auto()
    CONSTANT = auto()
    STATIC = auto()
    STRUCT = auto()
    FUNCTION = auto()
    TYPE_ALIAS = auto()
    PARAM = auto()
    EXTERN_DECLARE = auto()


class TypeKind(Enum):
    BASIC = auto()       # I32, F64, Str, Bool 等基本类型
    ARRAY = auto()       # T[]
    LIST = auto()        # List<T>
    DICT = auto()        # Dict<K, V>
    VEC = auto()         # Vec<T>[N]
    OPTIONAL = auto()    # T?
    UNION = auto()       # T1 | T2
    FUNCTION = auto()    # (params) => returnType
    STRUCT = auto()      # struct 类型
    POINTER = auto()     # *T 指针类型
    WEAK_REF = auto()    # #T 弱引用类型


class Type:
    """EzLang 类型表示"""

    def __init__(self, name: str = "unknown", kind: TypeKind = TypeKind.BASIC,
                 is_optional: bool = False, is_union: bool = False):
        self.kind = kind
        self.name = name
        self.is_optional = is_optional
        self.is_union = is_union
        # 复合类型的子类型信息
        self.element_type: Optional[Type] = None   # 数组/List/Vec/Optional 的元素类型
        self.key_type: Optional[Type] = None       # Dict 的键类型
        self.value_type: Optional[Type] = None     # Dict 的值类型
        self.vec_size: int = 0                     # Vec 的元素数量
        self.param_types: list[Type] = []          # 函数参数类型
        self.param_names: list[str] = []           # 函数参数名（按顺序）
        self.default_param_names: set[str] = set() # 有默认值的函数参数名
        self.return_type: Optional[Type] = None    # 函数返回类型
        self.union_types: list[Type] = []          # 联合类型的成员类型
        self.fields: dict[str, "Type"] = {}        # 结构体字段名→类型映射
        self.pointee_type: Optional[Type] = None    # 指针指向的类型
        self.referent_type: Optional[Type] = None    # 弱引用指向的类型

    def __repr__(self):
        if self.kind == TypeKind.ARRAY:
            return f"{self.element_type}[]"
        if self.kind == TypeKind.LIST:
            return f"List<{self.element_type}>"
        if self.kind == TypeKind.DICT:
            if self.key_type is not None and self.value_type is not None:
                return f"Dict<{self.key_type}, {self.value_type}>"
            return "Dict"
        if self.kind == TypeKind.VEC:
            return f"Vec<{self.element_type}>[{self.vec_size}]"
        if self.kind == TypeKind.OPTIONAL:
            return f"{self.element_type}?"
        if self.kind == TypeKind.UNION:
            return " | ".join(str(t) for t in self.union_types)
        if self.kind == TypeKind.FUNCTION:
            params = ", ".join(str(p) for p in self.param_types)
            return f"({params}) => {self.return_type}"
        if self.kind == TypeKind.POINTER:
            return f"*{self.pointee_type}"
        if self.kind == TypeKind.WEAK_REF:
            return f"#{self.referent_type}"
        opt = "?" if self.is_optional else ""
        return f"{self.name}{opt}"

    def __eq__(self, other):
        if not isinstance(other, Type):
            return False
        if self.kind != other.kind:
            return False
        if self.kind == TypeKind.BASIC:
            return self.name == other.name
        if self.kind == TypeKind.ARRAY or self.kind == TypeKind.LIST or self.kind == TypeKind.OPTIONAL:
            return self.element_type == other.element_type
        if self.kind == TypeKind.DICT:
            return self.key_type == other.key_type and self.value_type == other.value_type
        if self.kind == TypeKind.VEC:
            return self.element_type == other.element_type and self.vec_size == other.vec_size
        if self.kind == TypeKind.UNION:
            return self.union_types == other.union_types
        if self.kind == TypeKind.FUNCTION:
            return self.param_types == other.param_types and self.return_type == other.return_type
        if self.kind == TypeKind.POINTER:
            return self.pointee_type == other.pointee_type
        if self.kind == TypeKind.WEAK_REF:
            return self.referent_type == other.referent_type
        return self.name == other.name

    def is_numeric(self) -> bool:
        """是否数值类型（整数或浮点数）"""
        return self.name in ("I8", "I32", "I64", "U8", "U32", "U64", "F32", "F64")

    def is_integer(self) -> bool:
        return self.name in ("I8", "I32", "I64", "U8", "U32", "U64")

    def is_float(self) -> bool:
        return self.name in ("F32", "F64")

    def is_bool(self) -> bool:
        return self.name == "Bool"

    def is_string(self) -> bool:
        return self.name == "Str"

    def compatible_with(self, other: "Type") -> bool:
        """检查两类型是否兼容（可用于赋值、运算等）"""
        if self == other:
            return True
        # T 可以赋给 T?，T? 在需要 T 的位置由解包语义处理。
        if self.kind == TypeKind.OPTIONAL and self.element_type is not None:
            return self.element_type.compatible_with(other)
        if other.kind == TypeKind.OPTIONAL and other.element_type is not None:
            return self.compatible_with(other.element_type)
        # 数值类型之间可以隐式转换
        if self.is_numeric() and other.is_numeric():
            return True
        # List<T> 和 T[] 使用同一种运行时表示
        if {self.kind, other.kind} == {TypeKind.ARRAY, TypeKind.LIST}:
            if self.element_type is None or other.element_type is None:
                return True
            return self.element_type.compatible_with(other.element_type)
        if self.kind in (TypeKind.ARRAY, TypeKind.LIST) and other.kind in (TypeKind.ARRAY, TypeKind.LIST):
            if self.element_type is None or other.element_type is None:
                return True
            return self.element_type.compatible_with(other.element_type)
        if self.kind == TypeKind.DICT and other.kind == TypeKind.DICT:
            if self.key_type is None or self.value_type is None:
                return True
            if other.key_type is None or other.value_type is None:
                return True
            return self.key_type.compatible_with(other.key_type) and self.value_type.compatible_with(other.value_type)
        if self.kind == TypeKind.FUNCTION and other.kind == TypeKind.FUNCTION:
            if len(self.param_types) != len(other.param_types):
                return False
            for expected_param, actual_param in zip(self.param_types, other.param_types):
                if expected_param is not None and actual_param is not None \
                        and not expected_param.compatible_with(actual_param):
                    return False
            if self.return_type is None or other.return_type is None:
                return True
            return self.return_type.compatible_with(other.return_type)
        # 结构体按字段信息兼容，不能只比较名字
        if self.kind == TypeKind.STRUCT and other.kind == TypeKind.STRUCT:
            if self.name == other.name:
                return True
            if not self.fields or not other.fields:
                return False
            for field_name, field_type in self.fields.items():
                other_field_type = other.fields.get(field_name)
                if other_field_type is None or not field_type.compatible_with(other_field_type):
                    return False
            return True
        # 联合类型：实际类型匹配任一成员即为兼容
        if self.kind == TypeKind.UNION and self.union_types:
            return any(other.compatible_with(t) for t in self.union_types)
        if other.kind == TypeKind.UNION and other.union_types:
            return any(self.compatible_with(t) for t in other.union_types)
        if self.kind == TypeKind.POINTER and other.kind == TypeKind.POINTER:
            if self.pointee_type is None or other.pointee_type is None:
                return True
            return self.pointee_type.compatible_with(other.pointee_type)
        if self.kind == TypeKind.WEAK_REF and other.kind == TypeKind.WEAK_REF:
            if self.referent_type is None or other.referent_type is None:
                return True
            return self.referent_type.compatible_with(other.referent_type)
        if self.kind == TypeKind.WEAK_REF and other.kind == TypeKind.OPTIONAL:
            if self.referent_type is None or other.element_type is None:
                return True
            return self.referent_type.compatible_with(other.element_type)
        if self.kind == TypeKind.OPTIONAL and other.kind == TypeKind.WEAK_REF:
            if self.element_type is None or other.referent_type is None:
                return True
            return self.element_type.compatible_with(other.referent_type)
        return False


class Symbol:
    """符号表中的条目"""

    def __init__(
        self,
        name: str,
        kind: SymbolKind,
        type_: Optional[Type] = None,
        mutable: bool = True,
        exported: bool = False,
        line: int = 0,
        lock_policy: str = "ordered",
    ):
        self.name = name
        self.kind = kind
        self.type = type_
        self.mutable = mutable
        self.exported = exported
        self.line = line
        self.lock_policy = lock_policy

    def __repr__(self):
        return f"Symbol({self.name}, {self.kind}, {self.type})"


class Scope:
    """单个作用域"""

    def __init__(self, name: str = "global", parent: Optional["Scope"] = None):
        self.name = name
        self.parent = parent
        self.symbols: dict[str, Symbol] = {}

    def define(self, symbol: Symbol) -> Symbol:
        self.symbols[symbol.name] = symbol
        return symbol

    def resolve(self, name: str) -> Optional[Symbol]:
        """在当前作用域及父作用域中查找符号"""
        current: Optional[Scope] = self
        while current is not None:
            if name in current.symbols:
                return current.symbols[name]
            current = current.parent
        return None

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """仅在当前作用域中查找"""
        return self.symbols.get(name)

    def contains(self, name: str) -> bool:
        return name in self.symbols

    def __repr__(self):
        return f"Scope({self.name}, symbols={list(self.symbols.keys())})"


class SymbolTable:
    """全局符号表，管理作用域栈"""

    def __init__(self):
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def push_scope(self, name: str = "") -> Scope:
        scope = Scope(name, self.current_scope)
        self.current_scope = scope
        return scope

    def pop_scope(self) -> Scope:
        scope = self.current_scope
        if scope.parent is not None:
            self.current_scope = scope.parent
        return scope

    def define(self, symbol: Symbol) -> Symbol:
        existing = self.current_scope.resolve_local(symbol.name)
        if existing is not None:
            self.errors.append(
                f"行 {symbol.line}: 符号 '{symbol.name}' 重复声明"
            )
        return self.current_scope.define(symbol)

    def resolve(self, name: str) -> Optional[Symbol]:
        return self.current_scope.resolve(name)

    def add_error(self, msg: str):
        self.errors.append(self._with_hint(msg))

    def add_warning(self, msg: str):
        self.warnings.append(self._with_hint(msg))

    @staticmethod
    def _with_hint(msg: str) -> str:
        """为常见错误补充简短修复建议。"""
        if "未定义的变量" in msg:
            return msg + "。建议：检查拼写，或先用 let/const/declare 定义该符号"
        if "类型不匹配" in msg:
            return msg + "。建议：调整类型注解，或显式转换为期望类型"
        if "缺少必填参数" in msg:
            return msg + "。建议：按函数签名补齐具名参数"
        if "未知参数" in msg:
            return msg + "。建议：检查参数名是否与函数声明一致"
        if "没有关联 extern 库" in msg:
            return msg + "。建议：在 declare 前添加 extern，或将该函数实现为 compiler builtin"
        return msg

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def __repr__(self):
        return f"SymbolTable(scope={self.current_scope.name}, symbols={len(self.current_scope.symbols)})"


# 内建类型
def _make_basic(name: str) -> Type:
    return Type(name=name, kind=TypeKind.BASIC)


def _make_struct(name: str, fields: dict[str, Type]) -> Type:
    t = Type(name=name, kind=TypeKind.STRUCT)
    t.fields = fields
    return t


def _make_function(params: list[tuple[str, Type]], ret: Type) -> Type:
    t = Type(name="function", kind=TypeKind.FUNCTION)
    t.param_names = [name for name, _ in params]
    t.param_types = [type_ for _, type_ in params]
    t.return_type = ret
    return t


def _make_optional(inner: Type) -> Type:
    t = Type(name=f"{inner.name}?", kind=TypeKind.OPTIONAL)
    t.element_type = inner
    return t


def _make_weak(inner: Type) -> Type:
    t = Type(name=f"#{inner.name}", kind=TypeKind.WEAK_REF)
    t.referent_type = inner
    t.element_type = inner
    return t


BUILTIN_TYPES = {
    "I8": _make_basic("I8"),
    "I32": _make_basic("I32"),
    "I64": _make_basic("I64"),
    "U8": _make_basic("U8"),
    "U32": _make_basic("U32"),
    "U64": _make_basic("U64"),
    "F32": _make_basic("F32"),
    "F64": _make_basic("F64"),
    "Str": _make_basic("Str"),
    "Bool": _make_basic("Bool"),
    "Void": _make_basic("Void"),
    "Vec": Type(name="Vec", kind=TypeKind.BASIC),
    "List": Type(name="List", kind=TypeKind.BASIC),
    "Dict": Type(name="Dict", kind=TypeKind.DICT),
    "Date": _make_struct("Date", {"timestamp": _make_basic("I64")}),
    "Error": _make_struct("Error", {
        "code": _make_basic("I32"),
        "message": _make_basic("Str"),
        "file": _make_basic("Str"),
        "line": _make_basic("I32"),
        "column": _make_basic("I32"),
        "trace": _make_basic("Str"),
    }),
    "Blob": _make_struct("Blob", {"data": _make_basic("Str"), "size": _make_basic("I64")}),
}

BUILTIN_TYPES["Error"].methods = {
    "toString": _make_function([("this", _make_weak(BUILTIN_TYPES["Error"]))], BUILTIN_TYPES["Str"]),
}
_DATE_THIS = _make_weak(BUILTIN_TYPES["Date"])
BUILTIN_TYPES["Date"].methods = {
    "getYear": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "getMonth": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "getDay": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "getHour": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "getMinute": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "getSecond": _make_function([("this", _DATE_THIS)], BUILTIN_TYPES["I32"]),
    "add": _make_function([
        ("this", _DATE_THIS),
        ("year", _make_optional(BUILTIN_TYPES["I32"])),
        ("month", _make_optional(BUILTIN_TYPES["I32"])),
        ("day", _make_optional(BUILTIN_TYPES["I32"])),
        ("hour", _make_optional(BUILTIN_TYPES["I32"])),
        ("minute", _make_optional(BUILTIN_TYPES["I32"])),
        ("second", _make_optional(BUILTIN_TYPES["I32"])),
    ], BUILTIN_TYPES["Void"]),
    "sub": _make_function([
        ("this", _DATE_THIS),
        ("year", _make_optional(BUILTIN_TYPES["I32"])),
        ("month", _make_optional(BUILTIN_TYPES["I32"])),
        ("day", _make_optional(BUILTIN_TYPES["I32"])),
        ("hour", _make_optional(BUILTIN_TYPES["I32"])),
        ("minute", _make_optional(BUILTIN_TYPES["I32"])),
        ("second", _make_optional(BUILTIN_TYPES["I32"])),
    ], BUILTIN_TYPES["Void"]),
    "format": _make_function([("this", _DATE_THIS), ("fmt", BUILTIN_TYPES["Str"])], BUILTIN_TYPES["Str"]),
}
_BLOB_THIS = _make_weak(BUILTIN_TYPES["Blob"])
BUILTIN_TYPES["Blob"].methods = {
    "get": _make_function(
        [("this", _BLOB_THIS), ("index", BUILTIN_TYPES["I64"])],
        BUILTIN_TYPES["I8"],
    ),
    "slice": _make_function(
        [("this", _BLOB_THIS), ("start", BUILTIN_TYPES["I64"]), ("len", BUILTIN_TYPES["I64"])],
        BUILTIN_TYPES["Blob"],
    ),
}


def builtin_type(name: str) -> Optional[Type]:
    return BUILTIN_TYPES.get(name)
