"""
EzLang Semantic Analyzer Module
"""

from .antlr_generated.EzLangVisitor import EzLangVisitor
from .antlr_generated.EzLangParser import EzLangParser
from enum import Enum

class Lifetime(Enum):
    LOCAL = 1      # 当前作用域（Arena）
    ESCAPED = 2    # 逃逸到父作用域（通常是返回值）
    STATIC = 3     # 全局

class Type:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"Type({self.name})"

class BasicType(Type):
    pass

class StructType(Type):
    def __init__(self, name, fields=None):
        super().__init__(name)
        self.fields = fields or {} # name -> {"type": Type, "required": bool}

class GenericPlaceholderType(Type):
    pass


class FunctionType(Type):
    def __init__(self, name, parameters=None, return_type=None):
        super().__init__(name)
        self.parameters = parameters or []
        self.return_type = return_type or BasicType("I32")

class Symbol:
    def __init__(self, name, type_obj, lifetime=Lifetime.LOCAL):
        self.name = name
        self.type_obj = type_obj
        self.lifetime = lifetime

class SymbolTable:
    def __init__(self, parent=None):
        self.symbols = {}
        self.types = {}
        if parent is None:
            self.types = {
                "I8": BasicType("I8"), "I32": BasicType("I32"), "I64": BasicType("I64"),
                "U8": BasicType("U8"), "U32": BasicType("U32"), "U64": BasicType("U64"),
                "F32": BasicType("F32"), "F64": BasicType("F64"),
                "Str": BasicType("Str"), "Bool": BasicType("Bool"),
                "Void": BasicType("Void"), "Vec": BasicType("Vec"),
            }
        self.parent = parent

    def define(self, name, symbol):
        self.symbols[name] = symbol

    def define_type(self, name, type_obj):
        self.types[name] = type_obj

    def lookup(self, name):
        if name in self.symbols: return self.symbols[name]
        return self.parent.lookup(name) if self.parent else None

    def lookup_type(self, name):
        if name in self.types: return self.types[name]
        return self.parent.lookup_type(name) if self.parent else None

class SemanticAnalyzer(EzLangVisitor):
    def __init__(self, tree=None):
        self.tree = tree
        self.symbol_table = SymbolTable()
        self.errors = []
        self.current_function = None
        self.function_stack = []

    def analyze(self):
        if self.tree:
            self.visit(self.tree)
        if self.errors:
            raise Exception("Semantic errors:\n" + "\n".join(self.errors))

    def enter_scope(self):
        self.symbol_table = SymbolTable(parent=self.symbol_table)

    def exit_scope(self):
        if self.symbol_table.parent:
            self.symbol_table = self.symbol_table.parent

    def _build_function_type(self, name, function_ctx):
        parameters = []
        if function_ctx.parameters():
            for param in function_ctx.parameters().parameter():
                param_name = "this" if param.THIS() else param.ID().getText()
                param_type = self.visit(param.type_())
                parameters.append(
                    {
                        "name": param_name,
                        "type": param_type,
                        "has_default": param.expression() is not None,
                    }
                )

        return_type = self.visit(function_ctx.type_()) if function_ctx.type_() else self.symbol_table.lookup_type("I32")
        return FunctionType(name, parameters=parameters, return_type=return_type)

    def _function_uses_block_body(self, function_ctx):
        body_text = function_ctx.getText()
        arrow_index = body_text.rfind("=>")
        if arrow_index == -1:
            return False
        return body_text[arrow_index + 2 :].strip().startswith("{")

    def _extract_function_type_ctx(self, type_ctx):
        if type_ctx is None:
            return None

        for i in range(type_ctx.getChildCount()):
            child = type_ctx.getChild(i)
            if isinstance(child, EzLangParser.FunctionTypeContext):
                return child
        return None

    def _validate_function_call(self, function_type, argument_list_ctx, callee_name):
        named_arguments = {}

        if argument_list_ctx:
            for arg in argument_list_ctx.namedArgument():
                if arg.ID() and arg.ASSIGN():
                    arg_name = arg.ID().getText()
                    if arg_name in named_arguments:
                        self.errors.append(f"Duplicate argument '{arg_name}' for function '{callee_name}'")
                    named_arguments[arg_name] = True
                else:
                    self.errors.append(f"Positional arguments are not allowed for function '{callee_name}'")

        for param in function_type.parameters:
            if param["name"] in named_arguments:
                continue
            if not param["has_default"]:
                self.errors.append(f"Missing required argument '{param['name']}' for function '{callee_name}'")

        for arg_name in named_arguments:
            if not any(param["name"] == arg_name for param in function_type.parameters):
                self.errors.append(f"Unknown argument '{arg_name}' for function '{callee_name}'")

    def visitTypeDeclaration(self, ctx: EzLangParser.TypeDeclarationContext):
        type_name = ctx.ID().getText()
        aliased_type = self.visit(ctx.type_()) if ctx.type_() else Type(type_name)
        self.symbol_table.define_type(type_name, aliased_type)
        return self.visitChildren(ctx)

    def visitStructDeclaration(self, ctx: EzLangParser.StructDeclarationContext):
        struct_name = ctx.ID().getText()
        struct_type = StructType(struct_name)
        self.symbol_table.define_type(struct_name, struct_type)
        
        self.enter_scope()
        if ctx.genericParams():
            for param_id in ctx.genericParams().ID():
                self.symbol_table.define_type(param_id.getText(), GenericPlaceholderType(param_id.getText()))
                
        # 收集字段
        body = ctx.structBody()
        if body:
            for i in range(body.getChildCount()):
                child = body.getChild(i)
                if isinstance(child, EzLangParser.BaseStructContext):
                    base_name = child.ID().getText()
                    base_type = self.symbol_table.lookup_type(base_name)
                    if base_type and isinstance(base_type, StructType):
                        for f_name, f_info in base_type.fields.items():
                            struct_type.fields[f_name] = f_info
                    else:
                        self.errors.append(f"Undefined base struct: {base_name}")
                elif isinstance(child, EzLangParser.FieldContext):
                    f_name = child.ID().getText()
                    f_type = self.visit(child.type_())
                    is_required = child.ASSIGN() is None
                    struct_type.fields[f_name] = {"type": f_type, "required": is_required}
        
        res = self.visitChildren(ctx)
        self.exit_scope()
        return res

    def visitStructLiteral(self, ctx: EzLangParser.StructLiteralContext):
        struct_name = ctx.ID().getText()
        st_type = self.symbol_table.lookup_type(struct_name)
        if not st_type or not isinstance(st_type, StructType):
            self.errors.append(f"Undefined struct: {struct_name}")
            return None
        
        # 检查传入的字段
        provided_fields = set()
        if ctx.structFields():
            for sf in ctx.structFields().structField():
                if sf.ID():
                    provided_fields.add(sf.ID().getText())
        
        # 验证所有必填字段
        for f_name, info in st_type.fields.items():
            if info["required"] and f_name not in provided_fields:
                self.errors.append(f"Field '{f_name}' of struct '{struct_name}' must be initialized")
        
        return st_type

    def visitPostfixExpression(self, ctx: EzLangParser.PostfixExpressionContext):
        # 处理调用形式的实例化 Data()
        base_val = self.visit(ctx.primaryExpression())
        
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, EzLangParser.PostfixContext) and child.LPAREN():
                # 如果 base_val 是一个结构体类型，则它是实例化
                if isinstance(base_val, StructType):
                    provided_fields = set()
                    # 在 EzLang 中，Data(val = 10) 会被解析为带有 argumentList 的调用
                    if child.argumentList():
                        for na in child.argumentList().namedArgument():
                            if na.ID(): provided_fields.add(na.ID().getText())
                    
                    for f_name, info in base_val.fields.items():
                        if info["required"] and f_name not in provided_fields:
                            self.errors.append(f"Field '{f_name}' of struct '{base_val.name}' must be initialized")
                    return base_val
        return base_val

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        var_type = self.visit(ctx.type_()) if ctx.type_() else None
        lifetime = Lifetime.STATIC if ctx.STATIC() else Lifetime.LOCAL
        self.symbol_table.define(var_name, Symbol(var_name, var_type, lifetime))
        return self.visitChildren(ctx)

    def visitFunctionDeclaration(self, ctx: EzLangParser.FunctionDeclarationContext):
        func_name = ctx.ID().getText()
        function_type = self._build_function_type(func_name, ctx.functionExpression())
        self.symbol_table.define(func_name, Symbol(func_name, function_type, Lifetime.STATIC))
        return self.visit(ctx.functionExpression())

    def visitFunctionExpression(self, ctx: EzLangParser.FunctionExpressionContext):
        function_name = "anonymous"
        if isinstance(ctx.parentCtx, EzLangParser.FunctionDeclarationContext):
            function_name = ctx.parentCtx.ID().getText()
            function_symbol = self.symbol_table.lookup(function_name)
            function_type = function_symbol.type_obj if function_symbol else self._build_function_type(function_name, ctx)
        else:
            function_type = self._build_function_type(function_name, ctx)

        self.enter_scope()
        self.function_stack.append({"name": function_name, "has_return": False})
        for param in function_type.parameters:
            self.symbol_table.define(param["name"], Symbol(param["name"], param["type"], Lifetime.LOCAL))

        result = self.visitChildren(ctx)
        function_state = self.function_stack.pop()
        if self._function_uses_block_body(ctx) and not function_state["has_return"]:
            self.errors.append(f"Function '{function_name}' must use an explicit return statement")
        self.exit_scope()
        return function_type

    def visitReturnStatement(self, ctx: EzLangParser.ReturnStatementContext):
        if not self.function_stack:
            self.errors.append("return statement is only allowed inside a function")
            return None

        self.function_stack[-1]["has_return"] = True
        if ctx.expression():
            self.visit(ctx.expression())
        return None

    def visitDeclareStatement(self, ctx: EzLangParser.DeclareStatementContext):
        symbol_name = ctx.ID().getText()
        function_type_ctx = self._extract_function_type_ctx(ctx.type_())

        if function_type_ctx:
            function_type = self.visit(function_type_ctx)
            function_type.name = symbol_name
            self.symbol_table.define(symbol_name, Symbol(symbol_name, function_type, Lifetime.STATIC))
        else:
            declared_type = self.visit(ctx.type_())
            self.symbol_table.define(symbol_name, Symbol(symbol_name, declared_type, Lifetime.STATIC))
        return None

    def visitSimpleType(self, ctx: EzLangParser.SimpleTypeContext):
        base_name = ctx.baseType().getText()
        t = self.symbol_table.lookup_type(base_name)
        if not t:
            self.errors.append(f"Undefined type: {base_name}")
            return Type(base_name)
        return t

    def visitBaseType(self, ctx: EzLangParser.BaseTypeContext):
        name = ctx.getText()
        t = self.symbol_table.lookup_type(name)
        if not t:
            self.errors.append(f"Undefined type: {name}")
            return Type(name)
        return t

    def visitPrimaryExpression(self, ctx: EzLangParser.PrimaryExpressionContext):
        if ctx.ID() or ctx.THIS():
            name = "this" if ctx.THIS() else ctx.ID().getText()
            t = self.symbol_table.lookup_type(name)
            if t: return t # 返回类型对象用于实例化检查
            sym = self.symbol_table.lookup(name)
            if sym: return sym.type_obj
        return self.visitChildren(ctx)

    def visitPostfixExpression(self, ctx: EzLangParser.PostfixExpressionContext):
        base_val = self.visit(ctx.primaryExpression())

        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, EzLangParser.PostfixContext) and child.LPAREN():
                if isinstance(base_val, StructType):
                    provided_fields = set()
                    if child.argumentList():
                        for na in child.argumentList().namedArgument():
                            if na.ID():
                                provided_fields.add(na.ID().getText())

                    for f_name, info in base_val.fields.items():
                        if info["required"] and f_name not in provided_fields:
                            self.errors.append(f"Field '{f_name}' of struct '{base_val.name}' must be initialized")
                    return base_val

                if isinstance(base_val, FunctionType):
                    self._validate_function_call(base_val, child.argumentList(), base_val.name)
                    return base_val.return_type

        return base_val

    def visitFunctionType(self, ctx: EzLangParser.FunctionTypeContext):
        parameters = []
        if ctx.parameters():
            for param in ctx.parameters().parameter():
                param_name = "this" if param.THIS() else param.ID().getText()
                param_type = self.visit(param.type_())
                parameters.append(
                    {
                        "name": param_name,
                        "type": param_type,
                        "has_default": param.expression() is not None,
                    }
                )

        return_type = self.visit(ctx.type_()) if ctx.type_() else self.symbol_table.lookup_type("Void")
        return FunctionType("fn", parameters=parameters, return_type=return_type)

    def visitProgram(self, ctx: EzLangParser.ProgramContext):
        return self.visitChildren(ctx)
