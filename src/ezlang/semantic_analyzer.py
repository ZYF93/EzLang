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
        self.fields = fields or {}

class GenericPlaceholderType(Type):
    pass

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
    def __init__(self, tree):
        self.tree = tree
        self.symbol_table = SymbolTable()
        self.errors = []
        self.current_function = None

    def analyze(self):
        self.visit(self.tree)
        if self.errors:
            raise Exception("Semantic errors:\n" + "\n".join(self.errors))

    def enter_scope(self):
        self.symbol_table = SymbolTable(parent=self.symbol_table)

    def exit_scope(self):
        if self.symbol_table.parent:
            self.symbol_table = self.symbol_table.parent

    def visitTypeDeclaration(self, ctx: EzLangParser.TypeDeclarationContext):
        type_name = ctx.ID().getText()
        # 解析等号右边的类型
        aliased_type = None
        if ctx.type_():
            aliased_type = self.visit(ctx.type_())
        
        if aliased_type:
            self.symbol_table.define_type(type_name, aliased_type)
        else:
            self.symbol_table.define_type(type_name, Type(type_name))
        return self.visitChildren(ctx)

    def visitStructDeclaration(self, ctx: EzLangParser.StructDeclarationContext):
        struct_name = ctx.ID().getText()
        struct_type = StructType(struct_name)
        self.symbol_table.define_type(struct_name, struct_type)
        self.enter_scope()
        if ctx.genericParams():
            for param_id in ctx.genericParams().ID():
                self.symbol_table.define_type(param_id.getText(), GenericPlaceholderType(param_id.getText()))
        res = self.visitChildren(ctx)
        self.exit_scope()
        return res

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        var_type = self.visit(ctx.type_()) if ctx.type_() else None
        
        # 默认生存期是 LOCAL
        lifetime = Lifetime.LOCAL
        if ctx.STATIC():
            lifetime = Lifetime.STATIC
            
        self.symbol_table.define(var_name, Symbol(var_name, var_type, lifetime))
        return self.visitChildren(ctx)

    def visitFunctionExpression(self, ctx: EzLangParser.FunctionExpressionContext):
        # 进入函数，创建一个新的作用域
        self.enter_scope()
        res = self.visitChildren(ctx)
        self.exit_scope()
        return res

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

    def visitProgram(self, ctx: EzLangParser.ProgramContext):
        return self.visitChildren(ctx)