"""EzLang 语义分析器 — 遍历解析树进行作用域与类型检查"""

import os
import re
from pathlib import Path
from typing import Optional

from antlr4 import CommonTokenStream, InputStream, Token

from parser.EzLangLexer import EzLangLexer
from parser.EzLangParser import EzLangParser
from parser.EzLangVisitor import EzLangVisitor
from parser.string_literals import decode_string_literal_token
from .symbols import (
    SymbolTable, Symbol, SymbolKind, Type, TypeKind, Scope, builtin_type
)


class SemanticAnalyzer(EzLangVisitor):
    """语义分析访问器"""

    def __init__(self, base_dir: Optional[os.PathLike | str] = None, compile_target: Optional[str] = None,
                 allow_top_level_return: bool = False):
        self.symbols = SymbolTable()
        self.base_dir = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
        self.compile_target = compile_target
        self.allow_top_level_return = allow_top_level_return
        self.current_struct = None  # Optional[str]
        self.current_function_return: Optional[Type] = None  # 当前函数声明的返回类型
        self.in_function = False  # 是否在函数内部
        self.generic_templates: dict[str, tuple] = {}  # name → (param_names, template_ctx)
        self.struct_generic_params: dict[str, list[str]] = {}
        self.struct_method_types: dict[str, dict[str, Type]] = {}
        self._current_generic_names: set[str] = set()
        self.flow_depth = 0
        self.parallel_depth = 0
        self.loop_depth = 0
        self.match_depth = 0
        self.flow_blocks: list[dict] = []
        self.suspend_points: list[dict] = []
        self.race_calls: list[dict] = []
        self.flow_dependencies: list[dict] = []
        self.parallel_blocks: list[dict] = []
        self.locked_variables: dict[str, str] = {}
        self._parallel_return_stack: list[list[Type]] = []
        self._catch_throw_stack: list[list[Type]] = []
        self._blocking_calls = {
            "fetch", "fetchEx", "readFile", "writeFile", "appendFile", "sleep", "start",
            "tcpConnect", "tcpConnectTimeout", "tcpTlsConnect", "tcpTlsRead", "tcpTlsWrite",
            "tcpListen", "tcpAcceptTimeout", "tcpReadTimeout", "tcpWriteTimeout",
            "udpBind", "udpRecvFrom", "udpRecvFromTimeout", "udpRecvTimeout", "udpSendTimeout",
            "accept", "read", "write", "recv", "send",
            "wsConnect",
        }
        self._last_suspend_call: Optional[dict] = None
        self._current_decl_name: Optional[str] = None
        self._current_expr_reads: list[str] = []
        self._flow_suspend_values: dict[str, dict] = {}
        self.extern_libs: list[dict] = []
        self.active_extern_libs: list[str] = []
        self.declare_extern_map: dict[str, Optional[str]] = {}
        self._supported_extern_exts = {".a", ".lib", ".so", ".dylib", ".dll", ".o", ".ll", ".bc", ".framework", ".js", ".c"}
        self._exporting = False
        self._expected_expr_type_stack: list[Type] = []
        self._import_stack: set[Path] = set()
        self._imported_private_files: set[Path] = set()
        self._imported_exports: dict[Path, set[str]] = {}
        self._source_dir_stack: list[Path] = [self.base_dir]
        self._import_alias_stack: list[dict[str, str]] = []

    # ==================== 辅助方法 ====================

    def _union_type_ctxs(self, union_ctx) -> list:
        """把左递归解析得到的联合类型上下文展平为源码顺序。"""
        if not isinstance(union_ctx, EzLangParser.UnionTypeContext):
            return [union_ctx]
        result = []
        for child_ctx in union_ctx.type_():
            result.extend(self._union_type_ctxs(child_ctx))
        return result

    def _get_type_from_ctx(self, type_ctx) -> Optional[Type]:
        """从类型上下文中提取类型信息（支持复合类型）"""
        if type_ctx is None:
            return None

        if isinstance(type_ctx, EzLangParser.OptionalTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            if inner:
                result = Type(kind=TypeKind.OPTIONAL, name=f"{inner.name}?")
                result.element_type = inner
                return result

        if isinstance(type_ctx, EzLangParser.ArrayTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            if inner:
                result = Type(kind=TypeKind.ARRAY, name=f"{inner.name}[]")
                result.element_type = inner
                return result

        if isinstance(type_ctx, EzLangParser.ListTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            if inner:
                result = Type(kind=TypeKind.LIST, name=f"List<{inner.name}>")
                result.element_type = inner
                return result

        if isinstance(type_ctx, EzLangParser.VecTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            if inner:
                size = int(type_ctx.INTEGER_LITERAL().getText()) if type_ctx.INTEGER_LITERAL() is not None else 0
                result = Type(kind=TypeKind.VEC, name=f"Vec<{inner.name}>[{size}]")
                result.element_type = inner
                result.vec_size = size
                return result

        if isinstance(type_ctx, EzLangParser.UnionTypeContext):
            result = Type(kind=TypeKind.UNION, name="union")
            result.union_types = [self._get_type_from_ctx(t) for t in self._union_type_ctxs(type_ctx)]
            return result

        if isinstance(type_ctx, EzLangParser.ParenTypeContext):
            return self._get_type_from_ctx(type_ctx.type_())

        # 指针类型 *T。当前运行时按裸指针处理，语义阶段保留指向类型。
        if isinstance(type_ctx, EzLangParser.PointerTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            result = Type(kind=TypeKind.POINTER, name=f"*{inner.name if inner else 'unknown'}")
            result.pointee_type = inner
            return result

        # 弱引用类型 #T。语义上类似 T?，但 value 是对 T 的弱引用。
        if isinstance(type_ctx, EzLangParser.WeakTypeContext):
            inner = self._get_type_from_ctx(type_ctx.type_())
            result = Type(kind=TypeKind.WEAK_REF, name=f"#{inner.name if inner else 'unknown'}")
            result.referent_type = inner
            result.element_type = inner
            return result

        # 类型结构 { field: T } / { [key: K]: V } 可直接出现在类型位置。
        if isinstance(type_ctx, EzLangParser.TypeShapeTypeContext):
            return self._type_from_shape(type_ctx.typeShape())

        # 括号类型
        if hasattr(type_ctx, 'parenType') and type_ctx.parenType() is not None:
            inner = type_ctx.type_(0) if callable(type_ctx.type_) else None
            if inner is not None and not isinstance(inner, list):
                return self._get_type_from_ctx(inner)

        # 可选类型 Type?
        if hasattr(type_ctx, 'QUESTION') and type_ctx.QUESTION() is not None:
            inner_ctx = type_ctx.type_()
            if inner_ctx is not None and not isinstance(inner_ctx, list) and callable(inner_ctx):
                inner = self._get_type_from_ctx(inner_ctx)
            elif inner_ctx is not None and isinstance(inner_ctx, list) and len(inner_ctx) > 0:
                inner = self._get_type_from_ctx(inner_ctx[0])
            else:
                inner = None
            if inner:
                result = Type(kind=TypeKind.OPTIONAL, name=f"{inner.name}?")
                result.element_type = inner
                return result

        # 联合类型 Type1 | Type2
        if hasattr(type_ctx, 'PIPE') and type_ctx.PIPE() is not None:
            types = type_ctx.type_()
            if isinstance(types, list) and len(types) >= 2:
                result = Type(kind=TypeKind.UNION, name="union")
                result.union_types = [self._get_type_from_ctx(t) for t in self._union_type_ctxs(type_ctx)]
                return result

        # 数组类型 Type[]
        if (hasattr(type_ctx, 'arrayType') and type_ctx.arrayType() is not None):
            inner_ctx = type_ctx.type_()
            if inner_ctx is not None and not isinstance(inner_ctx, list):
                inner = self._get_type_from_ctx(inner_ctx)
                result = Type(kind=TypeKind.ARRAY, name=f"{inner.name}[]")
                result.element_type = inner
                return result

        # List 类型 List<Type>
        if (hasattr(type_ctx, 'listType') and type_ctx.listType() is not None):
            inner_ctx = type_ctx.type_()
            if inner_ctx is not None and not isinstance(inner_ctx, list):
                inner = self._get_type_from_ctx(inner_ctx)
                result = Type(kind=TypeKind.LIST, name=f"List<{inner.name}>")
                result.element_type = inner
                return result

        # Vec 类型 Vec<Type>[N]
        if (hasattr(type_ctx, 'vecType') and type_ctx.vecType() is not None):
            inner_ctx = type_ctx.type_()
            if inner_ctx is not None and not isinstance(inner_ctx, list):
                inner = self._get_type_from_ctx(inner_ctx)
                size = 0
                if type_ctx.INTEGER_LITERAL() is not None:
                    size = int(type_ctx.INTEGER_LITERAL().getText())
                result = Type(kind=TypeKind.VEC, name=f"Vec<{inner.name}>[{size}]")
                result.element_type = inner
                result.vec_size = size
                return result

        # 函数类型 (params) => returnType
        if (hasattr(type_ctx, 'functionType') and type_ctx.functionType() is not None):
            fn_ctx = type_ctx.functionType()
            ret = None
            ret_ctx = fn_ctx.type_()
            if ret_ctx is not None:
                ret = self._get_type_from_ctx(ret_ctx)
            param_types = []
            param_list = fn_ctx.paramTypeList()
            if param_list is not None:
                for pt in param_list.paramType():
                    t = self._get_type_from_ctx(pt.type_())
                    if t:
                        param_types.append(t)
            result = Type(kind=TypeKind.FUNCTION, name="function")
            result.param_types = param_types
            result.return_type = ret
            return result

        # 泛型参数函数类型 <T, U>(params) => returnType，主要用于 declare 声明。
        if isinstance(type_ctx, EzLangParser.GenericParamFunctionTypeContext):
            ret = self._get_type_from_ctx(type_ctx.type_())
            param_types = []
            param_names = []
            param_list = type_ctx.paramTypeList()
            if param_list is not None:
                for pt in param_list.paramType():
                    param_names.append(pt.VAR_IDENTIFIER().getText())
                    t = self._get_type_from_ctx(pt.type_())
                    if t:
                        param_types.append(t)
            result = Type(kind=TypeKind.FUNCTION, name="generic_function")
            result.param_types = param_types
            result.param_names = param_names
            result.return_type = ret
            result.generic_params = self._generic_names_from_type_list(type_ctx.typeList())
            return result

        # 泛型函数类型 <T, U> => ...
        if (hasattr(type_ctx, 'genericFunctionType') and type_ctx.genericFunctionType() is not None):
            ret = self._get_type_from_ctx(type_ctx.type_())
            result = Type(kind=TypeKind.FUNCTION, name="generic_function")
            result.return_type = ret
            result.generic_params = self._generic_names_from_type_list(type_ctx.genericFunctionType().typeList())
            return result

        # 基本类型
        bt = type_ctx.baseType() if hasattr(type_ctx, 'baseType') else None
        if bt is not None:
            if bt.I8() is not None: return Type(name="I8", kind=TypeKind.BASIC)
            if bt.I32() is not None: return Type(name="I32", kind=TypeKind.BASIC)
            if bt.I64() is not None: return Type(name="I64", kind=TypeKind.BASIC)
            if bt.U8() is not None: return Type(name="U8", kind=TypeKind.BASIC)
            if bt.U32() is not None: return Type(name="U32", kind=TypeKind.BASIC)
            if bt.U64() is not None: return Type(name="U64", kind=TypeKind.BASIC)
            if bt.F32() is not None: return Type(name="F32", kind=TypeKind.BASIC)
            if bt.F64() is not None: return Type(name="F64", kind=TypeKind.BASIC)
            if bt.STR() is not None: return Type(name="Str", kind=TypeKind.BASIC)
            if bt.BOOL() is not None: return Type(name="Bool", kind=TypeKind.BASIC)
            if bt.VOID() is not None: return Type(name="Void", kind=TypeKind.BASIC)
            if bt.TYPE_IDENTIFIER() is not None:
                name = bt.TYPE_IDENTIFIER().getText()
                generic_args = bt.genericArgs()
                if name == "Dict":
                    result = Type(name="Dict", kind=TypeKind.DICT)
                    if generic_args is not None:
                        args = list(generic_args.type_())
                        if len(args) >= 1:
                            result.key_type = self._get_type_from_ctx(args[0])
                        if len(args) >= 2:
                            result.value_type = self._get_type_from_ctx(args[1])
                    return result
                if name == "Meta" and generic_args is not None:
                    args = list(generic_args.type_())
                    value_type = self._get_type_from_ctx(args[0]) if args else Type(name="unknown", kind=TypeKind.BASIC)
                    meta_type = Type(name=f"Meta<{value_type}>", kind=TypeKind.STRUCT)
                    getter_type = Type(name="function", kind=TypeKind.FUNCTION)
                    getter_type.param_types = []
                    getter_type.param_names = []
                    getter_type.return_type = value_type
                    setter_type = Type(name="function", kind=TypeKind.FUNCTION)
                    setter_type.param_types = [value_type]
                    setter_type.param_names = ["value"]
                    setter_type.return_type = Type(name="Void", kind=TypeKind.BASIC)
                    meta_type.fields = {
                        "value": value_type,
                        "getter": getter_type,
                        "setter": setter_type,
                        "t": Type(name="Str", kind=TypeKind.BASIC),
                        "name": Type(name="Str", kind=TypeKind.BASIC),
                    }
                    return meta_type
                # 查找是否为已定义的结构体/别名或内置对象类型，直接返回完整类型信息
                resolved = self.symbols.resolve(name)
                if resolved and resolved.kind in (SymbolKind.STRUCT, SymbolKind.TYPE_ALIAS):
                    resolved_type = resolved.type
                    if resolved.kind == SymbolKind.STRUCT and generic_args is not None:
                        args = [self._get_type_from_ctx(t) for t in generic_args.type_()]
                        if None not in args:
                            return self._instantiate_struct_type(resolved_type, args)
                    return resolved_type
                builtin = builtin_type(name)
                if builtin is not None:
                    return builtin
                return Type(name=name, kind=TypeKind.BASIC)
            return Type(name="unknown", kind=TypeKind.BASIC)

        return None

    def _generic_names_from_type_list(self, type_list) -> list[str]:
        if type_list is None:
            return []
        return [type_ctx.getText() for type_ctx in type_list.type_()]

    def _generic_names_from_type(self, type_: Optional[Type]) -> list[str]:
        names = getattr(type_, "generic_params", None)
        return list(names) if names else []

    def _qualified_name(self, ctx) -> str:
        """读取支持点号命名空间的声明名。"""
        qname = ctx.qualifiedVarName() if hasattr(ctx, 'qualifiedVarName') else None
        if qname is None:
            token = ctx.VAR_IDENTIFIER() if hasattr(ctx, 'VAR_IDENTIFIER') else None
            name = token.getText() if token is not None else ""
        else:
            name = qname.getText()
        return self._import_alias_for(name)

    def _import_alias_for(self, name: str) -> str:
        for aliases in reversed(self._import_alias_stack):
            if name in aliases:
                return aliases[name]
        return name

    def _lock_policy_from_ctx(self, ctx) -> str:
        prefix = ctx.lockPrefix() if hasattr(ctx, 'lockPrefix') else None
        if prefix is None:
            return "ordered"
        if prefix.RP() is not None:
            return "read_preferred"
        if prefix.WP() is not None:
            return "write_preferred"
        return "ordered"

    def _is_placeholder_argument(self, expr_ctx) -> bool:
        """判断调用实参是否是完整的柯里化占位符 `?`。"""
        return expr_ctx is not None and expr_ctx.getText().strip() == '?'

    def _call_arg_items(self, arg_list_ctx) -> list[tuple[Optional[str], object]]:
        """返回调用实参；name 为 None 表示位置参数。"""
        if arg_list_ctx is None:
            return []
        if hasattr(arg_list_ctx, 'callArg'):
            items = []
            for arg in arg_list_ctx.callArg():
                named = arg.namedArg() if hasattr(arg, 'namedArg') else None
                if named is not None:
                    token = named.VAR_IDENTIFIER()
                    items.append((token.getText() if token is not None else None, named.expression()))
                else:
                    items.append((None, arg.expression() if hasattr(arg, 'expression') else None))
            return items
        return [
            (arg.VAR_IDENTIFIER().getText(), arg.expression())
            for arg in arg_list_ctx.namedArg()
            if arg.VAR_IDENTIFIER() is not None
        ]

    def _map_call_args_to_params(self, arg_list_ctx, expected_names: list[str], implicit_this: bool) -> tuple[dict[str, object], set[str], list[str]]:
        """把位置/具名调用参数映射到形参名，并返回占位符参数名和诊断。"""
        mapped: dict[str, object] = {}
        placeholders: set[str] = set()
        errors: list[str] = []
        positional_index = 1 if implicit_this and expected_names else 0
        seen_named = False
        for raw_name, expr_ctx in self._call_arg_items(arg_list_ctx):
            if raw_name is None:
                if seen_named:
                    errors.append("位置参数必须位于具名参数之前")
                if not expected_names:
                    continue
                if positional_index >= len(expected_names):
                    errors.append("位置参数数量过多")
                    continue
                arg_name = expected_names[positional_index]
                positional_index += 1
            else:
                seen_named = True
                arg_name = raw_name
            if arg_name in mapped:
                errors.append(f"重复提供参数 '{arg_name}'")
                continue
            if self._is_placeholder_argument(expr_ctx):
                placeholders.add(arg_name)
                mapped[arg_name] = Type(name="unknown", kind=TypeKind.BASIC)
                continue
            mapped[arg_name] = expr_ctx.accept(self) if expr_ctx is not None else None
        return mapped, placeholders, errors

    def _type_from_shape(self, shape_ctx) -> Type:
        """把匿名类型结构转换为结构体/字典语义类型。"""
        alias_type = Type(name="shape", kind=TypeKind.STRUCT)
        if shape_ctx is None:
            return alias_type
        members = list(shape_ctx.typeShapeMember())
        dynamic_members = [member for member in members if member.LBRACK() is not None]
        fixed_fields = self._shape_fixed_fields(shape_ctx)
        if dynamic_members:
            member = dynamic_members[0]
            field_types = member.type_()
            dict_type = Type(name="Dict", kind=TypeKind.DICT)
            if field_types and len(field_types) >= 1:
                dict_type.key_type = self._get_type_from_ctx(field_types[0])
            if field_types and len(field_types) >= 2:
                dict_type.value_type = self._get_type_from_ctx(field_types[-1])
            dict_type.fields.update(fixed_fields)
            return dict_type
        alias_type.fields.update(fixed_fields)
        return alias_type

    def _shape_fixed_fields(self, shape_ctx) -> dict[str, Type]:
        fields: dict[str, Type] = {}
        if shape_ctx is None:
            return fields
        for spread in shape_ctx.typeShapeSpread():
            spread_type = self._get_type_from_ctx(spread.type_())
            if spread_type is not None and spread_type.fields:
                for field_name, field_type in spread_type.fields.items():
                    fields.setdefault(field_name, field_type)
        for member in shape_ctx.typeShapeMember():
            if member.LBRACK() is not None or member.VAR_IDENTIFIER() is None:
                continue
            field_name = member.VAR_IDENTIFIER().getText()
            field_types = member.type_()
            fields[field_name] = self._get_type_from_ctx(field_types[-1]) if field_types else None
        return fields

    def _dict_field_name(self, field) -> Optional[str]:
        key_ctx = field.dictKey() if hasattr(field, 'dictKey') else None
        if key_ctx is None:
            return None
        if key_ctx.VAR_IDENTIFIER() is not None:
            return key_ctx.VAR_IDENTIFIER().getText()
        if key_ctx.STRING_LITERAL() is not None:
            return decode_string_literal_token(key_ctx.STRING_LITERAL().getText())
        return None

    def _with_expected_expr_type(self, expected: Optional[Type], expr_ctx) -> Optional[Type]:
        if expr_ctx is None:
            return None
        if expected is None:
            return expr_ctx.accept(self)
        self._expected_expr_type_stack.append(expected)
        try:
            return expr_ctx.accept(self)
        finally:
            self._expected_expr_type_stack.pop()

    def _expected_expr_type(self) -> Optional[Type]:
        return self._expected_expr_type_stack[-1] if self._expected_expr_type_stack else None

    def _infer_literal_type(self, ctx) -> Optional[Type]:
        """从字面量推导类型"""
        if ctx.INTEGER_LITERAL() is not None:
            try:
                value = int(ctx.INTEGER_LITERAL().getText(), 0)
            except ValueError:
                return Type(name="I32", kind=TypeKind.BASIC)
            return Type(name="I32" if -(2 ** 31) <= value <= (2 ** 31 - 1) else "I64", kind=TypeKind.BASIC)
        if ctx.FLOAT_LITERAL() is not None:
            return Type(name="F64", kind=TypeKind.BASIC)
        if ctx.STRING_LITERAL() is not None:
            text = decode_string_literal_token(ctx.STRING_LITERAL().getText())
            for match in re.finditer(r"\{\{(.+?)\}\}", text):
                expr_text = match.group(1).strip()
                expr_type = self._analyze_interpolation_expr(expr_text, ctx.start.line)
                if expr_type is None:
                    continue
                if expr_type.name != "Str":
                    self.symbols.add_error(f"行 {ctx.start.line}: 字符串插值表达式 '{expr_text}' 必须是 Str，实际为 '{expr_type}'")
            return Type(name="Str", kind=TypeKind.BASIC)
        if ctx.BOOL_LITERAL() is not None:
            return Type(name="Bool", kind=TypeKind.BASIC)
        return None

    def _analyze_interpolation_expr(self, expr_text: str, line: int) -> Optional[Type]:
        """按 EzLang 表达式语法分析字符串插值内部表达式。"""
        if not expr_text:
            self.symbols.add_error(f"行 {line}: 字符串插值表达式不能为空")
            return None
        stream = CommonTokenStream(EzLangLexer(InputStream(expr_text)))
        parser = EzLangParser(stream)
        parser.removeErrorListeners()
        expr = parser.expression()
        if parser.getNumberOfSyntaxErrors() > 0 or stream.LA(1) != Token.EOF:
            self.symbols.add_error(f"行 {line}: 字符串插值表达式语法错误: '{expr_text}'")
            return None
        return expr.accept(self)

    def _union_payload_type(self, type_: Type) -> Optional[Type]:
        """返回当前联合运行时 value 槽采用的语义类型。"""
        if type_.kind != TypeKind.UNION or not type_.union_types:
            return None
        width = {
            "Bool": 1,
            "I8": 1,
            "U8": 1,
            "I32": 4,
            "U32": 4,
            "F32": 4,
            "I64": 8,
            "U64": 8,
            "F64": 8,
            "Str": 8,
        }
        return max(type_.union_types, key=lambda t: width.get(t.name, 8) if t is not None else 0)

    def _check_type_compat(self, expected: Optional[Type], actual: Optional[Type],
                           ctx, msg_prefix: str = "类型") -> bool:
        """检查类型兼容性，不兼容时添加错误"""
        if expected is None or actual is None:
            return True
        if expected.name == "unknown" or actual.name == "unknown":
            return True
        if not expected.compatible_with(actual):
            line = ctx.start.line if hasattr(ctx, 'start') else 0
            self.symbols.add_error(
                f"行 {line}: {msg_prefix}不匹配：期望 '{expected}'，实际 '{actual}'"
            )
            return False
        return True

    def _check_return_type_set(self, return_types: list[Optional[Type]], ctx, label: str) -> None:
        """检查表达式块内多个 return 的类型是否一致。"""
        concrete = [t for t in return_types if t is not None and t.name != "unknown"]
        if not concrete:
            return
        expected = concrete[0]
        for actual in concrete[1:]:
            if expected.compatible_with(actual) or actual.compatible_with(expected):
                continue
            line = ctx.start.line if hasattr(ctx, 'start') else 0
            self.symbols.add_error(
                f"行 {line}: {label} 返回类型不一致：期望 '{expected}'，实际 '{actual}'"
            )
            return

    def _check_binary_op(self, left_type: Optional[Type], right_type: Optional[Type],
                         ctx, op_name: str) -> Optional[Type]:
        """检查二元运算类型，返回结果类型"""
        if left_type is None or right_type is None:
            return None
        if not left_type.compatible_with(right_type):
            line = ctx.start.line if hasattr(ctx, 'start') else 0
            self.symbols.add_error(
                f"行 {line}: 二元运算 '{op_name}' 类型不匹配：'{left_type}' 和 '{right_type}'"
            )
            return Type(name="unknown", kind=TypeKind.BASIC)
        return left_type  # 运算结果类型与操作数相同

    @staticmethod
    def _has_token(ctx, name: str) -> bool:
        """兼容 ANTLR 单 token 和重复 token 访问器。"""
        if not hasattr(ctx, name):
            return False
        token = getattr(ctx, name)()
        if isinstance(token, list):
            return len(token) > 0
        return token is not None

    def _make_vec_type(self, element_type: Type, size: int) -> Type:
        """构造 SIMD 向量类型。"""
        result = Type(kind=TypeKind.VEC, name=f"Vec<{element_type.name}>[{size}]")
        result.element_type = element_type
        result.vec_size = size
        return result

    def _is_numeric_vec(self, type_: Optional[Type]) -> bool:
        return (
            type_ is not None
            and type_.kind == TypeKind.VEC
            and type_.element_type is not None
            and type_.element_type.is_numeric()
        )

    def _is_integer_vec(self, type_: Optional[Type]) -> bool:
        return (
            type_ is not None
            and type_.kind == TypeKind.VEC
            and type_.element_type is not None
            and type_.element_type.is_integer()
        )

    def _is_mask_vec(self, type_: Optional[Type]) -> bool:
        return (
            type_ is not None
            and type_.kind == TypeKind.VEC
            and type_.element_type is not None
            and type_.element_type.is_bool()
        )

    def _vec_binary_type(self, left_type: Type, right_type: Type, ctx, op_text: str,
                         comparison: bool = False) -> Optional[Type]:
        """检查 SIMD 向量二元运算，支持标量广播。"""
        left_vec = left_type.kind == TypeKind.VEC
        right_vec = right_type.kind == TypeKind.VEC
        if not left_vec and not right_vec:
            return None

        vector_type = left_type if left_vec else right_type
        scalar_type = None if left_vec and right_vec else (right_type if left_vec else left_type)
        line = ctx.start.line if hasattr(ctx, 'start') else 0
        elem_type = vector_type.element_type
        if elem_type is None:
            return Type(name="unknown", kind=TypeKind.BASIC)

        if left_vec and right_vec:
            if left_type.vec_size != right_type.vec_size:
                self.symbols.add_error(
                    f"行 {line}: SIMD 向量长度不匹配：'{left_type}' 和 '{right_type}'"
                )
                return Type(name="unknown", kind=TypeKind.BASIC)
            if left_type.element_type != right_type.element_type:
                self.symbols.add_error(
                    f"行 {line}: SIMD 向量元素类型不匹配：'{left_type}' 和 '{right_type}'"
                )
                return Type(name="unknown", kind=TypeKind.BASIC)
        elif scalar_type is not None:
            same_numeric_family = (
                elem_type.is_integer() and scalar_type.is_integer()
            ) or (
                elem_type.is_float() and scalar_type.is_float()
            )
            if not same_numeric_family:
                self.symbols.add_error(
                    f"行 {line}: SIMD 向量与标量类型不匹配：'{vector_type}' 和 '{scalar_type}'"
                )
                return Type(name="unknown", kind=TypeKind.BASIC)

        op_is_shift = op_text in {"<<", ">>"}
        op_is_bitwise = op_text in {"&", "|", "^"}
        op_is_arithmetic = op_text in {"+", "-", "*", "/", "%"}

        if comparison:
            if not self._is_numeric_vec(vector_type):
                self.symbols.add_error(f"行 {line}: SIMD 向量比较要求数值元素类型，实际为 '{vector_type}'")
                return Type(name="unknown", kind=TypeKind.BASIC)
            return self._make_vec_type(Type(name="Bool", kind=TypeKind.BASIC), vector_type.vec_size)

        if op_is_arithmetic and not self._is_numeric_vec(vector_type):
            self.symbols.add_error(f"行 {line}: SIMD 向量算术运算要求数值元素类型，实际为 '{vector_type}'")
            return Type(name="unknown", kind=TypeKind.BASIC)
        if op_is_shift and not self._is_integer_vec(vector_type):
            self.symbols.add_error(f"行 {line}: SIMD 向量移位要求整数元素类型，实际为 '{vector_type}'")
            return Type(name="unknown", kind=TypeKind.BASIC)
        if op_is_bitwise and not (self._is_integer_vec(vector_type) or self._is_mask_vec(vector_type)):
            self.symbols.add_error(f"行 {line}: SIMD 向量位运算要求整数或布尔掩码元素类型，实际为 '{vector_type}'")
            return Type(name="unknown", kind=TypeKind.BASIC)
        if not (op_is_arithmetic or op_is_shift or op_is_bitwise):
            self.symbols.add_error(f"行 {line}: SIMD 向量不支持运算符 '{op_text}'")
            return Type(name="unknown", kind=TypeKind.BASIC)
        return vector_type

    def _is_unsigned_shift_rhs_type(self, type_: Optional[Type]) -> bool:
        if type_ is None or type_.name == "unknown":
            return True
        if type_.kind == TypeKind.VEC and type_.element_type is not None:
            return type_.element_type.name in {"U8", "U32", "U64"}
        return type_.is_integer() and type_.name in {"U8", "U32", "U64"}

    def _is_shift_lhs_type(self, type_: Optional[Type]) -> bool:
        if type_ is None or type_.name == "unknown":
            return True
        if type_.kind == TypeKind.VEC:
            return self._is_integer_vec(type_)
        return type_.is_integer()

    def _get_lvalue_name(self, ctx) -> Optional[str]:
        """从赋值表达式左侧的 pipelineExpression 获取被赋值的变量名"""

        def _find_identifier(node) -> Optional[str]:
            if hasattr(node, 'VAR_IDENTIFIER') and node.VAR_IDENTIFIER() is not None:
                return node.VAR_IDENTIFIER().getText()
            if hasattr(node, 'TYPE_IDENTIFIER') and node.TYPE_IDENTIFIER() is not None:
                return node.TYPE_IDENTIFIER().getText()
            if hasattr(node, 'getChildCount'):
                for i in range(node.getChildCount()):
                    result = _find_identifier(node.getChild(i))
                    if result:
                        return result
            return None

        return _find_identifier(ctx.pipelineExpression())

    def _get_lvalue_owner_name(self, ctx) -> Optional[str]:
        """读取左值所属的基变量名，用于 const 可变性检查。"""
        left = ctx.pipelineExpression() if hasattr(ctx, 'pipelineExpression') else ctx
        ident = self._leftmost_identifier_ctx(left)
        if ident is None:
            return None
        token = ident.VAR_IDENTIFIER() or ident.TYPE_IDENTIFIER()
        return token.getText() if token is not None else None

    def _get_identifier_text(self, ctx) -> str:
        """从标识符上下文获取名称（支持 VAR_IDENTIFIER 和 TYPE_IDENTIFIER）"""
        if hasattr(ctx, 'VAR_IDENTIFIER') and ctx.VAR_IDENTIFIER() is not None:
            return ctx.VAR_IDENTIFIER().getText()
        if hasattr(ctx, 'TYPE_IDENTIFIER') and ctx.TYPE_IDENTIFIER() is not None:
            return ctx.TYPE_IDENTIFIER().getText()
        return ""

    def _field_name_text(self, ctx) -> str:
        token = ctx.VAR_IDENTIFIER() if hasattr(ctx, 'VAR_IDENTIFIER') else None
        return token.getText() if token is not None else ""

    def _is_in_flow(self) -> bool:
        return self.flow_depth > 0

    def _is_in_parallel(self) -> bool:
        return self.parallel_depth > 0

    def _record_flow_dependency(self, name: str, ctx):
        if not self._is_in_flow():
            return
        deps = []
        seen = set()
        for read_name in self._current_expr_reads:
            if read_name in self._flow_suspend_values and read_name not in seen:
                deps.append(read_name)
                seen.add(read_name)
        if self._last_suspend_call is not None:
            self.flow_dependencies.append({
                "name": name,
                "source": self._last_suspend_call["name"],
                "depends_on": deps,
                "line": ctx.start.line,
            })
            self._flow_suspend_values[name] = self._last_suspend_call
        elif deps:
            self.flow_dependencies.append({
                "name": name,
                "source": None,
                "depends_on": deps,
                "line": ctx.start.line,
            })

    def _get_call_name(self, ctx) -> Optional[str]:
        if hasattr(ctx, 'primaryExpression') and ctx.primaryExpression() is not None:
            primary = ctx.primaryExpression()
            if hasattr(primary, 'VAR_IDENTIFIER') and primary.VAR_IDENTIFIER() is not None:
                return primary.VAR_IDENTIFIER().getText()
            if hasattr(primary, 'TYPE_IDENTIFIER') and primary.TYPE_IDENTIFIER() is not None:
                return primary.TYPE_IDENTIFIER().getText()
        if hasattr(ctx, 'postfixExpression') and ctx.postfixExpression() is not None:
            return self._get_call_name(ctx.postfixExpression())
        return None

    def _replace_generic_type(self, type_: Optional[Type], type_map: dict[str, Type]) -> Optional[Type]:
        """用推导出的具体类型替换泛型参数类型。"""
        if type_ is None:
            return None
        if type_.kind == TypeKind.BASIC and type_.name in type_map:
            return type_map[type_.name]
        result = Type(name=type_.name, kind=type_.kind)
        result.is_optional = type_.is_optional
        result.is_union = type_.is_union
        result.element_type = self._replace_generic_type(type_.element_type, type_map)
        result.key_type = self._replace_generic_type(type_.key_type, type_map)
        result.value_type = self._replace_generic_type(type_.value_type, type_map)
        result.vec_size = type_.vec_size
        result.param_types = [self._replace_generic_type(t, type_map) for t in type_.param_types]
        result.param_names = list(type_.param_names)
        result.default_param_names = set(type_.default_param_names)
        result.return_type = self._replace_generic_type(type_.return_type, type_map)
        result.union_types = [self._replace_generic_type(t, type_map) for t in type_.union_types]
        result.fields = {name: self._replace_generic_type(field_type, type_map) for name, field_type in type_.fields.items()}
        result.pointee_type = self._replace_generic_type(type_.pointee_type, type_map)
        if hasattr(type_, 'generic_base'):
            result.generic_base = type_.generic_base
        if hasattr(type_, 'type_args'):
            result.type_args = [self._replace_generic_type(t, type_map) for t in type_.type_args]
        return result

    def _instantiate_struct_type(self, struct_type: Type, type_args: list[Type]) -> Type:
        """按显式类型参数实例化泛型结构体字段类型。"""
        generic_names = self.struct_generic_params.get(struct_type.name, [])
        if not generic_names or len(generic_names) != len(type_args):
            return struct_type
        type_map = dict(zip(generic_names, type_args))
        result = Type(
            name=f"{struct_type.name}<" + ", ".join(str(t) for t in type_args) + ">",
            kind=TypeKind.STRUCT,
        )
        result.generic_base = struct_type.name
        result.type_args = list(type_args)
        result.fields = {
            field_name: self._replace_generic_type(field_type, type_map)
            for field_name, field_type in struct_type.fields.items()
        }
        return result

    def _function_type_from_fn_like(self, fn_like) -> Type:
        """从结构体方法签名/函数字面量提取函数类型。"""
        func_type = Type(name="function", kind=TypeKind.FUNCTION)
        func_type.return_type = self._get_type_from_ctx(fn_like.type_()) if fn_like.type_() is not None else None
        params = fn_like.paramList()
        if params is not None:
            for param in params.param():
                func_type.param_names.append(param.VAR_IDENTIFIER().getText())
                func_type.param_types.append(self._get_type_from_ctx(param.type_()) if param.type_() is not None else None)
                if param.expression() is not None:
                    func_type.default_param_names.add(param.VAR_IDENTIFIER().getText())
        return func_type

    def _method_type_for_struct(self, struct_type: Type, method_name: str) -> Optional[Type]:
        base_name = getattr(struct_type, 'generic_base', struct_type.name)
        methods = self.struct_method_types.get(base_name, {})
        method_type = methods.get(method_name)
        if method_type is None:
            builtin = builtin_type(base_name)
            builtin_methods = getattr(builtin, 'methods', {}) if builtin is not None else {}
            method_type = builtin_methods.get(method_name)
        if method_type is None:
            return None
        generic_names = self.struct_generic_params.get(base_name, [])
        type_args = getattr(struct_type, 'type_args', [])
        if generic_names and len(type_args) == len(generic_names):
            return self._replace_generic_type(method_type, dict(zip(generic_names, type_args)))
        return method_type

    def _is_weak_this_param(self, func_type: Optional[Type], index: int = 0) -> bool:
        """判断函数指定参数是否是规范的弱引用 this 参数。"""
        if func_type is None or func_type.kind != TypeKind.FUNCTION:
            return False
        if index >= len(func_type.param_names) or func_type.param_names[index] != "this":
            return False
        if index >= len(func_type.param_types):
            return False
        param_type = func_type.param_types[index]
        return param_type is not None and param_type.kind == TypeKind.WEAK_REF

    def _collection_method_type(self, receiver_type: Optional[Type], method_name: str) -> Optional[Type]:
        """List/Dict 的对象方法糖类型：nums.push(...) / dict.has(...)。"""
        if receiver_type is None:
            return None
        if receiver_type.kind in (TypeKind.ARRAY, TypeKind.LIST):
            item = receiver_type.element_type or Type(name="unknown", kind=TypeKind.BASIC)
            result = Type(name="function", kind=TypeKind.FUNCTION)
            if method_name in {"push", "unshift"}:
                result.param_names = ["item"]
                result.param_types = [item]
                result.return_type = Type(name="Void", kind=TypeKind.BASIC)
                return result
            if method_name in {"pop", "shift"}:
                result.return_type = Type(kind=TypeKind.OPTIONAL, name=f"{item.name}?")
                result.return_type.element_type = item
                return result
            if method_name == "len":
                result.return_type = Type(name="I64", kind=TypeKind.BASIC)
                return result
            if method_name == "slice":
                result.param_names = ["start", "end"]
                result.param_types = [Type(name="I64", kind=TypeKind.BASIC), Type(name="I64", kind=TypeKind.BASIC)]
                result.return_type = receiver_type
                return result
            if method_name == "sort":
                cmp_type = Type(name="function", kind=TypeKind.FUNCTION)
                cmp_type.param_names = ["a", "b"]
                cmp_type.param_types = [item, item]
                cmp_type.return_type = Type(name="I32", kind=TypeKind.BASIC)
                result.param_names = ["cmp"]
                result.param_types = [cmp_type]
                result.return_type = Type(name="Void", kind=TypeKind.BASIC)
                return result
            if method_name in {"filter", "find"}:
                pred_type = Type(name="function", kind=TypeKind.FUNCTION)
                pred_type.param_names = ["item"]
                pred_type.param_types = [item]
                pred_type.return_type = Type(name="Bool", kind=TypeKind.BASIC)
                result.param_names = ["pred"]
                result.param_types = [pred_type]
                if method_name == "filter":
                    result.return_type = receiver_type
                else:
                    result.return_type = Type(kind=TypeKind.OPTIONAL, name=f"{item.name}?")
                    result.return_type.element_type = item
                return result
            if method_name == "map":
                mapped = Type(name="unknown", kind=TypeKind.BASIC)
                map_type = Type(name="function", kind=TypeKind.FUNCTION)
                map_type.param_names = ["item"]
                map_type.param_types = [item]
                map_type.return_type = mapped
                result.param_names = ["f"]
                result.param_types = [map_type]
                result.return_type = Type(kind=TypeKind.LIST, name=f"List<{mapped.name}>")
                result.return_type.element_type = mapped
                return result
        if receiver_type.kind == TypeKind.DICT:
            key = receiver_type.key_type or Type(name="unknown", kind=TypeKind.BASIC)
            value = receiver_type.value_type or Type(name="unknown", kind=TypeKind.BASIC)
            result = Type(name="function", kind=TypeKind.FUNCTION)
            if method_name in {"has", "delete"}:
                result.param_names = ["key"]
                result.param_types = [key]
                result.return_type = Type(name="Bool", kind=TypeKind.BASIC)
                return result
            if method_name == "len":
                result.return_type = Type(name="I64", kind=TypeKind.BASIC)
                return result
            if method_name == "keys":
                result.return_type = Type(kind=TypeKind.LIST, name=f"List<{key.name}>")
                result.return_type.element_type = key
                return result
            if method_name == "values":
                result.return_type = Type(kind=TypeKind.LIST, name=f"List<{value.name}>")
                result.return_type.element_type = value
                return result
        return None

    def _bind_generic_type(self, expected: Optional[Type], actual: Optional[Type], type_map: dict[str, Type]) -> None:
        """根据形参类型和实参类型推导泛型参数。"""
        if expected is None or actual is None:
            return
        if expected.kind == TypeKind.BASIC and expected.name in self._current_generic_names:
            type_map.setdefault(expected.name, actual)
            return
        if expected.element_type is not None:
            self._bind_generic_type(expected.element_type, actual.element_type, type_map)
        if expected.key_type is not None:
            self._bind_generic_type(expected.key_type, actual.key_type, type_map)
        if expected.value_type is not None:
            self._bind_generic_type(expected.value_type, actual.value_type, type_map)
        if expected.pointee_type is not None:
            self._bind_generic_type(expected.pointee_type, actual.pointee_type, type_map)

    def _infer_struct_type_args_from_fields(self, struct_type: Type, init_list) -> list[Type] | None:
        """根据结构体字段初始化值推导泛型结构体类型实参。"""
        generic_names = self.struct_generic_params.get(struct_type.name, [])
        if not generic_names or init_list is None:
            return None
        self._current_generic_names = set(generic_names)
        type_map: dict[str, Type] = {}
        for init in init_list.structFieldInit():
            if init.ELLIPSIS() is not None or init.expression() is None:
                continue
            fname = self._field_name_text(init)
            expected = struct_type.fields.get(fname)
            actual = init.expression().accept(self)
            self._bind_generic_type(expected, actual, type_map)
        self._current_generic_names = set()
        if any(name not in type_map for name in generic_names):
            return None
        return [type_map[name] for name in generic_names]

    def _generic_template_param_names(self, call_name: str) -> list[str]:
        template = self.generic_templates.get(call_name)
        if template is None or len(template) < 2:
            return []
        template_ctx = template[1]
        if hasattr(template_ctx, 'paramTypeList'):
            params = template_ctx.paramTypeList()
            if params is not None:
                return [param.VAR_IDENTIFIER().getText() for param in params.paramType()]
        if not hasattr(template_ctx, 'functionLiteral'):
            return []
        fn = template_ctx.functionLiteral()
        if fn is None or fn.paramList() is None:
            return []
        return [param.VAR_IDENTIFIER().getText() for param in fn.paramList().param()]

    def _explicit_generic_call_type_map(self, call_name: str, call_ctx, gen_names: list[str]) -> dict[str, Type]:
        ident = self._leftmost_identifier_ctx(call_ctx.postfixExpression()) if call_ctx is not None else None
        if ident is None or ident.genericArgs() is None:
            return {}
        type_arg_ctxs = list(ident.genericArgs().type_())
        if len(type_arg_ctxs) != len(gen_names):
            return {}
        type_args = [self._get_type_from_ctx(t) for t in type_arg_ctxs]
        return {
            gen_name: type_arg
            for gen_name, type_arg in zip(gen_names, type_args)
            if type_arg is not None
        }

    def _infer_generic_template_return_type(
        self,
        call_name: str,
        type_map: dict[str, Type],
        named_args: dict[str, Optional[Type]],
    ) -> Optional[Type]:
        template = self.generic_templates.get(call_name)
        if template is None or len(template) < 2:
            return None
        template_ctx = template[1]
        if not hasattr(template_ctx, 'functionLiteral'):
            return None
        fn = template_ctx.functionLiteral()
        if fn is None:
            return None
        if fn.type_() is not None:
            return self._replace_generic_type(self._get_type_from_ctx(fn.type_()), type_map)
        if fn.expression() is None:
            return None

        prev_return = self.current_function_return
        prev_in_func = self.in_function
        prev_parallel_return_stack = self._parallel_return_stack
        prev_decl_name = self._current_decl_name
        prev_reads = self._current_expr_reads
        prev_suspend = self._last_suspend_call
        self.current_function_return = None
        self.in_function = True
        self._parallel_return_stack = []
        self._current_decl_name = None
        self._current_expr_reads = []
        self._last_suspend_call = None
        self.symbols.push_scope(f"{call_name}<infer>")
        try:
            params = fn.paramList()
            if params is not None:
                for param in params.param():
                    pname = param.VAR_IDENTIFIER().getText()
                    param_type = self._get_type_from_ctx(param.type_()) if param.type_() is not None else None
                    concrete_type = self._replace_generic_type(param_type, type_map)
                    if concrete_type is None:
                        concrete_type = named_args.get(pname)
                    self.symbols.define(Symbol(pname, SymbolKind.PARAM, concrete_type, line=param.start.line))
            inferred = fn.expression().accept(self)
            return self._replace_generic_type(inferred, type_map)
        finally:
            self.symbols.pop_scope()
            self._last_suspend_call = prev_suspend
            self._current_expr_reads = prev_reads
            self._current_decl_name = prev_decl_name
            self._parallel_return_stack = prev_parallel_return_stack
            self.in_function = prev_in_func
            self.current_function_return = prev_return

    def _infer_generic_function_type(
        self,
        call_name: Optional[str],
        target_type: Optional[Type],
        named_args: dict[str, Optional[Type]],
        call_ctx=None,
    ) -> Optional[Type]:
        if call_name is None or target_type is None or call_name not in self.generic_templates:
            return target_type
        gen_names, _ = self.generic_templates[call_name]
        self._current_generic_names = set(gen_names)
        type_map: dict[str, Type] = self._explicit_generic_call_type_map(call_name, call_ctx, gen_names)
        for index, pname in enumerate(target_type.param_names):
            if pname not in named_args or index >= len(target_type.param_types):
                continue
            self._bind_generic_type(target_type.param_types[index], named_args[pname], type_map)
        self._current_generic_names = set()
        if not type_map:
            return target_type
        inferred = Type(name="function", kind=TypeKind.FUNCTION)
        inferred.return_type = self._replace_generic_type(target_type.return_type, type_map)
        if inferred.return_type is None:
            inferred.return_type = self._infer_generic_template_return_type(call_name, type_map, named_args)
        inferred.param_types = [self._replace_generic_type(t, type_map) for t in target_type.param_types]
        inferred.param_names = list(target_type.param_names)
        inferred.default_param_names = set(target_type.default_param_names)
        return inferred

    def _curried_function_type(self, target_type: Type, placeholder_names: set[str]) -> Type:
        """根据占位参数生成柯里化后的函数类型。"""
        result = Type(name="function", kind=TypeKind.FUNCTION)
        result.return_type = target_type.return_type
        for index, pname in enumerate(target_type.param_names):
            if pname not in placeholder_names:
                continue
            result.param_names.append(pname)
            if index < len(target_type.param_types):
                result.param_types.append(target_type.param_types[index])
        return result

    # ==================== 声明访问 ====================

    def visitVariableDecl(self, ctx: EzLangParser.VariableDeclContext):
        """处理变量声明: let/const/static name: Type = expr"""
        name = self._qualified_name(ctx)
        kind = SymbolKind.VARIABLE
        mutable = True
        lock_policy = self._lock_policy_from_ctx(ctx)

        if ctx.LET() is not None:
            kind = SymbolKind.VARIABLE
            mutable = True
        elif ctx.CONST() is not None:
            kind = SymbolKind.CONSTANT
            mutable = False
        elif ctx.STATIC() is not None:
            kind = SymbolKind.STATIC
            mutable = True

        # 获取类型注解
        type_ctx = ctx.type_()
        annotated_type = self._get_type_from_ctx(type_ctx) if type_ctx is not None else None

        # 检查类型引用
        if annotated_type and annotated_type.kind == TypeKind.BASIC \
                and annotated_type.name not in ("I8", "I32", "I64", "U8", "U32", "U64",
                                                 "F32", "F64", "Str", "Bool", "Void",
                                                 "Vec", "List", "Dict", "unknown"):
            resolved = self.symbols.resolve(annotated_type.name)
            if resolved is None:
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 类型 '{annotated_type.name}' 未定义"
                )

        # 分析初始化表达式并推导类型
        expr = ctx.expression()
        inferred_type = None
        prev_decl_name = self._current_decl_name
        prev_reads = self._current_expr_reads
        prev_suspend = self._last_suspend_call
        self._current_decl_name = name
        self._current_expr_reads = []
        self._last_suspend_call = None
        if expr is not None:
            inferred_type = self._with_expected_expr_type(annotated_type, expr)
        self._record_flow_dependency(name, ctx)
        self._current_decl_name = prev_decl_name
        self._current_expr_reads = prev_reads
        self._last_suspend_call = prev_suspend

        # 类型检查：标注类型 vs 推导类型
        if annotated_type is None and inferred_type is not None:
            annotated_type = inferred_type  # 类型推导
        elif annotated_type is not None and inferred_type is not None:
            self._check_type_compat(annotated_type, inferred_type, ctx, "变量初始化类型")

        symbol = Symbol(name, kind, annotated_type, mutable=mutable, line=ctx.start.line, lock_policy=lock_policy)
        self.symbols.define(symbol)
        if lock_policy != "ordered":
            self.locked_variables[name] = lock_policy
        return None

    def visitStructDecl(self, ctx: EzLangParser.StructDeclContext):
        """处理结构体声明: struct Name<T> { ... }"""
        name = self._import_alias_for(ctx.TYPE_IDENTIFIER().getText())
        struct_type = Type(name=name, kind=TypeKind.STRUCT)
        if ctx.genericParams() is not None:
            self.struct_generic_params[name] = [t.getText() for t in ctx.genericParams().TYPE_IDENTIFIER()]
        symbol = Symbol(name, SymbolKind.STRUCT, struct_type, line=ctx.start.line)
        self.symbols.define(symbol)

        self.current_struct = name
        self.symbols.push_scope(name)

        for member in ctx.structMember():
            member.accept(self)

        # 从子作用域收集字段类型，存入结构体类型
        struct_scope = self.symbols.current_scope
        for sym_name, sym in struct_scope.symbols.items():
            if sym.kind == SymbolKind.VARIABLE:
                struct_type.fields[sym_name] = sym.type

        self.symbols.pop_scope()
        self.current_struct = None
        return None

    def visitStructField(self, ctx: EzLangParser.StructFieldContext):
        """处理结构体字段"""
        name = self._field_name_text(ctx)
        type_ctx = ctx.type_()
        type_ = self._get_type_from_ctx(type_ctx) if type_ctx is not None else None
        symbol = Symbol(name, SymbolKind.VARIABLE, type_, mutable=True, line=ctx.start.line)
        self.symbols.define(symbol)
        if self.current_struct:
            struct_symbol = self.symbols.global_scope.resolve(self.current_struct)
            if struct_symbol is not None and struct_symbol.type is not None:
                struct_symbol.type.fields[name] = type_
        return None

    def visitStructMethod(self, ctx: EzLangParser.StructMethodContext):
        """处理结构体方法 — 检查 this 参数绑定"""
        name = self._field_name_text(ctx)
        symbol = Symbol(name, SymbolKind.FUNCTION, Type(name="function", kind=TypeKind.FUNCTION),
                       line=ctx.start.line)
        self.symbols.define(symbol)

        fn = ctx.functionLiteral()
        sig = ctx.functionSignature()
        fn_like = fn or sig
        if self.current_struct and fn_like is not None:
            self.struct_method_types.setdefault(self.current_struct, {})[name] = self._function_type_from_fn_like(fn_like)
        if fn_like is not None:
            # 首参名为 this 时按实例方法校验；没有 this 的结构体方法视为类型级方法。
            params = fn_like.paramList()
            if params is not None and len(params.param()) > 0:
                first_param = params.param(0)
                pname = first_param.VAR_IDENTIFIER().getText()
                if pname == 'this' and self.current_struct and first_param.type_() is not None:
                    param_type = self._get_type_from_ctx(first_param.type_())
                    if param_type is not None and param_type.kind != TypeKind.WEAK_REF:
                        self.symbols.add_error(
                            f"行 {ctx.start.line}: 方法 'this' 参数必须是弱引用类型 '#{self.current_struct}'，"
                            f"实际为 '{param_type}'"
                        )
                    elif param_type is not None:
                        referent = param_type.referent_type or param_type.element_type
                        param_base = getattr(referent, 'generic_base', referent.name if referent else None)
                        if referent and param_base != self.current_struct and referent.name != "unknown":
                            self.symbols.add_error(
                                f"行 {ctx.start.line}: 方法 'this' 参数类型应为 '#{self.current_struct}'，"
                                f"实际为 '{param_type}'"
                            )

            self.symbols.push_scope(name)
            if params is not None:
                for param in params.param():
                    param.accept(self)
            prev_return = self.current_function_return
            prev_in_func = self.in_function
            prev_parallel_return_stack = self._parallel_return_stack
            self.current_function_return = self._get_type_from_ctx(fn_like.type_()) if fn_like.type_() is not None else None
            self.in_function = True
            self._parallel_return_stack = []
            if fn is not None and fn.expression() is not None:
                fn.expression().accept(self)
            elif fn is not None and fn.block() is not None:
                fn.block().accept(self)
            self._parallel_return_stack = prev_parallel_return_stack
            self.in_function = prev_in_func
            self.current_function_return = prev_return
            self.symbols.pop_scope()
        return None

    def visitStructSpread(self, ctx: EzLangParser.StructSpreadContext):
        """处理结构体展开 ...BaseType"""
        type_ctx = ctx.type_()
        if type_ctx is not None:
            type_ = self._get_type_from_ctx(type_ctx)
            if type_:
                resolved = self.symbols.resolve(type_.name)
                if resolved is None or resolved.kind != SymbolKind.STRUCT:
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 展开类型 '{type_.name}' 必须是已定义的结构体"
                    )
        return None

    def visitTypeAliasDecl(self, ctx: EzLangParser.TypeAliasDeclContext):
        """处理类型别名: type Name = ... """
        name = self._import_alias_for(ctx.TYPE_IDENTIFIER().getText())
        alias_type = Type(name=name, kind=TypeKind.STRUCT)

        shape = ctx.typeShape()
        if shape is not None:
            alias_type = self._type_from_shape(shape)
            alias_type.name = name
        elif ctx.type_() is not None:
            alias_type = self._get_type_from_ctx(ctx.type_()) or Type(name=name, kind=TypeKind.BASIC)
            alias_type.name = name

        symbol = Symbol(name, SymbolKind.TYPE_ALIAS, alias_type, line=ctx.start.line)
        self.symbols.define(symbol)
        return None

    def visitFunctionDecl(self, ctx: EzLangParser.FunctionDeclContext):
        """处理函数声明: let/const name = (...) => ..."""
        name = self._import_alias_for(ctx.VAR_IDENTIFIER().getText())
        kind = SymbolKind.CONSTANT if ctx.CONST() is not None else SymbolKind.FUNCTION

        fn = ctx.functionLiteral()
        ret_type = None
        param_types = []
        param_names = []
        default_param_names = set()
        if fn is not None:
            ret_ctx = fn.type_()
            if ret_ctx is not None:
                ret_type = self._get_type_from_ctx(ret_ctx)
            params = fn.paramList()
            if params is not None:
                for param in params.param():
                    pt = self._get_type_from_ctx(param.type_()) if param.type_() is not None else None
                    param_types.append(pt)
                    param_name = param.VAR_IDENTIFIER().getText()
                    param_names.append(param_name)
                    if param.expression() is not None:
                        default_param_names.add(param_name)

        func_type = Type(name="function", kind=TypeKind.FUNCTION)
        func_type.return_type = ret_type
        func_type.param_types = param_types
        func_type.param_names = param_names
        func_type.default_param_names = default_param_names
        symbol = Symbol(name, kind, func_type, line=ctx.start.line)
        self.symbols.define(symbol)

        # 收集泛型参数（可能出现在 functionDecl 或 functionLiteral 上）
        gen_params = ctx.genericParams()
        if gen_params is None and fn is not None:
            gen_params = fn.genericParams()
        if gen_params is not None:
            gen_names = [t.getText() for t in gen_params.TYPE_IDENTIFIER()]
            self.generic_templates[name] = (gen_names, ctx)

        # 分析函数体
        if fn is not None:
            self.symbols.push_scope(name)
            prev_return = self.current_function_return
            prev_in_func = self.in_function
            prev_parallel_return_stack = self._parallel_return_stack
            self.current_function_return = ret_type
            self.in_function = True
            self._parallel_return_stack = []
            params = fn.paramList()
            if params is not None:
                for param in params.param():
                    param.accept(self)
            if fn.expression() is not None:
                fn.expression().accept(self)
            elif fn.block() is not None:
                fn.block().accept(self)
            self._parallel_return_stack = prev_parallel_return_stack
            self.in_function = prev_in_func
            self.current_function_return = prev_return
            self.symbols.pop_scope()
        return None

    def visitParam(self, ctx: EzLangParser.ParamContext):
        """处理函数参数"""
        name = ctx.VAR_IDENTIFIER().getText()
        type_ctx = ctx.type_()
        type_ = self._get_type_from_ctx(type_ctx) if type_ctx is not None else None
        if name == "this" and type_ is not None and type_.kind != TypeKind.WEAK_REF:
            self.symbols.add_error(
                f"行 {ctx.start.line}: 'this' 参数必须是弱引用类型，例如 '#{type_.name}'"
            )
        symbol = Symbol(name, SymbolKind.PARAM, type_, line=ctx.start.line)
        self.symbols.define(symbol)

        # 检查默认值类型
        if ctx.expression() is not None:
            default_type = ctx.expression().accept(self)
            if type_ is not None and default_type is not None:
                self._check_type_compat(type_, default_type, ctx, "参数默认值类型")
        return None

    # ==================== 表达式访问（返回类型） ====================

    def visitLiteralExpr(self, ctx: EzLangParser.LiteralExprContext) -> Optional[Type]:
        """字面量类型推导"""
        return self._infer_literal_type(ctx.literal())

    def visitIdentifierExpr(self, ctx: EzLangParser.IdentifierExprContext) -> Optional[Type]:
        """标识符引用 — 返回符号的类型"""
        id_token = ctx.VAR_IDENTIFIER() or ctx.TYPE_IDENTIFIER()
        if id_token is None and ctx.VOID() is not None:
            return Type(name="I32", kind=TypeKind.BASIC)
        name = id_token.getText()
        symbol = self.symbols.resolve(name)
        if symbol is not None and symbol.kind in (SymbolKind.STRUCT, SymbolKind.TYPE_ALIAS):
            return Type(name="I32", kind=TypeKind.BASIC)
        if symbol is None and builtin_type(name) is not None:
            return Type(name="I32", kind=TypeKind.BASIC)
        if symbol is None and name == "race":
            func_type = Type(name="function", kind=TypeKind.FUNCTION)
            func_type.return_type = Type(name="I32", kind=TypeKind.BASIC)
            func_type.param_names = ["pl", "timeout"]
            func_type.param_types = [Type(name="array", kind=TypeKind.ARRAY), Type(name="I32", kind=TypeKind.BASIC)]
            func_type.default_param_names = {"timeout"}
            return func_type
        if symbol is None:
            self.symbols.add_error(
                f"行 {ctx.start.line}: 未定义的变量 '{name}'"
            )
            return None

        if self._is_in_flow() and name != self._current_decl_name:
            self._current_expr_reads.append(name)

        # 泛型参数验证
        if ctx.genericArgs() is not None:
            type_args = ctx.genericArgs().type_()
            if name in self.generic_templates:
                gen_names, _ = self.generic_templates[name]
                if len(type_args) != len(gen_names):
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 泛型函数 '{name}' 期望 {len(gen_names)} 个类型参数，"
                        f"实际提供了 {len(type_args)} 个"
                    )
            else:
                self.symbols.add_warning(
                    f"行 {ctx.start.line}: '{name}' 不是泛型函数，但提供了类型参数"
                )

        return symbol.type

    def visitParenExpr(self, ctx: EzLangParser.ParenExprContext) -> Optional[Type]:
        """括号表达式 — 返回内部表达式类型"""
        if ctx.expression() is not None:
            return ctx.expression().accept(self)
        return None

    # ==================== 二元运算表达式 ====================

    def _binop_type(self, ctx) -> Optional[Type]:
        """处理二元运算的类型检查"""
        # 获取左右操作数（所有二元运算规则的 getChild(0) 和 getChild(2) 模式）
        left_ctx = ctx.getChild(0) if ctx.getChildCount() > 0 else None
        right_ctx = ctx.getChild(2) if ctx.getChildCount() > 2 else None

        left_type = left_ctx.accept(self) if left_ctx is not None else None
        right_type = right_ctx.accept(self) if right_ctx is not None else None

        if left_type is None:
            return right_type
        if right_type is None:
            return left_type

        # 判断运算符类型，决定返回类型
        op_is_comparison = (
            self._has_token(ctx, 'EQ') or
            self._has_token(ctx, 'NE') or
            (self._has_token(ctx, 'LANGLE') and not self._has_token(ctx, 'SHL')) or
            self._has_token(ctx, 'RANGLE') or
            self._has_token(ctx, 'LE') or
            self._has_token(ctx, 'GE')
        )

        op_is_logical = (
            self._has_token(ctx, 'AND') or
            self._has_token(ctx, 'OR')
        )

        op_text = ctx.getChild(1).getText() if ctx.getChildCount() > 1 else ""
        vector_result = self._vec_binary_type(left_type, right_type, ctx, op_text, op_is_comparison)
        if vector_result is not None:
            return vector_result

        # 类型兼容性检查
        self._check_binary_op(left_type, right_type, ctx, "二元运算")

        if op_is_comparison or op_is_logical:
            return Type(name="Bool", kind=TypeKind.BASIC)
        return left_type

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'STAR') or self._has_token(ctx, 'SLASH') or self._has_token(ctx, 'PERCENT'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitAdditiveExpression(self, ctx: EzLangParser.AdditiveExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'PLUS') or self._has_token(ctx, 'MINUS'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitShiftExpression(self, ctx: EzLangParser.ShiftExpressionContext) -> Optional[Type]:
        if hasattr(ctx, 'shiftOperator') and ctx.shiftOperator():
            exprs = list(ctx.additiveExpression())
            result_type = exprs[0].accept(self) if exprs else None
            if not self._is_shift_lhs_type(result_type):
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 移位左操作数必须是整数或整数 SIMD 向量类型，实际为 '{result_type}'"
                )
            for rhs in exprs[1:]:
                rhs_type = rhs.accept(self)
                if not self._is_unsigned_shift_rhs_type(rhs_type):
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 移位右操作数必须是无符号整数类型，实际为 '{rhs_type}'"
                    )
            return result_type
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext) -> Optional[Type]:
        if (self._has_token(ctx, 'LANGLE') or self._has_token(ctx, 'RANGLE') or
                self._has_token(ctx, 'LE') or self._has_token(ctx, 'GE')):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'EQ') or self._has_token(ctx, 'NE'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitBitAndExpression(self, ctx: EzLangParser.BitAndExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'AMPERSAND'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitBitXorExpression(self, ctx: EzLangParser.BitXorExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'CARET'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitBitOrExpression(self, ctx: EzLangParser.BitOrExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'PIPE'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitAndExpression(self, ctx: EzLangParser.AndExpressionContext) -> Optional[Type]:
        exprs = list(ctx.equalityExpression()) if ctx.equalityExpression() else []
        if len(exprs) > 1 and self._if_like_operand(exprs[-1]) is not None:
            for expr in exprs[:-1]:
                expr.accept(self)
            if_ctx, _negated = self._if_like_operand(exprs[-1])
            self._visit_if_like_condition(if_ctx)
            return self._visit_if_like_branches(if_ctx, statement_context=False)
        if self._has_token(ctx, 'AND'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    def visitOrExpression(self, ctx: EzLangParser.OrExpressionContext) -> Optional[Type]:
        if self._has_token(ctx, 'OR'):
            return self._binop_type(ctx)
        return ctx.getChild(0).accept(self) if ctx.getChildCount() > 0 else None

    # ==================== 一元表达式 ====================

    def visitUnaryExpression(self, ctx: EzLangParser.UnaryExpressionContext) -> Optional[Type]:
        """一元表达式：!expr, -expr, +expr, ~expr"""
        inner = ctx.unaryExpression()
        if inner is not None:
            inner_type = inner.accept(self)
            if ctx.BANG() is not None:
                # ! 只能用于 Bool
                if inner_type and inner_type.name != "Bool" and inner_type.name != "unknown":
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 逻辑非 '!' 操作数必须是 Bool 类型，当前为 '{inner_type}'"
                    )
                return Type(name="Bool", kind=TypeKind.BASIC)
            # +, -, ~ 用于数值
            return inner_type

        # 后缀表达式
        postfix = ctx.postfixExpression()
        if postfix is not None:
            return postfix.accept(self)
        return None

    def visitPostfixUnaryExpression(self, ctx: EzLangParser.PostfixUnaryExpressionContext) -> Optional[Type]:
        postfix = ctx.postfixExpression()
        return postfix.accept(self) if postfix is not None else None

    def visitPrefixUnaryExpression(self, ctx: EzLangParser.PrefixUnaryExpressionContext) -> Optional[Type]:
        if ctx.BANG() is not None:
            if_like = self._if_like_operand(ctx)
            if if_like is not None:
                if_ctx, _negated = if_like
                self._visit_if_like_condition(if_ctx)
                return self._visit_if_like_branches(if_ctx, statement_context=False)
        inner = ctx.unaryExpression()
        inner_type = inner.accept(self) if inner is not None else None
        if ctx.BANG() is not None:
            if inner_type and inner_type.name != "Bool" and inner_type.name != "unknown":
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 逻辑非 '!' 操作数必须是 Bool 类型，当前为 '{inner_type}'"
                )
            return Type(name="Bool", kind=TypeKind.BASIC)
        return inner_type

    def visitPrefixTypeAssertion(self, ctx: EzLangParser.PrefixTypeAssertionContext) -> Optional[Type]:
        target_type = self._get_type_from_ctx(ctx.type_())
        inner = ctx.unaryExpression()
        if inner is not None:
            inner.accept(self)
        return target_type

    # ==================== 后缀表达式 ====================

    def visitPrimaryExpr(self, ctx: EzLangParser.PrimaryExprContext) -> Optional[Type]:
        return ctx.primaryExpression().accept(self)

    def visitMemberAccess(self, ctx: EzLangParser.MemberAccessContext) -> Optional[Type]:
        """成员访问：expr.field — 返回字段类型"""
        field_name = self._field_name_text(ctx)
        static_struct_name = self._static_struct_member_owner(ctx.postfixExpression())
        if static_struct_name is not None:
            method_type = self._method_type_for_struct(Type(name=static_struct_name, kind=TypeKind.STRUCT), field_name)
            if method_type is not None:
                return method_type

        target_type = None
        if ctx.postfixExpression() is not None:
            target_type = ctx.postfixExpression().accept(self)
        if target_type and target_type.kind == TypeKind.WEAK_REF:
            target_type = target_type.referent_type or target_type.element_type

        if isinstance(ctx.postfixExpression(), EzLangParser.OptionalUnwrapContext) and target_type is not None:
            field_type = None
            if target_type.kind == TypeKind.STRUCT:
                if target_type.fields and field_name in target_type.fields:
                    field_type = target_type.fields[field_name]
                else:
                    field_type = self._method_type_for_struct(target_type, field_name)
            if field_type is not None:
                result_type = field_type.return_type if field_type.kind == TypeKind.FUNCTION else field_type
                if result_type is not None:
                    result = Type(kind=TypeKind.OPTIONAL, name=f"{result_type.name}?")
                    result.element_type = result_type
                    return result
            result = Type(kind=TypeKind.OPTIONAL, name=f"{target_type.name}?")
            result.element_type = target_type
            return result

        # 结构体成员访问：从 struct_type.fields 查找
        if target_type and target_type.kind == TypeKind.STRUCT:
            if target_type.fields and field_name in target_type.fields:
                return target_type.fields[field_name]
            method_type = self._method_type_for_struct(target_type, field_name)
            if method_type is not None:
                return method_type
            if target_type.name != "unknown":
                self.symbols.add_warning(
                    f"行 {ctx.start.line}: 结构体 '{target_type.name}' 没有字段 '{field_name}'"
                )
            return None

        collection_method = self._collection_method_type(target_type, field_name)
        if collection_method is not None:
            return collection_method

        if target_type and target_type.kind == TypeKind.OPTIONAL:
            if field_name == "ok":
                return Type(name="Bool", kind=TypeKind.BASIC)
            if field_name == "value":
                return target_type.element_type or target_type.referent_type

        if target_type and target_type.kind == TypeKind.UNION:
            if field_name == "tag":
                return Type(name="I32", kind=TypeKind.BASIC)
            if field_name == "value":
                return self._union_payload_type(target_type)

        return None

    def visitWeakRefExpression(self, ctx: EzLangParser.WeakRefExpressionContext) -> Optional[Type]:
        """弱引用表达式 #expr：返回 #T。"""
        inner_type = ctx.unaryExpression().accept(self) if ctx.unaryExpression() is not None else None
        result = Type(kind=TypeKind.WEAK_REF, name=f"#{inner_type.name if inner_type else 'unknown'}")
        result.referent_type = inner_type
        result.element_type = inner_type
        return result

    def _static_struct_member_owner(self, ctx) -> Optional[str]:
        """识别 StructName.method 这种类型级结构体成员访问。"""
        primary = ctx.primaryExpression() if hasattr(ctx, 'primaryExpression') else None
        if primary is None:
            return None
        if not isinstance(primary, EzLangParser.IdentifierExprContext):
            return None
        token = primary.TYPE_IDENTIFIER()
        if token is None:
            return None
        name = token.getText()
        symbol = self.symbols.resolve(name)
        if symbol is not None and symbol.kind == SymbolKind.STRUCT:
            return name
        return None

    def visitCall(self, ctx: EzLangParser.CallContext) -> Optional[Type]:
        """函数调用：获取函数返回类型，检查参数类型"""
        target = ctx.postfixExpression()
        if target is not None:
            call_name = self._get_call_name(target)
            target_type = target.accept(self)
            implicit_this = isinstance(target, EzLangParser.MemberAccessContext) and not self._is_static_struct_member_access(target)

            # 收集调用时提供的命名参数及其类型
            named_args: dict[str, Optional[Type]] = {}
            placeholder_names: set[str] = set()
            if ctx.namedArgList() is not None:
                expected_for_mapping = target_type.param_names if target_type and target_type.kind == TypeKind.FUNCTION else []
                if not expected_for_mapping and call_name in self.generic_templates:
                    expected_for_mapping = self._generic_template_param_names(call_name)
                mapped_args, placeholder_names, mapping_errors = self._map_call_args_to_params(
                    ctx.namedArgList(), expected_for_mapping, implicit_this
                )
                for message in mapping_errors:
                    self.symbols.add_error(f"行 {ctx.start.line}: {message}")
                for arg_name, arg_type in mapped_args.items():
                    if call_name == "race" and arg_name == "pl":
                        arg_type = Type(name="array", kind=TypeKind.ARRAY)
                    named_args[arg_name] = arg_type

            target_type = self._infer_generic_function_type(call_name, target_type, named_args, ctx)

            if call_name == "race":
                if not self._is_in_flow():
                    self.symbols.add_error(f"行 {ctx.start.line}: race() 只能在 flow 块内使用")
                else:
                    self.race_calls.append({"name": call_name, "line": ctx.start.line})
                    race_result = self._race_pl_return_type(ctx)
                    if race_result is not None:
                        target_type = Type(name="function", kind=TypeKind.FUNCTION)
                        target_type.return_type = race_result
                        target_type.param_names = ["pl", "timeout"]
                        target_type.param_types = [Type(name="array", kind=TypeKind.ARRAY), Type(name="I32", kind=TypeKind.BASIC)]
                        target_type.default_param_names = {"timeout"}
            elif self._is_in_flow() and call_name in self._blocking_calls:
                point = {"name": call_name, "line": ctx.start.line}
                self.suspend_points.append(point)
                self._last_suspend_call = point

            # 函数调用参数类型匹配检查
            if target_type and target_type.kind == TypeKind.FUNCTION and target_type.param_names:
                expected_names = set(target_type.param_names)
                seen_names: set[str] = set()
                for arg_name, _arg_type in named_args.items():
                        if arg_name in seen_names:
                            self.symbols.add_error(
                                f"行 {ctx.start.line}: 重复提供参数 '{arg_name}'"
                            )
                        seen_names.add(arg_name)
                        if arg_name not in expected_names:
                            self.symbols.add_error(
                                f"行 {ctx.start.line}: 未知参数 '{arg_name}'"
                            )
                implicit_this_name = target_type.param_names[0] if implicit_this and self._is_weak_this_param(target_type) else None
                explicit_optional_this = target_type.param_names[0] if self._is_weak_this_param(target_type) else None
                for pname in target_type.param_names:
                    if pname == implicit_this_name:
                        continue
                    if pname == explicit_optional_this and pname not in named_args:
                        continue
                    if pname not in named_args and pname not in target_type.default_param_names:
                        self.symbols.add_error(
                            f"行 {ctx.start.line}: 缺少必填参数 '{pname}'"
                        )
                for i, pname in enumerate(target_type.param_names):
                    if pname == implicit_this_name:
                        continue
                    if pname in named_args:
                        actual = named_args[pname]
                        expected = target_type.param_types[i] if i < len(target_type.param_types) else None
                        if expected and actual and expected.name != "unknown" and actual.name != "unknown":
                            if not expected.compatible_with(actual):
                                line = ctx.start.line if hasattr(ctx, 'start') else 0
                                self.symbols.add_error(
                                    f"行 {line}: 参数 '{pname}' 类型不匹配：期望 '{expected}'，实际 '{actual}'"
                                )

            if target_type and target_type.kind == TypeKind.FUNCTION:
                collection_type = self._collection_call_return_type(call_name, ctx)
                if collection_type is not None:
                    return collection_type
                if placeholder_names:
                    return self._curried_function_type(target_type, placeholder_names)
                return target_type.return_type
        return None

    def _race_pl_return_type(self, ctx) -> Optional[Type]:
        """从 race(pl = [() => T, ...]) 分支推断返回类型。"""
        if ctx.namedArgList() is None:
            return None
        pl_expr = None
        for arg_name, expr_ctx in self._call_arg_items(ctx.namedArgList()):
            if arg_name == 'pl':
                pl_expr = expr_ctx
                break
        array_lit = self._find_array_literal_ctx(pl_expr)
        if array_lit is None or array_lit.expressionList() is None:
            return None

        result_type = None
        for branch_expr in array_lit.expressionList().expression():
            fn = self._find_function_literal_ctx(branch_expr)
            if fn is None:
                return None
            branch_type = self._function_literal_return_type(fn)
            if branch_type is None:
                continue
            if result_type is None:
                result_type = branch_type
            elif not result_type.compatible_with(branch_type) and not branch_type.compatible_with(result_type):
                self.symbols.add_error(
                    f"行 {branch_expr.start.line}: race(pl) 分支返回类型不一致："
                    f"期望 '{result_type}'，实际 '{branch_type}'"
                )
        return result_type

    def _function_literal_return_type(self, fn) -> Optional[Type]:
        if fn is None:
            return None
        if fn.type_() is not None:
            return self._get_type_from_ctx(fn.type_())
        prev_return_stack = self._parallel_return_stack
        prev_return = self.current_function_return
        prev_in_func = self.in_function
        self._parallel_return_stack = [[]]
        self.current_function_return = None
        self.in_function = True
        self.symbols.push_scope("race")
        params = fn.paramList()
        if params is not None:
            for param in params.param():
                param.accept(self)
        if fn.expression() is not None:
            expr_type = fn.expression().accept(self)
        elif fn.block() is not None:
            fn.block().accept(self)
            expr_type = None
        else:
            expr_type = None
        return_types = self._parallel_return_stack.pop()
        self._check_return_type_set(return_types, fn, "race(pl) 分支")
        self._parallel_return_stack = prev_return_stack
        self.current_function_return = prev_return
        self.in_function = prev_in_func
        self.symbols.pop_scope()
        return return_types[-1] if return_types else (expr_type or Type(name="Void", kind=TypeKind.BASIC))

    def _find_array_literal_ctx(self, ctx):
        if ctx is None:
            return None
        if hasattr(ctx, 'arrayLiteral') and ctx.arrayLiteral() is not None:
            return ctx.arrayLiteral()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                found = self._find_array_literal_ctx(ctx.getChild(i))
                if found is not None:
                    return found
        return None

    def _find_function_literal_ctx(self, ctx):
        if ctx is None:
            return None
        if hasattr(ctx, 'functionLiteral') and ctx.functionLiteral() is not None:
            return ctx.functionLiteral()
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                found = self._find_function_literal_ctx(ctx.getChild(i))
                if found is not None:
                    return found
        return None

    def _collection_call_return_type(self, call_name: Optional[str], ctx) -> Optional[Type]:
        if call_name is None or ctx is None or not hasattr(ctx, 'postfixExpression'):
            return None
        ident = self._leftmost_identifier_ctx(ctx.postfixExpression())
        generic_args = []
        if ident is not None and ident.genericArgs() is not None:
            generic_args = [self._get_type_from_ctx(t) for t in ident.genericArgs().type_()]
        first = generic_args[0] if generic_args else Type(name="unknown", kind=TypeKind.BASIC)
        second = generic_args[1] if len(generic_args) > 1 else first

        if call_name == 'listLen' or call_name == 'dictLen':
            return Type(name="I64", kind=TypeKind.BASIC)
        if call_name in {'listPush', 'listUnshift', 'listSort'}:
            return Type(name="Void", kind=TypeKind.BASIC)
        if call_name in {'listPop', 'listShift', 'listFind'}:
            result = Type(kind=TypeKind.OPTIONAL, name=f"{first.name}?")
            result.element_type = first
            return result
        if call_name in {'listSlice', 'listFilter', 'randomShuffle'}:
            result = Type(kind=TypeKind.LIST, name=f"List<{first.name}>")
            result.element_type = first
            return result
        if call_name == 'listMap':
            result = Type(kind=TypeKind.LIST, name=f"List<{second.name}>")
            result.element_type = second
            return result
        if call_name == 'dictHas' or call_name == 'dictDelete':
            return Type(name="Bool", kind=TypeKind.BASIC)
        if call_name == 'dictKeys':
            result = Type(kind=TypeKind.LIST, name=f"List<{first.name}>")
            result.element_type = first
            return result
        if call_name == 'dictValues':
            result = Type(kind=TypeKind.LIST, name=f"List<{second.name}>")
            result.element_type = second
            return result
        return None

    def _is_static_struct_member_access(self, ctx) -> bool:
        if not isinstance(ctx, EzLangParser.MemberAccessContext):
            return False
        return self._static_struct_member_owner(ctx.postfixExpression()) is not None

    def _leftmost_identifier_ctx(self, ctx):
        if isinstance(ctx, EzLangParser.IdentifierExprContext):
            return ctx
        if hasattr(ctx, 'postfixExpression') and ctx.postfixExpression() is not None:
            return self._leftmost_identifier_ctx(ctx.postfixExpression())
        if hasattr(ctx, 'primaryExpression') and ctx.primaryExpression() is not None:
            return self._leftmost_identifier_ctx(ctx.primaryExpression())
        if hasattr(ctx, 'getChildCount'):
            for i in range(ctx.getChildCount()):
                result = self._leftmost_identifier_ctx(ctx.getChild(i))
                if result is not None:
                    return result
        return None

    def visitTypeAssertion(self, ctx: EzLangParser.TypeAssertionContext) -> Optional[Type]:
        """类型断言 expr! — 拆包可选类型，返回内部类型"""
        target = ctx.postfixExpression()
        if target is not None:
            target_type = target.accept(self)
            if target_type and target_type.kind == TypeKind.OPTIONAL:
                return target_type.element_type
            if target_type and target_type.kind != TypeKind.OPTIONAL and target_type.name != "unknown":
                self.symbols.add_warning(
                    f"行 {ctx.start.line}: 对非可选类型 '{target_type}' 使用类型断言 '!'"
                )
            return target_type
        return None

    def visitOptionalUnwrap(self, ctx: EzLangParser.OptionalUnwrapContext) -> Optional[Type]:
        """可选链 expr? — 返回可选类型的内部类型或 None"""
        target = ctx.postfixExpression()
        if target is not None:
            target_type = target.accept(self)
            if target_type and target_type.kind == TypeKind.OPTIONAL:
                return target_type.element_type
            if target_type and target_type.kind == TypeKind.WEAK_REF:
                return target_type.referent_type
        return None

    def visitIndex(self, ctx: EzLangParser.IndexContext) -> Optional[Type]:
        """数组索引：arr[i] — 检查索引类型，返回元素类型"""
        target = ctx.postfixExpression()
        target_type = None
        if target is not None:
            target_type = target.accept(self)

        # 检查索引表达式类型（应为整数）
        index_type = None
        if ctx.expression() is not None:
            index_type = ctx.expression().accept(self)
        if target_type and target_type.kind == TypeKind.DICT:
            self._check_type_compat(target_type.key_type, index_type, ctx, "字典键类型")
            return target_type.value_type
        if index_type and not index_type.is_integer() and index_type.name != "unknown":
            self.symbols.add_warning(
                f"行 {ctx.start.line}: 数组索引应为整数类型，实际为 '{index_type}'"
            )

        # 检查目标是否为可索引类型
        if target_type and target_type.element_type:
            return target_type.element_type
        if target_type and target_type.kind == TypeKind.ARRAY:
            return target_type.element_type
        if target_type and target_type.kind not in (TypeKind.ARRAY, TypeKind.LIST) and \
           target_type.element_type is None and target_type.name != "unknown":
            self.symbols.add_warning(
                f"行 {ctx.start.line}: 对非数组类型 '{target_type}' 使用索引访问"
            )
        return None

    # ==================== 赋值 ====================

    def visitAssignmentExpression(self, ctx: EzLangParser.AssignmentExpressionContext) -> Optional[Type]:
        """检查赋值表达式类型"""
        # 总是访问左操作数（pipelineExpression）
        left = ctx.pipelineExpression()
        left_type = None
        if left is not None:
            left_type = left.accept(self)

        # 如果有赋值运算符
        if ctx.assignmentOperator() is not None:
            right = ctx.assignmentExpression()
            right_type = self._with_expected_expr_type(left_type, right) if right is not None else None

            name = self._get_lvalue_owner_name(ctx)
            if name:
                symbol = self.symbols.resolve(name)
                if symbol is not None and not symbol.mutable:
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 不能修改常量 '{name}'"
                    )

            # 按真实左值类型检查，避免 arr[i] 被误判为整个数组类型。
            if ctx.assignmentOperator().ASSIGN() is not None and right_type is not None:
                self._check_type_compat(left_type, right_type, ctx, "赋值类型")

            return left_type

        return left_type

    # ==================== 条件表达式 ====================

    def visitConditionalExpression(self, ctx: EzLangParser.ConditionalExpressionContext) -> Optional[Type]:
        """三元条件表达式：cond ? a : b"""
        result = None
        if ctx.getChildCount() > 0:
            result = ctx.getChild(0).accept(self)  # rangeExpression
        if self._is_misparsed_prefix_not_conditional(ctx):
            return Type(name="Bool", kind=TypeKind.BASIC)
        if ctx.QUESTION() is not None:
            cond_exprs = ctx.conditionalExpression()
            if cond_exprs is not None and len(cond_exprs) > 1:
                result = cond_exprs[1].accept(self)  # else 分支
        return result

    def _is_misparsed_prefix_not_conditional(self, ctx) -> bool:
        """识别 `!(cond) ? a : b` 被解析成 `!((cond) ? a : b)` 的兼容形状。"""
        if not isinstance(ctx, EzLangParser.ConditionalExpressionContext) or ctx.QUESTION() is None:
            return False
        text = ctx.getText() if hasattr(ctx, 'getText') else ''
        return text.startswith('!(')

    def _control_flow_dict_literal(self, ctx):
        if isinstance(ctx, EzLangParser.DictExprContext):
            return ctx.dictLiteral()
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._control_flow_dict_literal(ctx.getChild(0))
        return None

    def _visit_control_flow_body(self, ctx) -> Optional[Type]:
        literal = self._control_flow_dict_literal(ctx)
        if literal is None:
            return ctx.accept(self) if ctx is not None else None
        last_type = None
        for field in literal.dictField():
            key = field.dictKey()
            if key is None or key.VAR_IDENTIFIER() is None or field.type_() is not None:
                return ctx.accept(self)
            name = self._dict_field_name(field)
            symbol = self.symbols.resolve(name)
            if symbol is None:
                self.symbols.add_error(f"行 {field.start.line}: 未定义的变量 '{name}'")
                continue
            if not symbol.mutable:
                self.symbols.add_error(f"行 {field.start.line}: 不能修改常量 '{name}'")
            value_type = self._with_expected_expr_type(symbol.type, field.expression())
            if symbol.type is not None and value_type is not None:
                self._check_type_compat(symbol.type, value_type, field, "赋值类型")
            last_type = symbol.type
        return last_type

    def _if_like_operand(self, ctx):
        if ctx is None:
            return None
        if isinstance(ctx, EzLangParser.IfLikeExprContext):
            return ctx, False
        if isinstance(ctx, EzLangParser.IfLikePrimaryExprContext):
            return ctx.ifLikeExpr(), False
        if isinstance(ctx, EzLangParser.PrefixUnaryExpressionContext) and ctx.BANG() is not None:
            inner = self._if_like_operand(ctx.unaryExpression())
            if inner is not None:
                if_ctx, negated = inner
                return if_ctx, not negated
            return None
        if hasattr(ctx, 'getChildCount') and ctx.getChildCount() == 1:
            return self._if_like_operand(ctx.getChild(0))
        return None

    def _visit_if_like_condition(self, ctx: EzLangParser.IfLikeExprContext) -> Optional[Type]:
        cond_type = ctx.expression(0).accept(self) if ctx.expression(0) is not None else None
        if cond_type and cond_type.name != "Bool" and cond_type.name != "unknown":
            self.symbols.add_warning(
                f"行 {ctx.start.line}: 条件表达式应为 Bool 类型，当前为 '{cond_type}'"
            )
        return cond_type

    def _visit_if_like_branches(self, ctx: EzLangParser.IfLikeExprContext, statement_context: bool) -> Optional[Type]:
        then_type = None
        else_type = None
        then_ctx, else_ctx = self._if_like_branch_ctxs(ctx)
        if then_ctx is not None:
            then_type = self._visit_control_flow_body(then_ctx) if statement_context and else_ctx is None else then_ctx.accept(self)
        if else_ctx is not None:
            else_type = else_ctx.accept(self)
        if then_type is not None and else_type is not None:
            if then_type.name != else_type.name:
                self.symbols.add_warning(
                    f"行 {ctx.start.line}: 条件分支类型不一致：'{then_type}' 和 '{else_type}'"
                )
        return then_type or else_type

    def visitRangeExpression(self, ctx: EzLangParser.RangeExpressionContext) -> Optional[Type]:
        if ctx.getChildCount() > 0:
            return ctx.getChild(0).accept(self)
        return None

    # ==================== 主要表达式 ====================

    def visitStructLiteralExpr(self, ctx: EzLangParser.StructLiteralExprContext) -> Optional[Type]:
        """结构体字面量：TypeName(field = value)"""
        name = ctx.structLiteral().TYPE_IDENTIFIER().getText()
        resolved = self.symbols.resolve(name)
        builtin = builtin_type(name)
        if resolved is None and (builtin is None or builtin.kind != TypeKind.STRUCT):
            self.symbols.add_error(f"行 {ctx.start.line}: 未定义的类型 '{name}'")
            return Type(name=name, kind=TypeKind.STRUCT)
        # 返回符号表中的结构体类型（保留 fields 信息），内置对象类型走内建表。
        struct_type = resolved.type if resolved and resolved.type else builtin
        if ctx.structLiteral().genericArgs() is not None and struct_type is not None:
            type_args = [self._get_type_from_ctx(t) for t in ctx.structLiteral().genericArgs().type_()]
            if None not in type_args:
                struct_type = self._instantiate_struct_type(struct_type, type_args)
        elif struct_type is not None and struct_type.name in self.struct_generic_params:
            type_args = self._infer_struct_type_args_from_fields(
                struct_type,
                ctx.structLiteral().structFieldInitList(),
            )
            if type_args is not None:
                struct_type = self._instantiate_struct_type(struct_type, type_args)

        # 遍历字段初始化，验证字段名有效性
        init_list = ctx.structLiteral().structFieldInitList()
        if init_list is not None:
            for init in init_list.structFieldInit():
                # 实例展开 ...expr：源值必须是结构体，且同名字段类型要兼容
                if init.ELLIPSIS() is not None:
                    spread_type = init.expression().accept(self) if init.expression() is not None else None
                    if spread_type is None:
                        continue
                    if spread_type.kind != TypeKind.STRUCT:
                        self.symbols.add_warning(
                            f"行 {ctx.start.line}: 实例展开只能用于结构体值，实际为 '{spread_type}'"
                        )
                        continue
                    if struct_type.fields and spread_type.fields:
                        for field_name, source_field_type in spread_type.fields.items():
                            target_field_type = struct_type.fields.get(field_name)
                            if target_field_type is not None and source_field_type is not None \
                                    and not target_field_type.compatible_with(source_field_type):
                                self.symbols.add_warning(
                                    f"行 {ctx.start.line}: 实例展开字段 '{field_name}' 类型不兼容："
                                    f"期望 '{target_field_type}'，实际 '{source_field_type}'"
                                )
                    continue
                fname = self._field_name_text(init)
                if struct_type.fields and fname not in struct_type.fields:
                    self.symbols.add_warning(
                        f"行 {ctx.start.line}: 结构体 '{name}' 没有字段 '{fname}'"
                    )
                # 检查字段初始化值类型
                if init.expression() is not None:
                    expected = struct_type.fields.get(fname) if struct_type.fields and fname in struct_type.fields else None
                    val_type = self._with_expected_expr_type(expected, init.expression())
                    if struct_type.fields and fname in struct_type.fields:
                        if expected and val_type and expected.name != "unknown" and val_type.name != "unknown":
                            self._check_type_compat(expected, val_type, init, "字段初始化类型")
        return struct_type

    def visitArrayLiteralExpr(self, ctx: EzLangParser.ArrayLiteralExprContext) -> Optional[Type]:
        """数组字面量：[a, b, c]"""
        arr = ctx.arrayLiteral()
        element_type = None
        if arr.expressionList() is not None:
            for expr_ctx in arr.expressionList().expression():
                t = expr_ctx.accept(self)
                if element_type is None:
                    element_type = t
        result = Type(kind=TypeKind.ARRAY, name="array")
        result.element_type = element_type
        return result

    def visitVecLiteralExpr(self, ctx: EzLangParser.VecLiteralExprContext) -> Optional[Type]:
        """SIMD 向量字面量：Vec[1, 2, 3, 4] — 检查元素类型一致性"""
        vec = ctx.vecLiteral()
        element_type = None
        elem_count = 0
        if vec.expressionList() is not None:
            for expr_ctx in vec.expressionList().expression():
                t = expr_ctx.accept(self)
                elem_count += 1
                if element_type is None:
                    element_type = t
                elif t and element_type and not element_type.compatible_with(t) \
                        and t.name != "unknown" and element_type.name != "unknown":
                    self.symbols.add_warning(
                        f"行 {ctx.start.line}: 向量元素类型不一致：'{element_type}' 和 '{t}'"
                    )
        # 向量大小应为 2 的幂
        if elem_count > 0 and (elem_count & (elem_count - 1)) != 0:
            self.symbols.add_warning(
                f"行 {ctx.start.line}: 向量大小 {elem_count} 不是 2 的幂"
            )
        result = Type(kind=TypeKind.VEC, name=f"Vec<{element_type}>[{elem_count}]")
        result.element_type = element_type
        result.vec_size = elem_count
        return result

    def visitFnLiteralExpr(self, ctx: EzLangParser.FnLiteralExprContext) -> Optional[Type]:
        """函数字面量：(a, b) => expr"""
        fn = ctx.functionLiteral()
        ret_type = None
        param_types = []
        param_names = []
        default_param_names = set()
        if fn is not None:
            ret_ctx = fn.type_()
            if ret_ctx is not None:
                ret_type = self._get_type_from_ctx(ret_ctx)
            params = fn.paramList()
            if params is not None:
                for param in params.param():
                    pt = self._get_type_from_ctx(param.type_()) if param.type_() is not None else None
                    param_types.append(pt)
                    param_name = param.VAR_IDENTIFIER().getText()
                    param_names.append(param_name)
                    if param.expression() is not None:
                        default_param_names.add(param_name)

        func_type = Type(name="function", kind=TypeKind.FUNCTION)
        func_type.return_type = ret_type
        func_type.param_types = param_types
        func_type.param_names = param_names
        func_type.default_param_names = default_param_names

        # 分析函数体
        if fn is not None:
            self.symbols.push_scope("lambda")
            params = fn.paramList()
            if params is not None:
                for param in params.param():
                    param.accept(self)
            prev_return = self.current_function_return
            prev_in_func = self.in_function
            prev_parallel_return_stack = self._parallel_return_stack
            self.current_function_return = ret_type
            self.in_function = True
            self._parallel_return_stack = []
            if fn.expression() is not None:
                fn.expression().accept(self)
            elif fn.block() is not None:
                fn.block().accept(self)
            self._parallel_return_stack = prev_parallel_return_stack
            self.in_function = prev_in_func
            self.current_function_return = prev_return
            self.symbols.pop_scope()
        return func_type

    # ==================== 控制流表达式 ====================

    def _if_like_branch_ctxs(self, ctx: EzLangParser.IfLikeExprContext):
        """返回类 if 的 then/else 分支节点；分支可为 expression 或 block。"""
        then_ctx = ctx.getChild(4) if ctx.getChildCount() > 4 else None
        else_ctx = ctx.getChild(6) if ctx.COLON() is not None and ctx.getChildCount() > 6 else None
        return then_ctx, else_ctx

    def visitIfLikeExpr(self, ctx: EzLangParser.IfLikeExprContext) -> Optional[Type]:
        """类 if 表达式: (cond) ? a : b"""
        self._visit_if_like_condition(ctx)
        return self._visit_if_like_branches(ctx, statement_context=True)

    def visitLoopExpr(self, ctx: EzLangParser.LoopExprContext) -> Optional[Type]:
        """循环表达式"""
        self.loop_depth += 1
        self.symbols.push_scope("loop")
        try:
            name = ctx.VAR_IDENTIFIER()
            if name is not None:
                loop_var_type = Type(name="I32", kind=TypeKind.BASIC)
                range_ctx = ctx.rangeExpression()
                if range_ctx is not None and range_ctx.ELLIPSIS() is None:
                    iter_type = range_ctx.accept(self)
                    if iter_type is not None and iter_type.element_type is not None:
                        loop_var_type = iter_type.element_type
                symbol = Symbol(name.getText(), SymbolKind.VARIABLE,
                              loop_var_type, mutable=False, line=ctx.start.line)
                self.symbols.define(symbol)
            if ctx.block() is not None:
                ctx.block().accept(self)
        finally:
            self.symbols.pop_scope()
            self.loop_depth -= 1
        return None

    def visitMatchBlockExpr(self, ctx: EzLangParser.MatchBlockExprContext) -> Optional[Type]:
        """match 块"""
        if ctx.matchBlock() is not None:
            ctx.matchBlock().accept(self)
        return None

    # ==================== 其他表达式 ====================

    def visitBlockExpr(self, ctx: EzLangParser.BlockExprContext) -> Optional[Type]:
        """块表达式"""
        if ctx.block() is not None:
            return ctx.block().accept(self)
        return None

    def visitDictExpr(self, ctx: EzLangParser.DictExprContext) -> Optional[Type]:
        """字典字面量"""
        expected_type = self._expected_expr_type()
        dict_type = Type(name="Dict", kind=TypeKind.DICT)
        key_type = expected_type.key_type if expected_type is not None and expected_type.kind == TypeKind.DICT else None
        value_type = expected_type.value_type if expected_type is not None and expected_type.kind == TypeKind.DICT else None
        if ctx.dictLiteral() is not None:
            for field in ctx.dictLiteral().dictField():
                field_name = self._dict_field_name(field)
                expected_value_type = value_type
                if expected_type is not None and expected_type.kind == TypeKind.STRUCT and field_name in expected_type.fields:
                    expected_value_type = expected_type.fields[field_name]
                if expected_type is not None and expected_type.kind == TypeKind.DICT and field_name in expected_type.fields:
                    expected_value_type = expected_type.fields[field_name]

                key_ctx = field.dictKey()
                inferred_key = None
                if key_ctx is not None:
                    if key_ctx.expression() is not None:
                        inferred_key = key_ctx.expression().accept(self)
                    elif key_ctx.VAR_IDENTIFIER() is not None or key_ctx.STRING_LITERAL() is not None:
                        inferred_key = Type(name="Str", kind=TypeKind.BASIC)
                if inferred_key is not None:
                    if key_type is None:
                        key_type = inferred_key
                    elif not key_type.compatible_with(inferred_key):
                        self.symbols.add_warning(
                            f"行 {ctx.start.line}: 字典键类型不一致：'{key_type}' 和 '{inferred_key}'"
                        )
                if field.expression() is not None:
                    annotated_value_type = self._get_type_from_ctx(field.type_()) if field.type_() is not None else None
                    expected_for_expr = annotated_value_type or expected_value_type
                    current_value_type = self._with_expected_expr_type(expected_for_expr, field.expression())
                    if annotated_value_type is not None:
                        self._check_type_compat(annotated_value_type, current_value_type, field, "字典字段类型")
                    if expected_value_type is not None:
                        self._check_type_compat(expected_value_type, current_value_type, field, "字典字段类型")
                    if value_type is None:
                        value_type = current_value_type
                    elif current_value_type and value_type and not value_type.compatible_with(current_value_type):
                        self.symbols.add_warning(
                            f"行 {ctx.start.line}: 字典值类型不一致：'{value_type}' 和 '{current_value_type}'"
                        )
        if expected_type is not None and expected_type.kind in (TypeKind.STRUCT, TypeKind.DICT) and expected_type.fields:
            if ctx.dictLiteral() is not None:
                present_fields = {self._dict_field_name(field) for field in ctx.dictLiteral().dictField()}
                for field_name in expected_type.fields:
                    if field_name not in present_fields:
                        self.symbols.add_error(
                            f"行 {ctx.start.line}: 对象字面量缺少字段 '{field_name}'"
                        )
        if expected_type is not None and expected_type.kind == TypeKind.STRUCT:
            return expected_type
        dict_type.key_type = key_type or Type(name="Str", kind=TypeKind.BASIC)
        dict_type.value_type = value_type
        dict_type.fields = dict(expected_type.fields) if expected_type is not None and expected_type.kind == TypeKind.DICT else {}
        return dict_type

    def _markup_attr_type(self, attr) -> Optional[Type]:
        if attr.expression() is not None:
            return attr.expression().accept(self)
        if attr.STRING_LITERAL() is not None:
            return Type(name="Str", kind=TypeKind.BASIC)
        if attr.INTEGER_LITERAL() is not None:
            return Type(name="I32", kind=TypeKind.BASIC)
        if attr.BOOL_LITERAL() is not None:
            return Type(name="Bool", kind=TypeKind.BASIC)
        return None

    def _markup_children_type(self, ctx) -> Type:
        element_type = None
        for child in ctx.markupChild():
            current_type = None
            if child.markupLiteral() is not None:
                current_type = self.visitMarkupLiteral(child.markupLiteral())
            elif child.expression() is not None:
                current_type = child.expression().accept(self)
            elif child.STRING_LITERAL() is not None:
                current_type = Type(name="Str", kind=TypeKind.BASIC)
            if element_type is None:
                element_type = current_type
            elif current_type and element_type and not element_type.compatible_with(current_type):
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 标记子节点类型不一致：'{element_type}' 和 '{current_type}'"
                )
        result = Type(kind=TypeKind.ARRAY, name="array")
        result.element_type = element_type or Type(name="Str", kind=TypeKind.BASIC)
        return result

    def _check_markup_children_against_expected(self, ctx, expected: Optional[Type]) -> None:
        """按工厂函数的 children 元素类型逐项检查标记子节点。"""
        if expected is None or expected.kind not in (TypeKind.ARRAY, TypeKind.LIST):
            actual = self._markup_children_type(ctx)
            if expected and actual and not expected.compatible_with(actual):
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 参数 'children' 类型不匹配：期望 '{expected}'，实际 '{actual}'"
                )
            return
        elem_expected = expected.element_type
        actual = self._markup_children_type(ctx) if elem_expected is None else None
        if elem_expected is None:
            return
        for child in ctx.markupChild():
            child_type = None
            if child.markupLiteral() is not None:
                child_type = self.visitMarkupLiteral(child.markupLiteral())
            elif child.expression() is not None:
                child_type = child.expression().accept(self)
            elif child.STRING_LITERAL() is not None:
                child_type = Type(name="Str", kind=TypeKind.BASIC)
            if child_type is not None and not elem_expected.compatible_with(child_type):
                self.symbols.add_error(
                    f"行 {ctx.start.line}: 参数 'children' 类型不匹配：期望元素 '{elem_expected}'，实际 '{child_type}'"
                )

    def visitMarkupExpr(self, ctx: EzLangParser.MarkupExprContext) -> Optional[Type]:
        return self.visitMarkupLiteral(ctx.markupLiteral())

    def visitMarkupLiteral(self, ctx: EzLangParser.MarkupLiteralContext) -> Optional[Type]:
        names = ctx.VAR_IDENTIFIER()
        tag_name = names[0].getText() if names else "tag"
        if len(names) >= 2 and names[0].getText() != names[-1].getText():
            self.symbols.add_error(
                f"行 {ctx.start.line}: 标记闭合名称不匹配：'{names[0].getText()}' 和 '{names[-1].getText()}'"
            )
        symbol = self.symbols.resolve(tag_name)
        if symbol is not None and symbol.type is not None and symbol.type.kind == TypeKind.FUNCTION:
            func_type = symbol.type
            expected_names = set(func_type.param_names)
            provided_names: set[str] = set()
            for attr in ctx.markupAttr():
                attr_name = attr.VAR_IDENTIFIER().getText()
                provided_names.add(attr_name)
                if func_type.param_names and attr_name not in expected_names:
                    self.symbols.add_error(f"行 {ctx.start.line}: 未知参数 '{attr_name}'")
                if attr_name in func_type.param_names:
                    idx = func_type.param_names.index(attr_name)
                    expected = func_type.param_types[idx] if idx < len(func_type.param_types) else None
                    actual = self._markup_attr_type(attr)
                    if expected and actual and expected.name != "unknown" and actual.name != "unknown":
                        if not expected.compatible_with(actual):
                            self.symbols.add_error(
                                f"行 {ctx.start.line}: 参数 '{attr_name}' 类型不匹配：期望 '{expected}'，实际 '{actual}'"
                            )
            has_children = bool(ctx.markupChild())
            if has_children:
                provided_names.add('children')
                if 'children' in func_type.param_names:
                    idx = func_type.param_names.index('children')
                    expected = func_type.param_types[idx] if idx < len(func_type.param_types) else None
                    self._check_markup_children_against_expected(ctx, expected)
                else:
                    self._markup_children_type(ctx)
                    self.symbols.add_error(f"行 {ctx.start.line}: 未知参数 'children'")
            elif 'children' in expected_names and 'children' not in func_type.default_param_names:
                self.symbols.add_error(f"行 {ctx.start.line}: 缺少必填参数 'children'")
            for pname in func_type.param_names:
                if pname not in provided_names and pname not in func_type.default_param_names:
                    self.symbols.add_error(f"行 {ctx.start.line}: 缺少必填参数 '{pname}'")
            return func_type.return_type
        for attr in ctx.markupAttr():
            self._markup_attr_type(attr)
        self._markup_children_type(ctx)
        self.symbols.add_error(
            f"行 {ctx.start.line}: 标记 '<{tag_name}>' 需要作用域内存在同名工厂函数 '{tag_name}'"
        )
        return Type(name="unknown", kind=TypeKind.BASIC)

    def visitFlowBlockExpr(self, ctx: EzLangParser.FlowBlockExprContext) -> Optional[Type]:
        if ctx.flowBlock() is not None:
            return ctx.flowBlock().accept(self)
        return None

    def visitParallelBlockExpr(self, ctx: EzLangParser.ParallelBlockExprContext) -> Optional[Type]:
        if ctx.parallelBlock() is not None:
            return ctx.parallelBlock().accept(self)
        return None

    def visitCatchBlockExpr(self, ctx: EzLangParser.CatchBlockExprContext) -> Optional[Type]:
        if ctx.catchBlock() is not None:
            return ctx.catchBlock().accept(self)
        return None

    def visitTypeofExpr(self, ctx: EzLangParser.TypeofExprContext) -> Optional[Type]:
        """typeof 表达式 — 校验目标表达式/类型，运行时返回稳定类型标识。"""
        # typeof type_: 解析类型
        if ctx.type_() is not None:
            self._get_type_from_ctx(ctx.type_())
        elif ctx.unaryExpression() is not None:
            ctx.unaryExpression().accept(self)
        return Type(name="I32", kind=TypeKind.BASIC)

    def visitPlaceholderExpr(self, ctx: EzLangParser.PlaceholderExprContext) -> Optional[Type]:
        """? 在 Optional<T> 期望上下文中表示空值；调用实参中仍由占位绑定逻辑处理。"""
        expected = self._expected_expr_type()
        if expected is not None and expected.kind == TypeKind.OPTIONAL:
            return expected
        self.symbols.add_error(
            f"行 {ctx.start.line}: '?' 只能作为函数调用的柯里化占位参数使用"
        )
        return Type(name="unknown", kind=TypeKind.BASIC)

    def visitPipeline(self, ctx: EzLangParser.PipelineContext) -> Optional[Type]:
        """管道表达式：expr -> fn(x = %)"""
        input_type = ctx.postfixExpression().accept(self) if ctx.postfixExpression() is not None else None
        func_name = ctx.VAR_IDENTIFIER().getText() if ctx.VAR_IDENTIFIER() is not None else None
        return self._check_pipeline_call(func_name, input_type, ctx.pipelineArgList(), ctx)

    def visitPipelineExpression(self, ctx: EzLangParser.PipelineExpressionContext) -> Optional[Type]:
        """顶层管道表达式：expr -> fn(args)。"""
        input_type = ctx.conditionalExpression().accept(self) if ctx.conditionalExpression() is not None else None
        if ctx.THIN_ARROW() is None:
            return input_type
        func_name = ctx.VAR_IDENTIFIER().getText() if ctx.VAR_IDENTIFIER() is not None else None
        return self._check_pipeline_call(func_name, input_type, ctx.pipelineArgList(), ctx)

    def _check_pipeline_call(self, func_name: Optional[str], input_type: Optional[Type], arg_list, ctx) -> Optional[Type]:
        """管道调用语义检查：管道值默认绑定到首个形参，% 绑定到对应具名形参。"""
        if not func_name:
            return input_type
        symbol = self.symbols.resolve(func_name)
        if symbol is None or symbol.type is None or symbol.type.kind != TypeKind.FUNCTION:
            if symbol is None:
                self.symbols.add_error(f"行 {ctx.start.line}: 未定义的变量 '{func_name}'")
            return Type(name="unknown", kind=TypeKind.BASIC)

        func_type = symbol.type
        provided: dict[str, Optional[Type]] = {}
        seen_names: set[str] = set()
        has_percent = False
        if arg_list is not None:
            for arg in arg_list.pipelineArg():
                if arg.VAR_IDENTIFIER() is None:
                    continue
                arg_name = arg.VAR_IDENTIFIER().getText()
                if arg_name in seen_names:
                    self.symbols.add_error(f"行 {ctx.start.line}: 重复提供参数 '{arg_name}'")
                seen_names.add(arg_name)
                if func_type.param_names and arg_name not in func_type.param_names:
                    self.symbols.add_error(f"行 {ctx.start.line}: 未知参数 '{arg_name}'")
                if arg.PERCENT() is not None:
                    provided[arg_name] = input_type
                    has_percent = True
                elif arg.expression() is not None:
                    provided[arg_name] = arg.expression().accept(self)

        if func_type.param_names and not has_percent:
            first_param = func_type.param_names[0]
            if first_param not in provided:
                provided[first_param] = input_type

        for pname in func_type.param_names:
            if pname not in provided and pname not in func_type.default_param_names:
                self.symbols.add_error(f"行 {ctx.start.line}: 缺少必填参数 '{pname}'")

        for index, pname in enumerate(func_type.param_names):
            if pname not in provided:
                continue
            expected = func_type.param_types[index] if index < len(func_type.param_types) else None
            actual = provided[pname]
            if expected and actual and expected.name != "unknown" and actual.name != "unknown":
                if not expected.compatible_with(actual):
                    self.symbols.add_error(
                        f"行 {ctx.start.line}: 参数 '{pname}' 类型不匹配：期望 '{expected}'，实际 '{actual}'"
                    )

        return func_type.return_type

    # ==================== 语句访问 ====================

    def visitReturnStatement(self, ctx: EzLangParser.ReturnStatementContext):
        """return 语句 — 检查位置和返回值类型"""
        # 检查是否在函数或 flow 块内
        if not self.in_function and not self._is_in_flow() and not self._is_in_parallel() and not self.allow_top_level_return:
            self.symbols.add_error(
                f"行 {ctx.start.line}: return 语句只能出现在函数内部"
            )
            return None
        # 检查返回值类型
        expr = ctx.expression()
        if expr is not None:
            actual_type = self._with_expected_expr_type(self.current_function_return, expr)
            if self._parallel_return_stack:
                self._parallel_return_stack[-1].append(actual_type)
            elif actual_type is not None and self.current_function_return is not None:
                self._check_type_compat(self.current_function_return, actual_type,
                                       ctx, "函数返回类型")
        return None

    def visitBlock(self, ctx: EzLangParser.BlockContext) -> Optional[Type]:
        """块 — 返回最后一个表达式的类型"""
        self.symbols.push_scope()
        last_type = None
        for stmt in ctx.statement():
            t = stmt.accept(self)
            if t is not None:
                last_type = t
        self.symbols.pop_scope()
        return last_type

    def visitFlowBlock(self, ctx: EzLangParser.FlowBlockContext):
        block_info = {
            "start_line": ctx.start.line,
            "end_line": ctx.stop.line if ctx.stop is not None else ctx.start.line,
        }
        self.flow_blocks.append(block_info)
        prev_values = self._flow_suspend_values
        if self.flow_depth == 0:
            self._flow_suspend_values = {}
        self.flow_depth += 1
        self._parallel_return_stack.append([])
        self.symbols.push_scope("flow")
        if ctx.block() is not None:
            ctx.block().accept(self)
        self.symbols.pop_scope()
        return_types = self._parallel_return_stack.pop()
        self._check_return_type_set(return_types, ctx, "flow 块")
        self.flow_depth -= 1
        if self.flow_depth == 0:
            self._flow_suspend_values = prev_values
        return return_types[-1] if return_types else Type(name="Void", kind=TypeKind.BASIC)

    def visitParallelBlock(self, ctx: EzLangParser.ParallelBlockContext):
        block_info = {
            "start_line": ctx.start.line,
            "end_line": ctx.stop.line if ctx.stop is not None else ctx.start.line,
            "in_flow": self._is_in_flow(),
        }
        self.parallel_blocks.append(block_info)
        if self._is_in_flow():
            point = {"name": "parallel", "line": ctx.start.line}
            self.suspend_points.append(point)
            self._last_suspend_call = point

        self.parallel_depth += 1
        self._parallel_return_stack.append([])
        self.symbols.push_scope("parallel")
        if ctx.block() is not None:
            ctx.block().accept(self)
        self.symbols.pop_scope()
        return_types = self._parallel_return_stack.pop()
        self._check_return_type_set(return_types, ctx, "parallel 块")
        self.parallel_depth -= 1
        return return_types[-1] if return_types else Type(name="Void", kind=TypeKind.BASIC)

    def visitMatchBlock(self, ctx: EzLangParser.MatchBlockContext):
        self.match_depth += 1
        try:
            for clause in ctx.matchClause():
                clause.accept(self)
        finally:
            self.match_depth -= 1
        return None

    def visitMatchClause(self, ctx: EzLangParser.MatchClauseContext):
        if ctx.expression() is not None:
            ctx.expression().accept(self)
        if ctx.statement() is not None:
            self._visit_control_flow_body(ctx.statement())
        if ctx.block() is not None:
            ctx.block().accept(self)
        return None

    def visitBreakStatement(self, ctx: EzLangParser.BreakStatementContext):
        if self.loop_depth <= 0 and self.match_depth <= 0:
            self.symbols.add_error(f"行 {ctx.start.line}: break 只能用于 loop 或 match 内")
        return None

    def visitContinueStatement(self, ctx: EzLangParser.ContinueStatementContext):
        if self.loop_depth <= 0 and self.match_depth <= 0:
            self.symbols.add_error(f"行 {ctx.start.line}: continue 只能用于 loop 或 match 内")
        return None

    def visitCatchBlock(self, ctx: EzLangParser.CatchBlockContext):
        self._catch_throw_stack.append([])
        self.symbols.push_scope("catch")
        if ctx.block() is not None:
            ctx.block().accept(self)
        self.symbols.pop_scope()
        thrown_types = self._catch_throw_stack.pop()
        return thrown_types[-1] if thrown_types else builtin_type("Error")

    # ==================== 表达式语句 ====================

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext) -> Optional[Type]:
        if ctx.expression() is not None:
            return ctx.expression().accept(self)
        return None

    # ==================== 模块访问 ====================

    def visitImportDecl(self, ctx: EzLangParser.ImportDeclContext):
        import_path = decode_string_literal_token(ctx.STRING_LITERAL().getText())
        resolved = self._resolve_import_path(import_path)
        if resolved is None:
            self.symbols.add_error(f"行 {ctx.start.line}: import 路径不存在: {import_path}")
            return None
        if resolved in self._import_stack:
            self.symbols.add_error(f"行 {ctx.start.line}: import 循环依赖: {resolved}")
            return None

        requested = self._import_specs(ctx)
        exports, export_order, private_nodes = self._parse_import_module(resolved)
        missing = [name for name in requested if name not in exports]
        for name in missing:
            self.symbols.add_error(f"行 {ctx.start.line}: import 符号 '{name}' 未由 {import_path} 导出")

        selected = self._select_import_exports(requested.keys(), exports)
        imported_names = self._imported_exports.setdefault(resolved, set())

        self._import_stack.add(resolved)
        self._source_dir_stack.append(resolved.parent)
        try:
            if resolved not in self._imported_private_files:
                self._imported_private_files.add(resolved)
                for private_node in private_nodes:
                    private_node.accept(self)
            for name in export_order:
                if name not in selected:
                    continue
                if name in imported_names and name not in requested:
                    continue
                export_ctx = exports.get(name)
                if export_ctx is None:
                    continue
                alias = requested.get(name, name)
                self._import_alias_stack.append({name: alias})
                try:
                    export_ctx.accept(self)
                finally:
                    self._import_alias_stack.pop()
                imported_names.add(name)
        finally:
            self._source_dir_stack.pop()
            self._import_stack.remove(resolved)
        return None

    def _resolve_import_path(self, import_path: str) -> Path | None:
        path = Path(import_path).expanduser()
        roots = [self._source_dir_stack[-1] if self._source_dir_stack else self.base_dir]
        if not path.is_absolute():
            roots.append(Path(__file__).resolve().parents[3] / "packages")
        for root in roots:
            raw = path if path.is_absolute() else (root / path)
            candidates = [raw]
            if raw.suffix != ".ez":
                candidates.extend([raw.with_suffix(".ez"), raw / "index.ez", raw / f"{raw.name}.ez"])
            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved.exists() and resolved.is_file():
                    return resolved
        return None

    def _import_specs(self, ctx: EzLangParser.ImportDeclContext) -> dict[str, str]:
        specs: dict[str, str] = {}
        spec_list = ctx.importSpecList()
        if spec_list is None:
            return specs
        for spec in spec_list.importSpec():
            names = spec.importName()
            if not names:
                continue
            name = self._import_name_text(names[0])
            alias = self._import_name_text(names[1]) if len(names) > 1 else name
            if name:
                specs[name] = alias or name
        return specs

    def _import_name_text(self, ctx) -> str:
        if ctx is None:
            return ""
        token = ctx.TYPE_IDENTIFIER() or ctx.VAR_IDENTIFIER()
        return token.getText() if token is not None else ""

    def _parse_import_module(self, path: Path) -> tuple[dict[str, object], list[str], list[object]]:
        from antlr4 import InputStream, CommonTokenStream
        from parser.EzLangLexer import EzLangLexer
        from parser.EzLangParser import EzLangParser as Parser

        lexer = EzLangLexer(InputStream(path.read_text(encoding='utf-8')))
        tree = Parser(CommonTokenStream(lexer)).compilationUnit()
        exports: dict[str, object] = {}
        export_order: list[str] = []
        private_nodes: list[object] = []
        for index in range(tree.getChildCount()):
            child = self._import_top_level_node(tree.getChild(index))
            if child is None:
                continue
            if isinstance(child, EzLangParser.ExternDeclContext):
                private_nodes.append(child)
                continue
            if not isinstance(child, EzLangParser.DeclarationContext):
                continue
            export_ctx = child.exportDecl()
            if export_ctx is None:
                private_nodes.append(child)
                continue
            name = self._export_decl_name(export_ctx)
            if name:
                exports[name] = export_ctx
                export_order.append(name)
        return exports, export_order, private_nodes

    def _import_top_level_node(self, child):
        if isinstance(child, (EzLangParser.DeclarationContext, EzLangParser.ExternDeclContext)):
            return child
        if hasattr(child, 'declaration') and child.declaration() is not None:
            return child.declaration()
        if hasattr(child, 'externDecl') and child.externDecl() is not None:
            return child.externDecl()
        return None

    def _select_import_exports(self, requested_names, exports: dict[str, object]) -> set[str]:
        selected = {name for name in requested_names if name in exports}
        changed = True
        while changed:
            changed = False
            selected_text = "\n".join(exports[name].getText() for name in selected)
            for name in exports:
                if name in selected:
                    continue
                if re.search(rf'\b{re.escape(name)}\b', selected_text):
                    selected.add(name)
                    changed = True
        return selected

    def _export_decl_name(self, ctx: EzLangParser.ExportDeclContext) -> str | None:
        fn = ctx.functionDecl()
        if fn is not None:
            return fn.VAR_IDENTIFIER().getText()
        vd = ctx.variableDecl()
        if vd is not None:
            return self._qualified_name(vd)
        sd = ctx.structDecl()
        if sd is not None:
            return sd.TYPE_IDENTIFIER().getText()
        ta = ctx.typeAliasDecl()
        if ta is not None:
            return ta.TYPE_IDENTIFIER().getText()
        dd = ctx.declareDecl()
        if dd is not None:
            return self._qualified_name(dd)
        return None

    def visitExportDecl(self, ctx: EzLangParser.ExportDeclContext):
        prev_exporting = self._exporting
        self._exporting = True
        try:
            fn = ctx.functionDecl()
            if fn is not None: return fn.accept(self)
            vd = ctx.variableDecl()
            if vd is not None: return vd.accept(self)
            sd = ctx.structDecl()
            if sd is not None: return sd.accept(self)
            ta = ctx.typeAliasDecl()
            if ta is not None: return ta.accept(self)
            dd = ctx.declareDecl()
            if dd is not None: return dd.accept(self)
            return None
        finally:
            self._exporting = prev_exporting

    def _resolve_extern_path(self, raw_path: str) -> Path | None:
        """解析内置标准库 extern 路径。"""
        if raw_path.startswith('@std/'):
            root = Path(__file__).resolve().parents[3]
            return (root / 'packages' / 'std' / raw_path[len('@std/'):]).resolve()
        if raw_path.startswith('@pkg/'):
            root = Path(__file__).resolve().parents[3]
            return (root / 'packages' / raw_path[len('@pkg/'):]).resolve()
        return None

    def visitExternDecl(self, ctx: EzLangParser.ExternDeclContext):
        raw_path = decode_string_literal_token(ctx.STRING_LITERAL().getText())
        builtin_path = self._resolve_extern_path(raw_path)
        path = Path(raw_path)
        resolved_path = builtin_path or (path if path.is_absolute() else self.base_dir / path)
        resolved = str(resolved_path.resolve())
        target = ctx.targetPlatform().getText() if ctx.targetPlatform() is not None else None
        active = target is None or self.compile_target is None or target == self.compile_target
        info = {"path": resolved, "target": target, "active": active, "line": ctx.start.line}
        self.extern_libs.append(info)

        suffix = resolved_path.suffix
        is_system_lib = builtin_path is None and not path.is_absolute() and path.parent == Path('.') and suffix == ''
        if not is_system_lib and suffix not in self._supported_extern_exts:
            self.symbols.add_error(f"行 {ctx.start.line}: extern 路径格式不支持：'{raw_path}'")
        if active:
            if not is_system_lib and not resolved_path.exists():
                self.symbols.add_error(f"行 {ctx.start.line}: extern 路径不存在：'{raw_path}'")
            self.active_extern_libs.append(raw_path if is_system_lib else resolved)
        return None

    def visitDeclareDecl(self, ctx: EzLangParser.DeclareDeclContext):
        name = self._qualified_name(ctx)
        type_ctx = ctx.type_()
        type_ = self._get_type_from_ctx(type_ctx) if type_ctx is not None else None
        kind = SymbolKind.EXTERN_DECLARE
        symbol = Symbol(name, kind, type_, exported=self._exporting, line=ctx.start.line)
        self.symbols.define(symbol)
        generic_names = self._generic_names_from_type(type_)
        if generic_names:
            self.generic_templates[name] = (generic_names, type_ctx)
        linked_lib = self.active_extern_libs[-1] if self.active_extern_libs else None
        self.declare_extern_map[name] = linked_lib
        if linked_lib is None:
            self.symbols.add_warning(f"行 {ctx.start.line}: declare 符号 '{name}' 没有关联 extern 库")
        return None

    # ==================== Throw 语句 ====================

    def visitThrowStatement(self, ctx: EzLangParser.ThrowStatementContext):
        thrown_type = None
        if ctx.expression() is not None:
            thrown_type = ctx.expression().accept(self)
        if self._catch_throw_stack and thrown_type is not None:
            self._catch_throw_stack[-1].append(thrown_type)
        return thrown_type

    # ==================== 默认访问 ====================

    def defaultResult(self):
        return None

    def visitChildren(self, ctx):
        """重写：根据 Context 类型自动分发到对应的 visit 方法"""
        ctx_name = type(ctx).__name__
        if ctx_name.endswith("Context"):
            rule_name = ctx_name[:-7]
            method_name = "visit" + rule_name
            if method_name in type(self).__dict__:
                method = getattr(self, method_name)
                return method(ctx)
        return self._visit_children(ctx)

    def _visit_children(self, ctx):
        result = None
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if hasattr(child, 'accept'):
                r = child.accept(self)
                if r is not None:
                    result = r
        return result


def analyze(source: str, base_dir: Optional[os.PathLike | str] = None,
            compile_target: Optional[str] = None,
            allow_top_level_return: bool = False) -> SemanticAnalyzer:
    """分析 EzLang 源码，返回分析器实例（包含符号表和错误）"""
    from antlr4 import InputStream, CommonTokenStream
    from parser.EzLangLexer import EzLangLexer
    from parser.EzLangParser import EzLangParser as Parser

    lexer = EzLangLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = Parser(stream)
    parser.removeErrorListeners()
    tree = parser.compilationUnit()

    analyzer = SemanticAnalyzer(
        base_dir=base_dir,
        compile_target=compile_target,
        allow_top_level_return=allow_top_level_return,
    )
    tree.accept(analyzer)
    return analyzer
