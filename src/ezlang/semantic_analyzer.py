"""
EzLang Semantic Analyzer Module
"""

from .antlr_generated.EzLangVisitor import EzLangVisitor
from .antlr_generated.EzLangParser import EzLangParser

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

class VectorType(Type):
    def __init__(self, element_type, size=None):
        super().__init__(f"Vec<{element_type.name}>")
        self.element_type = element_type
        self.size = size

class Symbol:
    def __init__(self, name, type_obj):
        self.name = name
        self.type_obj = type_obj

class SymbolTable:
    def __init__(self, parent=None):
        self.symbols = {}
        self.types = {}
        if parent is None:
            # Root table initialization with built-ins
            self.types = {
                "I8": BasicType("I8"),
                "I32": BasicType("I32"),
                "I64": BasicType("I64"),
                "U8": BasicType("U8"),
                "U32": BasicType("U32"),
                "U64": BasicType("U64"),
                "F32": BasicType("F32"),
                "F64": BasicType("F64"),
                "Str": BasicType("Str"),
                "Bool": BasicType("Bool"),
                "Void": BasicType("Void"),
                "Vec": BasicType("Vec"), # Base Vec identifier
            }
        self.parent = parent

    def define(self, name, symbol):
        self.symbols[name] = symbol

    def define_type(self, name, type_obj):
        self.types[name] = type_obj

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_type(self, name):
        if name in self.types:
            return self.types[name]
        if self.parent:
            return self.parent.lookup_type(name)
        return None

class SemanticAnalyzer(EzLangVisitor):
    def __init__(self, tree):
        self.tree = tree
        self.symbol_table = SymbolTable()
        self.errors = []

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
        # 暂时将别名定义为一个占位符或解析出的类型
        self.symbol_table.define_type(type_name, Type(type_name))
        return self.visitChildren(ctx)

    def visitStructDeclaration(self, ctx: EzLangParser.StructDeclarationContext):
        struct_name = ctx.ID().getText()
        struct_type = StructType(struct_name)
        self.symbol_table.define_type(struct_name, struct_type)
        
        self.enter_scope()
        # 如果有泛型参数，将它们加入当前作用域的类型表
        if ctx.genericParams():
            for param_id in ctx.genericParams().ID():
                self.symbol_table.define_type(param_id.getText(), GenericPlaceholderType(param_id.getText()))
        
        res = self.visitChildren(ctx)
        self.exit_scope()
        return res

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        var_type = None
        if ctx.type_():
            var_type = self.visit(ctx.type_())
        self.symbol_table.define(var_name, Symbol(var_name, var_type))
        return self.visitChildren(ctx)

    def visitType(self, ctx: EzLangParser.TypeContext):
        # 处理联合类型中的第一个
        return self.visit(ctx.getChild(0))

    def visitSimpleType(self, ctx: EzLangParser.SimpleTypeContext):
        base_name = ctx.baseType().getText()
        t = self.symbol_table.lookup_type(base_name)
        if not t:
            self.errors.append(f"Undefined type: {base_name}")
            return Type(base_name)
        
        # 处理后缀 (数组, 泛型等)
        # 目前简单实现，仅支持识别
        return t

    def visitBaseType(self, ctx: EzLangParser.BaseTypeContext):
        name = ctx.getText()
        t = self.symbol_table.lookup_type(name)
        if not t:
            self.errors.append(f"Undefined type: {name}")
            return Type(name)
        return t

    def visitParameter(self, ctx: EzLangParser.ParameterContext):
        # 处理参数类型解析，特别是 this: Counter
        param_name = ctx.getChild(0).getText()
        param_type = self.visit(ctx.type_())
        self.symbol_table.define(param_name, Symbol(param_name, param_type))
        return self.visitChildren(ctx)

    def visitProgram(self, ctx: EzLangParser.ProgramContext):
        return self.visitChildren(ctx)